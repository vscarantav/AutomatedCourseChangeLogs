# EN/PT Parity Instructions (from MATH108X pilot)

These rules come from the Math108X test run and should guide future EN↔PT
parity report runs. English is canon. Portuguese must reflect EN changes;
when it does not, point that out to Course Designers.

## Scope

- Pair courses as `{CODE}` (English) ↔ `{CODE}-PT` (Portuguese).
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
gap count significantly (the pilot found 443 findings, 432 high). Course
Designers should use the following triage order instead of reviewing every
finding:

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
When both EN and PT have a matching bank (by title structure or numeric
fingerprint), but the extracted answer keys differ:
- Some are caused by **wording differences** that our extraction treats as
  distinct (e.g. different choice IDs across languages). These are typically
  false positives for math/numerical questions where the graded value is the
  same number.
- True mismatches occur when a graded numeric value, formula result, or
  range is different between EN and PT. Focus on calculated and numerical
  question types first.

### Priority 4 — Unmatched EN banks (214 in the pilot)
Most of these are single-question banks (e.g. `Final Exam Q12`, `L03 Skill 2
Q4`) where the question lives inside a consolidated PT bank but the tool
could not automatically pair them. Before creating new PT banks:
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

- Generated: 2026-09-11
- EN snapshot: `2026-09-11_extracted`
- PT snapshot: `2026-09-11_extracted`
- Pages matched / missing in PT: 11 / 4
- Quizzes matched / missing in PT: 48 / 1
- Assignments matched / missing in PT: 5 / 0
- Question banks matched / missing in PT: 211 / 214
- Actionable findings: 443 (high=432, medium=7, low=4)

## Next productization steps

1. Extend slug maps beyond MATH108X.
2. Continue improving Q&A answer-key equality for matched banks.
3. EN/PT parity gaps appear on a dedicated **EN/PT Parity** tab in the
   weekly designer HTML report, with a brief pointer in Raw Logs by Course.
   The Monday week-over-week diff logic is unchanged. Full detail remains
   available via `python scripts/run_math108x_parity.py`.
