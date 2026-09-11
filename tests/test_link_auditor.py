import os
import sys
import tempfile
import unittest


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from link_auditor import (
    find_inaccessible_google_exports,
    is_inaccessible_google_export,
)
from parity_comparer import answer_keys_compatible, extract_answer_keys


class LinkAuditorTests(unittest.TestCase):
    def test_flags_google_docx_and_xlsx_exports(self):
        self.assertTrue(
            is_inaccessible_google_export(
                "https://docs.google.com/document/d/abc/export?format=docx"
            )
        )
        self.assertTrue(
            is_inaccessible_google_export(
                "https://docs.google.com/spreadsheets/d/abc/export?format=xlsx"
            )
        )
        self.assertTrue(
            is_inaccessible_google_export(
                "https://drive.google.com/uc?export=download&id=123"
            )
        )

    def test_allows_published_google_links(self):
        self.assertFalse(
            is_inaccessible_google_export(
                "https://docs.google.com/document/d/abc/pub"
            )
        )
        self.assertFalse(
            is_inaccessible_google_export(
                "https://docs.google.com/spreadsheets/d/e/2PACX-abc/pubhtml"
            )
        )
        self.assertFalse(
            is_inaccessible_google_export(
                "https://docs.google.com/document/d/abc/edit?usp=sharing"
            )
        )

    def test_finds_export_links_in_snapshot_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            wiki = os.path.join(tmp, "wiki_content")
            os.makedirs(wiki)
            with open(os.path.join(wiki, "page.html"), "w", encoding="utf-8") as handle:
                handle.write(
                    "<html><title>W02 Case Study Worksheet</title>"
                    '<a href="https://docs.google.com/document/d/1ABC/export?format=docx">Doc</a>'
                    '<a href="https://docs.google.com/document/d/1ABC/pub">OK</a>'
                    "</html>"
                )
            findings = find_inaccessible_google_exports(tmp)
            self.assertEqual(len(findings), 1)
            self.assertIn("format=docx", findings[0]["url"])
            self.assertEqual(findings[0]["display_title"], "W02 Case Study Worksheet")

    def test_uses_nearby_module_title_for_export_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = os.path.join(tmp, "course_settings")
            os.makedirs(settings)
            with open(os.path.join(settings, "module_meta.xml"), "w", encoding="utf-8") as handle:
                handle.write(
                    """
                    <modules>
                      <item>
                        <title>Budget Spreadsheet</title>
                        <url>https://docs.google.com/spreadsheets/d/xyz/export?format=xlsx</url>
                      </item>
                    </modules>
                    """
                )
            findings = find_inaccessible_google_exports(tmp)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["display_title"], "Budget Spreadsheet")


class AnswerKeyTests(unittest.TestCase):
    def test_extracts_numerical_correct_answer(self):
        qti = """
        <item ident="1" title="Q">
          <itemmetadata><qtimetadata><qtimetadatafield>
            <fieldlabel>question_type</fieldlabel>
            <fieldentry>numerical_question</fieldentry>
          </qtimetadatafield></qtimetadata></itemmetadata>
          <resprocessing>
            <respcondition continue="No">
              <conditionvar><varequal respident="response1">18.7</varequal></conditionvar>
              <setvar action="Set" varname="SCORE">100</setvar>
            </respcondition>
          </resprocessing>
        </item>
        """
        keys = extract_answer_keys(qti)
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys[0][0], "numerical_question")
        self.assertIn("eq:18.7", keys[0][1])

    def test_compatible_when_en_keys_subset_of_pt(self):
        en = (("numerical_question", frozenset({"eq:18.7"})),)
        pt = (
            ("numerical_question", frozenset({"eq:18.7"})),
            ("numerical_question", frozenset({"eq:42"})),
        )
        ok, detail = answer_keys_compatible(en, pt)
        self.assertTrue(ok)
        self.assertIn("consolidation", detail.lower())

    def test_incompatible_when_answer_missing(self):
        en = (("numerical_question", frozenset({"eq:18.7"})),)
        pt = (("numerical_question", frozenset({"eq:99"})),)
        ok, detail = answer_keys_compatible(en, pt)
        self.assertFalse(ok)
        self.assertIn("not found", detail.lower())


if __name__ == "__main__":
    unittest.main()
