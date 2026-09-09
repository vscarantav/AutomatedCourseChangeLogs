import os
import sys
import unittest


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from html_reporter import generate_html_report


def make_course(course_url):
    return {
        "course_name": "TEST101",
        "designer": "Test Designer",
        "has_changes": False,
        "is_new": False,
        "zero_changes_streak": 0,
        "categories": {},
        "course_url": course_url,
        "comparison_period": {
            "previous_date": "2026-09-01",
            "current_date": "2026-09-08",
        },
    }


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
        report = generate_html_report(
            "2026-09-08",
            [course],
        )

        comparison_text = (
            "Compared today's Canvas version (2026-09-08) with snapshot "
            "from 2026-09-01"
        )
        course_link = "href='https://canvas.example.edu/courses/123'"
        self.assertEqual(report.count(comparison_text), 3)
        self.assertEqual(report.count(course_link), 3)
        self.assertIn("title='Open live course in Canvas'", report)
        self.assertIn("target='_blank'", report)

    def test_non_http_course_url_is_not_rendered_as_a_link(self):
        report = generate_html_report(
            "2026-09-08",
            [make_course("javascript:alert('unsafe')")],
        )

        self.assertNotIn("javascript:", report)
        self.assertIn("<span class='course-name'>TEST101</span>", report)


if __name__ == "__main__":
    unittest.main()
