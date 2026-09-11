import os
import sys
import tempfile
import unittest


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from parity_comparer import (
    assessment_structure_key,
    classify_assessment_role,
    compare_snapshots,
    pair_by_structure,
    parity_report_to_compact,
    ResourceItem,
    ParityFinding,
    ParityReport,
)


class ParityComparerTests(unittest.TestCase):
    def test_week_lesson_roles_align_en_and_pt(self):
        self.assertEqual(
            assessment_structure_key("W03 Exam: Unit 1"),
            assessment_structure_key("S03 Exame: Unidade 1"),
        )
        self.assertEqual(
            classify_assessment_role("Lesson 5 Extra Practice Quiz (Optional)"),
            classify_assessment_role("Lição 5 – Questionário de Prática Extra (Opcional)"),
        )

    def test_pair_by_structure_matches_unique_keys(self):
        en = [
            ResourceItem(
                "quiz",
                "W02 Checkpoint: Budgeting",
                "",
                structure_key=assessment_structure_key("W02 Checkpoint: Budgeting"),
            )
        ]
        pt = [
            ResourceItem(
                "quiz",
                "S02 Checkpoint: Orçamento",
                "",
                structure_key=assessment_structure_key("S02 Checkpoint: Orçamento"),
            )
        ]
        matched, missing, extra = pair_by_structure(en, pt)
        self.assertEqual(len(matched), 1)
        self.assertEqual(missing, [])
        self.assertEqual(extra, [])

    def test_compare_snapshots_flags_missing_pt_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            en = os.path.join(tmp, "en")
            pt = os.path.join(tmp, "pt")
            os.makedirs(os.path.join(en, "wiki_content"))
            os.makedirs(os.path.join(pt, "wiki_content"))
            with open(
                os.path.join(en, "wiki_content", "course-homepage.html"),
                "w",
                encoding="utf-8",
            ) as f:
                f.write("<html><title>Homepage</title></html>")
            with open(
                os.path.join(en, "wiki_content", "excel-tips-and-tricks.html"),
                "w",
                encoding="utf-8",
            ) as f:
                f.write("<html><title>Excel Tips</title></html>")
            with open(
                os.path.join(pt, "wiki_content", "plano-de-aula.html"),
                "w",
                encoding="utf-8",
            ) as f:
                f.write("<html><title>Plano de Aula</title></html>")

            report = compare_snapshots("MATH108X", en, "MATH108X-PT", pt)
            missing = [
                f
                for f in report.findings
                if f.category == "pages" and f.severity == "high"
            ]
            self.assertEqual(report.stats["pages_matched"], 1)
            self.assertEqual(report.stats["pages_missing_in_pt"], 1)
            self.assertTrue(any("Excel Tips" in f.en_title for f in missing))

    def test_parity_report_to_compact_caps_highlights(self):
        findings = [
            ParityFinding("info", "pages", "A", "A-pt", "matched"),
            ParityFinding("high", "pages", "Missing", "", "missing page"),
            ParityFinding("medium", "quizzes", "Quiz", "Quiz-pt", "draw mismatch"),
            ParityFinding("low", "question_banks", "", "Extra", "extra bank"),
        ]
        report = ParityReport(
            en_code="MATH108X",
            pt_code="MATH108X-PT",
            en_snapshot="2026-09-11_extracted",
            pt_snapshot="2026-09-11_extracted",
            findings=findings,
            stats={
                "actionable_findings": 3,
                "high_findings": 1,
                "medium_findings": 1,
                "low_findings": 1,
            },
        )
        compact = parity_report_to_compact(report, max_highlights=1)
        self.assertEqual(compact["en_code"], "MATH108X")
        self.assertEqual(len(compact["highlights"]), 1)
        self.assertEqual(compact["highlights"][0]["severity"], "high")
        self.assertEqual(compact["highlights_omitted"], 1)


if __name__ == "__main__":
    unittest.main()
