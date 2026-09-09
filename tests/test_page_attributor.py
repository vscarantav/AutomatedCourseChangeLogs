import datetime
import os
import sys
import unittest
from unittest.mock import mock_open, patch


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from html_reporter import generate_file_item_html
from page_attributor import attribute_page_changes, course_id_from_url
import canvas_exporter
import page_attributor


class FakeCanvasResponse:
    def __init__(self, payload, next_url=None):
        self._payload = payload
        self.links = {"next": {"url": next_url}} if next_url else {}

    def json(self):
        return self._payload


class PageAttributorTests(unittest.TestCase):
    def test_attributes_only_revisions_inside_exact_export_window(self):
        course_data = {
            "categories": {
                "pages": [{
                    "file_path": "wiki_content/weekly-overview.html",
                    "file_title": "Weekly Overview",
                    "status": "Modified",
                    "labels": ["Content Change"],
                    "diff_lines": ["-Old", "+New"],
                }]
            }
        }

        def revisions(course_id, page_url):
            self.assertEqual(course_id, "123")
            self.assertEqual(page_url, "weekly-overview")
            return [
                {
                    "revision_id": 1,
                    "updated_at": "2026-09-01T18:00:00Z",
                    "edited_by": {"id": 10, "display_name": "Before Boundary"},
                },
                {
                    "revision_id": 2,
                    "updated_at": "2026-09-05T12:30:00Z",
                    "edited_by": {"id": 20, "display_name": "Jane Smith"},
                },
                {
                    "revision_id": 3,
                    "updated_at": "2026-09-06T12:30:00Z",
                    "edited_by": None,
                },
                {
                    "revision_id": 4,
                    "updated_at": "2026-09-09T12:30:00Z",
                    "edited_by": {"id": 30, "display_name": "After Boundary"},
                },
            ]

        boundaries = [
            (datetime.datetime(2026, 9, 1, 18, tzinfo=datetime.timezone.utc), "export_metadata"),
            (datetime.datetime(2026, 9, 8, 18, tzinfo=datetime.timezone.utc), "export_metadata"),
        ]
        with patch("page_attributor._load_snapshot_boundary", side_effect=boundaries):
            stats = attribute_page_changes(
                course_data,
                "123",
                "course/2026-09-01_extracted",
                "course/2026-09-08_extracted",
                revision_fetcher=revisions,
            )
        attribution = course_data["categories"]["pages"][0]["attribution"]

        self.assertEqual(stats["pages_attributed"], 1)
        self.assertEqual(attribution["status"], "attributed")
        self.assertEqual(attribution["window_precision"], "exact")
        self.assertEqual(attribution["revision_count"], 2)
        self.assertEqual(attribution["unattributed_revision_count"], 1)
        self.assertEqual(
            [actor["name"] for actor in attribution["actors"]],
            ["Jane Smith"],
        )

    def test_deleted_page_is_marked_unavailable_without_api_call(self):
        course_data = {
            "categories": {
                "pages": [{
                    "file_path": "wiki_content/deleted-page.html",
                    "status": "Deleted",
                    "labels": [],
                    "diff_lines": [],
                }]
            }
        }

        def unexpected_fetch(*args):
            self.fail("Deleted pages should not trigger a revision lookup")

        stats = attribute_page_changes(
            course_data,
            "123",
            os.path.join("course", "2026-09-01_extracted"),
            os.path.join("course", "2026-09-08_extracted"),
            revision_fetcher=unexpected_fetch,
        )

        attribution = course_data["categories"]["pages"][0]["attribution"]
        self.assertEqual(stats["pages_unavailable"], 1)
        self.assertEqual(attribution["status"], "unavailable")
        self.assertIn("Deleted pages", attribution["reason"])

    def test_course_id_parser_rejects_non_canvas_course_urls(self):
        self.assertEqual(
            course_id_from_url("https://canvas.example.edu/courses/456/settings"),
            "456",
        )
        self.assertIsNone(course_id_from_url("https://canvas.example.edu/accounts/456"))
        self.assertIsNone(course_id_from_url(""))

    def test_report_renders_and_escapes_attribution(self):
        item = {
            "file_path": "wiki_content/example.html",
            "file_title": "Example",
            "status": "Modified",
            "labels": [],
            "diff_lines": [],
            "attribution": {
                "status": "attributed",
                "window_precision": "exact",
                "unattributed_revision_count": 0,
                "actors": [{
                    "user_id": 7,
                    "name": "Jane <Admin>",
                    "profile_url": "https://canvas.example.edu/users/7",
                    "changed_at": "2026-09-05T12:30:00Z",
                    "revision_id": 2,
                }],
            },
        }

        rendered = generate_file_item_html(item)

        self.assertIn("Changed by Jane &lt;Admin&gt;", rendered)
        self.assertNotIn("Jane <Admin>", rendered)
        self.assertIn("Canvas page history", rendered)
        self.assertIn("https://canvas.example.edu/users/7", rendered)

    def test_page_revision_client_follows_canvas_pagination(self):
        responses = [
            FakeCanvasResponse([{"revision_id": 2}], "https://canvas/next"),
            FakeCanvasResponse([{"revision_id": 1}]),
        ]

        with patch("canvas_exporter._canvas_request", side_effect=responses) as request:
            revisions = canvas_exporter.get_page_revisions("123", "page with spaces")

        self.assertEqual([revision["revision_id"] for revision in revisions], [2, 1])
        first_call = request.call_args_list[0]
        second_call = request.call_args_list[1]
        self.assertIn("page%20with%20spaces/revisions", first_call.args[1])
        self.assertEqual(first_call.kwargs["params"], {"per_page": 100})
        self.assertIsNone(second_call.kwargs["params"])

    def test_course_files_request_includes_editor_user_and_paginates(self):
        responses = [
            FakeCanvasResponse([{"id": 1}], "https://canvas/files?page=2"),
            FakeCanvasResponse([{"id": 2}]),
        ]

        with patch("canvas_exporter._canvas_request", side_effect=responses) as request:
            files = canvas_exporter.get_course_files("123")

        self.assertEqual([file["id"] for file in files], [1, 2])
        self.assertEqual(
            request.call_args_list[0].kwargs["params"],
            {"include[]": "user", "per_page": 100},
        )
        self.assertIsNone(request.call_args_list[1].kwargs["params"])

    def test_course_audit_client_resolves_linked_users(self):
        response = FakeCanvasResponse({
            "events": [{"id": "event-1", "links": {"user": 7}}],
            "linked": {"users": [{"id": 7, "name": "Course Editor"}]},
            "links": {},
        })

        with patch("canvas_exporter._canvas_request", return_value=response):
            audit = canvas_exporter.get_course_audit_events(
                "123",
                "2026-09-01T00:00:00Z",
                "2026-09-08T23:59:59Z",
            )

        self.assertEqual(audit["events"][0]["id"], "event-1")
        self.assertEqual(audit["users"]["7"]["name"], "Course Editor")

    def test_snapshot_boundary_prefers_exact_export_metadata(self):
        metadata = '{"export_created_at":"2026-09-08T18:23:32Z"}'
        with patch("page_attributor.os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=metadata)):
                boundary, source = page_attributor._load_snapshot_boundary(
                    "course/2026-09-08_extracted",
                    is_end=True,
                )

        self.assertEqual(source, "export_metadata")
        self.assertEqual(boundary.isoformat(), "2026-09-08T18:23:32+00:00")


if __name__ == "__main__":
    unittest.main()
