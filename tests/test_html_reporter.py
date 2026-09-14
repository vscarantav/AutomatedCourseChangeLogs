import os
import sys
import unittest


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from html_reporter import generate_html_report


def make_course(course_url, course_name="TEST101", impact=None, has_changes=False):
    course = {
        "course_name": course_name,
        "designer": "Test Designer",
        "has_changes": has_changes,
        "is_new": False,
        "zero_changes_streak": 0,
        "categories": {},
        "course_url": course_url,
        "comparison_period": {
            "previous_date": "2026-09-01",
            "current_date": "2026-09-08",
        },
    }
    if impact:
        course["course_ai_impact"] = impact
        course["course_ai_summary"] = f"{course_name} summary"
    return course


class HtmlReporterTests(unittest.TestCase):
    def test_course_report_shows_comparison_dates_and_live_course_link(self):
        course = make_course("https://canvas.example.edu/courses/123")
        course["has_changes"] = True
        course["course_ai_summary"] = "A page changed."
        course["course_ai_impact"] = "Low"
        course["categories"] = {
            "pages": [{
                "file_path": "wiki_content/example.html",
                "file_title": "Example",
                "status": "Modified",
                "labels": ["Content Change"],
                "diff_lines": ["-Old", "+New"],
            }]
        }
        course["category_ai_summaries"] = {
            "pages": "A page had a content update."
        }
        report = generate_html_report(
            "2026-09-08",
            [course],
        )

        comparison_text = (
            "Compared today's Canvas version (Sep 8, 2026) with snapshot "
            "from Sep 1, 2026"
        )
        course_link = "href='https://canvas.example.edu/courses/123'"
        self.assertEqual(report.count(comparison_text), 2)
        self.assertEqual(report.count(course_link), 2)
        self.assertIn("title='Open live course in Canvas'", report)
        self.assertIn("target='_blank'", report)
        self.assertIn("Impact: Low", report)
        self.assertEqual(report.count("Impact: Low"), 2)
        self.assertIn("1 change", report)
        self.assertIn("A page had a content update.", report)
        self.assertNotIn("Raw Logs by Category", report)
        self.assertNotIn("logs-category", report)

    def test_report_flags_inaccessible_google_export_links(self):
        course = make_course(None, "LINK101", has_changes=False)
        course["inaccessible_google_exports"] = [{
            "url": "https://docs.google.com/document/d/abc/export?format=docx",
            "relative_path": "wiki_content/page.html",
            "display_title": "W02 Case Study Worksheet",
            "issue": "Google Doc export link (docx).",
        }]
        report = generate_html_report("2026-09-08", [course])
        self.assertIn("Google Export Link Issues", report)
        self.assertIn("export?format=docx", report)
        self.assertIn("1 Google export link", report)
        self.assertIn("Student Access Issue", report)
        self.assertIn("W02 Case Study Worksheet", report)
        self.assertNotIn("wiki_content/page.html", report)
        self.assertNotIn('id="metric-link-issues"', report)
        self.assertNotIn('id="metric-parity-gaps"', report)

    def test_report_includes_compact_en_pt_parity_section(self):
        # EN/PT parity tab is temporarily disabled in the HTML report.
        course = make_course(None, "MATH108X", has_changes=False)
        course["en_pt_parity"] = {
            "en_code": "MATH108X",
            "pt_code": "MATH108X-PT",
            "en_snapshot": "2026-09-11_extracted",
            "pt_snapshot": "2026-09-11_extracted",
            "stats": {
                "actionable_findings": 3,
                "high_findings": 2,
                "medium_findings": 1,
                "pages_missing_in_pt": 1,
                "quizzes_missing_in_pt": 0,
                "assignments_missing_in_pt": 0,
                "banks_missing_in_pt": 2,
            },
            "highlights": [{
                "severity": "high",
                "category": "pages",
                "en_title": "Excel Tips",
                "pt_title": "",
                "message": "EN page is missing in PT.",
            }],
            "highlights_omitted": 2,
        }
        report = generate_html_report("2026-09-08", [course])
        self.assertNotIn('id="parity-tab"', report)
        self.assertNotIn("switchTab('parity-tab'", report)
        self.assertNotIn("EN/PT Parity Gaps", report)
        logs_section = report.split('id="logs-course"')[1]
        self.assertNotIn("EN/PT gap", logs_section)
        self.assertNotIn("Excel Tips", logs_section)

    def test_raw_logs_by_course_sorts_by_impact(self):
        courses = [
            make_course(None, "LOW101", impact="Low", has_changes=True),
            make_course(None, "NONE101", has_changes=False),
            make_course(None, "HIGH101", impact="High", has_changes=True),
            make_course(None, "MED101", impact="Medium", has_changes=True),
        ]
        for course in courses:
            if course["has_changes"]:
                course["categories"] = {
                    "pages": [{
                        "file_path": "wiki_content/example.html",
                        "file_title": "Example",
                        "status": "Modified",
                        "labels": ["Content Change"],
                        "diff_lines": ["-Old", "+New"],
                    }]
                }

        report = generate_html_report("2026-09-08", courses)
        logs_section = report.split('id="logs-course"')[1]
        high_pos = logs_section.find("HIGH101")
        med_pos = logs_section.find("MED101")
        low_pos = logs_section.find("LOW101")
        none_pos = logs_section.find("NONE101")

        self.assertTrue(high_pos < med_pos < low_pos < none_pos)

    def test_non_http_course_url_is_not_rendered_as_a_link(self):
        report = generate_html_report(
            "2026-09-08",
            [make_course("javascript:alert('unsafe')")],
        )

        self.assertNotIn("javascript:", report)
        self.assertIn("<span class='course-name'>TEST101</span>", report)


if __name__ == "__main__":
    unittest.main()
