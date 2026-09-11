import json
import os
import sys
import tempfile
import unittest


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from differ import generate_diff_data


def _write_file(path, content="hello"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


class ZeroChangeStreakTests(unittest.TestCase):
    def _make_snapshots(self, course_dir, older_name, newer_name, newer_content="hello"):
        older = os.path.join(course_dir, older_name)
        newer = os.path.join(course_dir, newer_name)
        _write_file(os.path.join(older, "wiki_content", "page.html"), "hello")
        _write_file(os.path.join(newer, "wiki_content", "page.html"), newer_content)
        return older, newer

    def test_streak_is_stored_per_course_not_shared(self):
        with tempfile.TemporaryDirectory() as history_dir:
            course_a = os.path.join(history_dir, "COURSE_A")
            course_b = os.path.join(history_dir, "COURSE_B")
            older_a, newer_a = self._make_snapshots(
                course_a, "2026-09-08_extracted", "2026-09-15_extracted"
            )
            older_b, newer_b = self._make_snapshots(
                course_b, "2026-09-08_extracted", "2026-09-15_extracted"
            )

            data_a = generate_diff_data(older_a, newer_a, "COURSE_A")
            data_b = generate_diff_data(older_b, newer_b, "COURSE_B")

            self.assertFalse(data_a["has_changes"])
            self.assertFalse(data_b["has_changes"])
            self.assertEqual(data_a["zero_changes_streak"], 1)
            self.assertEqual(data_b["zero_changes_streak"], 1)
            self.assertFalse(os.path.exists(os.path.join(history_dir, "state.json")))
            self.assertTrue(os.path.exists(os.path.join(course_a, "state.json")))
            self.assertTrue(os.path.exists(os.path.join(course_b, "state.json")))

    def test_same_snapshot_rerun_does_not_increment_streak(self):
        with tempfile.TemporaryDirectory() as history_dir:
            course_dir = os.path.join(history_dir, "COURSE_A")
            older, newer = self._make_snapshots(
                course_dir, "2026-09-08_extracted", "2026-09-15_extracted"
            )

            first = generate_diff_data(older, newer, "COURSE_A")
            second = generate_diff_data(older, newer, "COURSE_A")

            self.assertEqual(first["zero_changes_streak"], 1)
            self.assertEqual(second["zero_changes_streak"], 1)

    def test_streak_increments_across_distinct_no_change_snapshots(self):
        with tempfile.TemporaryDirectory() as history_dir:
            course_dir = os.path.join(history_dir, "COURSE_A")
            week1_old, week1_new = self._make_snapshots(
                course_dir, "2026-09-08_extracted", "2026-09-15_extracted"
            )
            generate_diff_data(week1_old, week1_new, "COURSE_A")

            week2_old, week2_new = self._make_snapshots(
                course_dir, "2026-09-15_extracted", "2026-09-22_extracted"
            )
            data = generate_diff_data(week2_old, week2_new, "COURSE_A")

            self.assertEqual(data["zero_changes_streak"], 2)

    def test_changes_reset_streak(self):
        with tempfile.TemporaryDirectory() as history_dir:
            course_dir = os.path.join(history_dir, "COURSE_A")
            older, newer = self._make_snapshots(
                course_dir,
                "2026-09-08_extracted",
                "2026-09-15_extracted",
                newer_content="changed",
            )

            with open(os.path.join(course_dir, "state.json"), "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "zero_changes_streak": 4,
                        "last_current_snapshot": "2026-09-01_extracted",
                    },
                    f,
                )

            data = generate_diff_data(older, newer, "COURSE_A")
            self.assertTrue(data["has_changes"])
            self.assertEqual(data["zero_changes_streak"], 0)


if __name__ == "__main__":
    unittest.main()
