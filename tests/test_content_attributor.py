import datetime
import os
import sys
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from content_attributor import attribute_course_changes
from differ import _manifest_resource_categories, get_semantic_labels
from html_reporter import generate_file_item_html


WINDOW_START = datetime.datetime(2026, 9, 1, 12, tzinfo=datetime.timezone.utc)
WINDOW_END = datetime.datetime(2026, 9, 8, 12, tzinfo=datetime.timezone.utc)


def item(path, status="Modified", title="Example"):
    return {
        "file_path": path,
        "file_title": title,
        "status": status,
        "labels": [],
        "diff_lines": [],
    }


def course_data(**categories):
    defaults = {
        "manifest": [],
        "assignments": [],
        "pages": [],
        "quizzes_banks": [],
        "course_settings": [],
        "rubrics": [],
        "discussions": [],
        "files_media": [],
        "other": [],
    }
    defaults.update(categories)
    return {"categories": defaults}


class ContentAttributorTests(unittest.TestCase):
    def boundaries(self):
        return patch(
            "content_attributor._load_snapshot_boundary",
            side_effect=[
                (WINDOW_START, "export_metadata"),
                (WINDOW_END, "export_metadata"),
            ],
        )

    def test_unsupported_categories_are_explicitly_marked_unavailable(self):
        assignment = item("g123/assignment_settings.xml")
        quiz = item("g456/assessment_qti.xml")
        data = course_data(assignments=[assignment], quizzes_banks=[quiz])

        with self.boundaries():
            stats = attribute_course_changes(
                data,
                "123",
                "previous",
                "current",
                file_fetcher=lambda course_id: [],
                folder_fetcher=lambda course_id: [],
                discussion_fetcher=lambda course_id: [],
                audit_fetcher=lambda *args: {"events": [], "users": {}},
            )

        self.assertEqual(stats["items_unavailable"], 2)
        self.assertEqual(assignment["attribution"]["status"], "unavailable")
        self.assertIn("Assignments API", assignment["attribution"]["reason"])
        self.assertIn("Editor Unavailable", generate_file_item_html(assignment))

    def test_file_uses_last_content_editor_inside_comparison_window(self):
        changed_file = item("web_resources/Uploaded Media/guide.pdf")
        data = course_data(files_media=[changed_file])
        files = [{
            "id": 55,
            "folder_id": 9,
            "display_name": "guide.pdf",
            "modified_at": "2026-09-05T10:00:00Z",
            "user": {
                "id": 7,
                "display_name": "File Editor",
                "html_url": "https://canvas.example.edu/users/7",
            },
        }]
        folders = [{"id": 9, "full_name": "course files/Uploaded Media"}]

        with self.boundaries():
            stats = attribute_course_changes(
                data,
                "123",
                "previous",
                "current",
                file_fetcher=lambda course_id: files,
                folder_fetcher=lambda course_id: folders,
                discussion_fetcher=lambda course_id: [],
                audit_fetcher=lambda *args: {"events": [], "users": {}},
            )

        attribution = changed_file["attribution"]
        self.assertEqual(stats["items_attributed"], 1)
        self.assertEqual(attribution["source"], "canvas_files_api")
        self.assertEqual(attribution["actors"][0]["name"], "File Editor")

    def test_file_editor_outside_window_is_not_guessed(self):
        changed_file = item("web_resources/guide.pdf")
        data = course_data(files_media=[changed_file])
        files = [{
            "id": 55,
            "display_name": "guide.pdf",
            "modified_at": "2026-09-09T10:00:00Z",
            "user": {"id": 7, "display_name": "Later Editor"},
        }]

        with self.boundaries():
            attribute_course_changes(
                data,
                "123",
                "previous",
                "current",
                file_fetcher=lambda course_id: files,
                folder_fetcher=lambda course_id: [],
                discussion_fetcher=lambda course_id: [],
                audit_fetcher=lambda *args: {"events": [], "users": {}},
            )

        self.assertEqual(changed_file["attribution"]["status"], "unavailable")
        self.assertEqual(changed_file["attribution"]["actors"], [])

    def test_added_discussion_uses_topic_creator(self):
        discussion = item("g123.xml", status="Added", title="Welcome Topic")
        data = course_data(discussions=[discussion])
        topics = [{
            "id": 77,
            "title": "Welcome Topic",
            "user_name": "Discussion Creator",
            "posted_at": "2026-09-04T09:00:00Z",
        }]

        with self.boundaries():
            attribute_course_changes(
                data,
                "123",
                "previous",
                "current",
                file_fetcher=lambda course_id: [],
                folder_fetcher=lambda course_id: [],
                discussion_fetcher=lambda course_id: topics,
                audit_fetcher=lambda *args: {"events": [], "users": {}},
            )

        attribution = discussion["attribution"]
        self.assertEqual(attribution["status"], "attributed")
        self.assertEqual(attribution["verb"], "Created by")
        self.assertEqual(attribution["actors"][0]["name"], "Discussion Creator")

    def test_discussion_creator_outside_window_is_not_guessed(self):
        discussion = item("g123.xml", status="Added", title="Welcome Topic")
        data = course_data(discussions=[discussion])
        topics = [{
            "id": 77,
            "title": "Welcome Topic",
            "user_name": "Original Creator",
            "posted_at": "2026-08-04T09:00:00Z",
        }]

        with self.boundaries():
            attribute_course_changes(
                data,
                "123",
                "previous",
                "current",
                file_fetcher=lambda course_id: [],
                folder_fetcher=lambda course_id: [],
                discussion_fetcher=lambda course_id: topics,
                audit_fetcher=lambda *args: {"events": [], "users": {}},
            )

        self.assertEqual(discussion["attribution"]["status"], "unavailable")
        self.assertEqual(discussion["attribution"]["actors"], [])

    def test_course_setting_uses_user_backed_course_audit_event(self):
        setting = item("course_settings/course_settings.xml")
        data = course_data(course_settings=[setting])
        audit = {
            "events": [{
                "event_type": "updated",
                "created_at": "2026-09-03T08:00:00Z",
                "links": {"user": 42},
            }],
            "users": {"42": {"id": 42, "name": "Settings Editor"}},
        }

        with self.boundaries():
            attribute_course_changes(
                data,
                "123",
                "previous",
                "current",
                file_fetcher=lambda course_id: [],
                folder_fetcher=lambda course_id: [],
                discussion_fetcher=lambda course_id: [],
                audit_fetcher=lambda *args: audit,
            )

        attribution = setting["attribution"]
        self.assertEqual(attribution["status"], "attributed")
        self.assertEqual(attribution["source"], "canvas_course_audit_api")
        self.assertEqual(attribution["actors"][0]["name"], "Settings Editor")

    def test_course_audit_event_outside_window_is_not_used(self):
        setting = item("course_settings/course_settings.xml")
        data = course_data(course_settings=[setting])
        audit = {
            "events": [{
                "event_type": "updated",
                "created_at": "2026-08-03T08:00:00Z",
                "links": {"user": 42},
            }],
            "users": {"42": {"id": 42, "name": "Earlier Editor"}},
        }

        with self.boundaries():
            attribute_course_changes(
                data,
                "123",
                "previous",
                "current",
                file_fetcher=lambda course_id: [],
                folder_fetcher=lambda course_id: [],
                discussion_fetcher=lambda course_id: [],
                audit_fetcher=lambda *args: audit,
            )

        self.assertEqual(setting["attribution"]["status"], "unavailable")
        self.assertEqual(setting["attribution"]["actors"], [])

    def test_missing_canvas_course_id_marks_every_item_unavailable(self):
        page = item("wiki_content/example.html")
        assignment = item("g123/assignment_settings.xml")
        data = course_data(pages=[page], assignments=[assignment])

        with self.boundaries():
            stats = attribute_course_changes(
                data,
                None,
                "previous",
                "current",
            )

        self.assertEqual(stats["items_unavailable"], 2)
        self.assertIn("no usable Canvas course URL", page["attribution"]["reason"])

    def test_manifest_identifies_discussion_resource_files(self):
        manifest = """<?xml version='1.0'?>
        <manifest xmlns='http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1'>
          <resources>
            <resource identifier='g123' type='imsdt_xmlv1p1'>
              <file href='g123.xml'/>
            </resource>
          </resources>
        </manifest>
        """
        manifest_tree = ET.ElementTree(ET.fromstring(manifest))
        with patch("differ.os.path.exists", return_value=True):
            with patch("differ.ET.parse", return_value=manifest_tree):
                categories = _manifest_resource_categories("snapshot")

        self.assertEqual(categories["g123.xml"], "discussions")

    def test_unneeded_metadata_and_date_labels_are_not_generated(self):
        labels = get_semantic_labels([
            '-<assignment due_at="2026-09-01" identifier="old-id">',
            '+<assignment due_at="2026-09-08" identifier="new-id">',
        ])

        self.assertNotIn("Date/Restriction", labels)
        self.assertNotIn("Metadata/System", labels)


if __name__ == "__main__":
    unittest.main()
