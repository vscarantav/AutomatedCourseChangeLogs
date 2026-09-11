"""
Math108X EN/PT parity pilot.

Does NOT touch the Monday weekly change-log report.
Compares latest EN vs PT snapshots and writes:
  - reports/parity/MATH108X_parity_<date>.md
  - docs/en_pt_parity_instructions.md (rules learned from this pilot)
"""

from __future__ import annotations

import datetime
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from parity_comparer import compare_course_pair, render_parity_markdown  # noqa: E402


INSTRUCTIONS_TEMPLATE = """# EN/PT Parity Instructions (from MATH108X pilot)

These rules come from the Math108X test run and should guide future EN↔PT
parity report runs. English is canon. Portuguese must reflect EN changes;
when it does not, point that out to Course Designers.

## Scope

- Pair courses as `{{CODE}}` (English) ↔ `{{CODE}}-PT` (Portuguese).
- Compare **latest extracted snapshots** of each language (not week-over-week
  within one language).
- Keep this check **separate** from the Monday weekly Canvas change report
  until productized.

## What to compare

1. **Pages (`wiki_content`)**
   - PT should have an equivalent for every EN page.
   - Filenames often differ (`w01-vocabulary` ↔ `s01-vocabulario`).
   - Maintain a known slug map per course; start from MATH108X map in
     `src/parity_comparer.py` (`KNOWN_PAGE_PAIRS`).

2. **Quizzes / assessments**
   - Match by structural key: role + week (`W`/`S`) + lesson + unit.
   - Roles include lesson, exam, review, checkpoint, honesty, syllabus,
     WhatsApp, extra practice, final exam / final review.
   - After title pairing, compare linked `sourcebank_ref` counts. Unequal
     draws are a high-priority designer flag.

3. **Assignments**
   - Same structural matching as quizzes (`W02 Case Study` ↔ `S02 Estudo de Caso`).
   - Ignore EN-only internal shells (e.g. Quality Assurance DO NOT PUBLISH).

4. **Question banks (MATH108X hard case)**
   - EN often uses many **single-question object banks** pulled into quizzes
     via `sourcebank_ref`.
   - PT often **consolidates** variants into fewer multi-item banks.
   - Do **not** require 1:1 bank-file parity by Canvas ID.
   - Match by:
     - bank title structure (Final Exam Q12, Unit/Unidade, L01 skill name, Q#)
     - overlapping question types
     - language-agnostic **numeric fingerprints** (shared numbers/formulas)
     - **answer-key equality**: extract correct answers from QTI scoring
       (`varequal`, numeric ranges, credited choices). EN wording can differ
       from PT, but graded answer values should still match. If PT consolidates
       banks, every EN answer key should appear inside the PT bank.
   - Unmatched EN banks / answer-key mismatches are actionable for Course
     Designers.

## MATH108X-specific guidance

MATH108X is a unique case among all EN/PT pairs because of its question bank
structure. EN has **425 mostly single-question banks** that PT consolidates
into **215 multi-item banks**. This architectural difference inflates the raw
gap count significantly. Course Designers should use the following triage
order instead of reviewing every finding:

### Priority 1 — Missing pages (fast wins)
4 EN pages have no PT equivalent: `Accessibility Aids`, `Excel Tips & Tricks`,
`Rubrics Basics`, `W02 Introductions`. These are straightforward to resolve.

### Priority 2 — Quiz draw mismatches
Several matched quizzes pull from different numbers of question banks:
- `Unit 1/2/3 Review Extra Practice` — EN draws from many more banks than PT
- `W03 Exam: Unit 1` — EN 26 draws vs PT 12
- `W07 Final Exam` — EN 26 draws vs PT 25

This does **not** necessarily mean content is missing. PT may have the same
questions inside fewer, consolidated banks. Verify that the PT quiz still
covers the same question pool by checking the actual quiz items.

### Priority 3 — Answer-key mismatches on matched banks
When both EN and PT have a matching bank but the extracted answer keys differ:
- Some are caused by **wording differences** that our extraction treats as
  distinct. These are typically false positives for math/numerical questions
  where the graded value is the same number.
- True mismatches occur when a graded numeric value, formula result, or
  range is different between EN and PT. Focus on calculated and numerical
  question types first.

### Priority 4 — Unmatched EN banks
Most of these are single-question banks where the question lives inside a
consolidated PT bank but the tool could not automatically pair them. Before
creating new PT banks:
1. Search the PT quiz that covers the same unit/lesson.
2. Verify the question text and correct answer exist inside the PT quiz or
   one of its linked banks.
3. Only flag as a genuine gap if the question content is truly absent from PT.

### Known false positives to ignore
- PT-only pages `Centrally-Managed Graders`, `S07 Vocabulário`, `Teste`,
  `Textbook Information` — these are intentional PT additions, not gaps.
- PT-only quiz `S01 Questionário: Introdução à Tutoria Online` — PT-specific
  onboarding quiz with no EN equivalent.

## Designer messaging

When EN has a change or resource that PT lacks:

> English is the canon course. This EN change/resource is not reflected in
> Portuguese. Please update the PT course so pages, quizzes, and
> question/answer coverage stay aligned.

For MATH108X specifically, include:

> Note: MATH108X-EN uses many single-question banks that Portuguese
> consolidates into fewer multi-item banks. Many "unmatched bank" findings
> are a structural difference, not missing content. Please verify by checking
> whether the question/answer exists inside a consolidated PT bank before
> adding duplicates.

## How to run the MATH108X pilot

```bash
python scripts/run_math108x_parity.py
```

Outputs:
- `reports/parity/MATH108X_parity_<date>.md` — findings for designers
- `docs/en_pt_parity_instructions.md` — this instruction file (refreshed)

## Latest MATH108X pilot snapshot

- Generated: {generated_at}
- EN snapshot: `{en_snapshot}`
- PT snapshot: `{pt_snapshot}`
- Pages matched / missing in PT: {pages_matched} / {pages_missing}
- Quizzes matched / missing in PT: {quizzes_matched} / {quizzes_missing}
- Assignments matched / missing in PT: {assignments_matched} / {assignments_missing}
- Question banks matched / missing in PT: {banks_matched} / {banks_missing}
- Actionable findings: {actionable} (high={high}, medium={medium}, low={low})

## Next productization steps

1. Extend slug maps beyond MATH108X.
2. Continue improving Q&A answer-key equality for matched banks.
3. EN/PT parity gaps appear on a dedicated **EN/PT Parity** tab in the
   weekly designer HTML report, with a brief pointer in Raw Logs by Course.
   The Monday week-over-week diff logic is unchanged. Full detail remains
   available via `python scripts/run_math108x_parity.py`.
"""


def main():
    history_dir = os.path.join(ROOT_DIR, "all_course_history")
    report = compare_course_pair(history_dir, "MATH108X", "MATH108X-PT")
    markdown = render_parity_markdown(report)

    parity_dir = os.path.join(ROOT_DIR, "reports", "parity")
    docs_dir = os.path.join(ROOT_DIR, "docs")
    os.makedirs(parity_dir, exist_ok=True)
    os.makedirs(docs_dir, exist_ok=True)

    stamp = datetime.date.today().strftime("%Y-%m-%d")
    report_path = os.path.join(parity_dir, f"MATH108X_parity_{stamp}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    instructions = INSTRUCTIONS_TEMPLATE.format(
        generated_at=stamp,
        en_snapshot=report.en_snapshot,
        pt_snapshot=report.pt_snapshot,
        pages_matched=report.stats["pages_matched"],
        pages_missing=report.stats["pages_missing_in_pt"],
        quizzes_matched=report.stats["quizzes_matched"],
        quizzes_missing=report.stats["quizzes_missing_in_pt"],
        assignments_matched=report.stats["assignments_matched"],
        assignments_missing=report.stats["assignments_missing_in_pt"],
        banks_matched=report.stats["banks_matched"],
        banks_missing=report.stats["banks_missing_in_pt"],
        actionable=report.stats["actionable_findings"],
        high=report.stats["high_findings"],
        medium=report.stats["medium_findings"],
        low=report.stats["low_findings"],
    )
    instructions_path = os.path.join(docs_dir, "en_pt_parity_instructions.md")
    with open(instructions_path, "w", encoding="utf-8") as f:
        f.write(instructions)

    print(f"MATH108X EN/PT parity complete.")
    print(f"EN snapshot: {report.en_snapshot}")
    print(f"PT snapshot: {report.pt_snapshot}")
    print(
        "Summary: "
        f"pages missing={report.stats['pages_missing_in_pt']}, "
        f"quizzes missing={report.stats['quizzes_missing_in_pt']}, "
        f"assignments missing={report.stats['assignments_missing_in_pt']}, "
        f"banks missing={report.stats['banks_missing_in_pt']}, "
        f"actionable={report.stats['actionable_findings']}"
    )
    print(f"Wrote {report_path}")
    print(f"Wrote {instructions_path}")


if __name__ == "__main__":
    main()
