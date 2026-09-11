"""
EN (canon) vs PT course parity comparison.

English is authoritative. Portuguese should mirror EN pages, quizzes,
assignments, and assessment question coverage. Canvas IDs differ across
languages, so matching is by normalized titles / structural keys.
"""

from __future__ import annotations

import html as html_lib
import os
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional


WEEK_RE = re.compile(r"\b(?:W|S)(\d{1,2})\b", re.I)
LESSON_RE = re.compile(r"\b(?:Lesson|Li[cç][aã]o|L)[\s\-]*(\d{1,2})\b", re.I)
UNIT_RE = re.compile(r"\b(?:Unit|Unidade)\s*(\d{1,2})\b", re.I)
QNUM_RE = re.compile(r"\bQ\s*(\d{1,3})\b", re.I)

# Shared EN/PT page slug pairs observed in MATH108X (extend per course later).
KNOWN_PAGE_PAIRS = {
    "setup-notes-and-course-settings": "setup-notes-and-course-settings",
    "w01-vocabulary": "s01-vocabulario",
    "w02-vocabulary": "s02-vocabulario",
    "w03-vocabulary": "s03-vocabulario",
    "w04-vocabulary": "s04-vocabulario",
    "w05-vocabulary": "s05-vocabulario",
    "w06-vocabulary": "s06-vocabulario",
    "installing-microsoft-excel": "instalar-microsoft-excel",
    "attention-messaging-instructors-and-graders": "atencao-mensagens-para-instrutores-e-avaliadores",
    "teaching-notes": "teaching-notes-and-outreach",
    "course-homepage": "plano-de-aula",
}


def strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_text(text: str) -> str:
    text = strip_accents(html_lib.unescape(text or ""))
    text = text.lower()
    text = re.sub(r"[_\-/]+", " ", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def slug_from_filename(filename: str) -> str:
    return os.path.splitext(os.path.basename(filename))[0]


def extract_html_title(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="ignore") as handle:
            content = handle.read(20000)
    except OSError:
        return slug_from_filename(path)
    match = re.search(r"<title[^>]*>(.*?)</title>", content, re.I | re.S)
    if match and match.group(1).strip():
        return re.sub(r"\s+", " ", match.group(1)).strip()
    return slug_from_filename(path)


def classify_assessment_role(title: str) -> str:
    n = normalize_text(title)
    if "final exam review" in n or "revisao para o exame final" in n or "revisao do exame final" in n:
        return "final_exam_review"
    if "final exam" in n or "exame final" in n:
        return "final_exam"
    if "extra practice" in n or "pratica extra" in n or "questionario de pratica extra" in n:
        return "extra_practice"
    if "honesty" in n or "honestidade" in n:
        return "honesty"
    if "plagiarism" in n or "plagio" in n:
        return "plagiarism_ai"
    if "syllabus" in n or "conteudo do curso" in n:
        return "syllabus"
    if "whatsapp participation" in n or "participacao no whatsapp" in n:
        return "whatsapp_participation"
    if "whatsapp" in n:
        return "whatsapp_quiz"
    if "checkpoint" in n:
        return "checkpoint"
    if "exam" in n or "exame" in n:
        return "exam"
    if "review" in n or "revisao" in n:
        return "review"
    if "lesson" in n or "licao" in n:
        return "lesson"
    if "quiz" in n or "questionario" in n:
        return "quiz"
    return "other"


def assessment_structure_key(title: str) -> tuple:
    week = WEEK_RE.search(title)
    lesson = LESSON_RE.search(title)
    unit = UNIT_RE.search(title)
    role = classify_assessment_role(title)
    return (
        role,
        int(week.group(1)) if week else None,
        int(lesson.group(1)) if lesson else None,
        int(unit.group(1)) if unit else None,
    )


def bank_structure_key(title: str) -> tuple:
    n = normalize_text(title)
    qnum = QNUM_RE.search(title)
    lesson = LESSON_RE.search(title)
    unit = UNIT_RE.search(title)
    role = "other"
    if "final exam review" in n or ("revisao" in n and "final" in n):
        role = "final_exam_review"
    elif "final exam" in n or "exame final" in n:
        role = "final_exam"
    elif "unit" in n or "unidade" in n:
        role = "unit_exam"
    elif lesson or re.match(r"^l\d+", n):
        role = "lesson_skill"
    return (
        role,
        int(lesson.group(1)) if lesson else None,
        int(unit.group(1)) if unit else None,
        int(qnum.group(1)) if qnum else None,
        tuple(sorted(set(re.findall(r"[a-z]{4,}|\d+(?:\.\d+)?", n)))[:12]),
    )


def numeric_fingerprint(text: str) -> tuple:
    """Language-agnostic numeric/formula tokens useful for math Q&A matching."""
    nums = re.findall(r"-?\d+(?:\.\d+)?", text or "")
    filtered = [n for n in nums if n not in {"0", "1", "-1"}]
    return tuple(sorted(filtered)[:40])


def _normalize_answer_token(value: str) -> str:
    text = html_lib.unescape(value or "").strip()
    text = strip_accents(text).lower()
    text = re.sub(r"\s+", " ", text)
    return text


def extract_answer_keys(qti_text: str) -> tuple:
    """
    Extract language-agnostic correct-answer signatures from QTI items.

    For each question item we keep:
      (question_type, frozenset of correct answer tokens)

    Tokens come from scoring conditions (varequal / numeric ranges) and from
    multiple-choice labels marked correct. This is the 'deeper' check beyond
    title pairing: EN and PT may word questions differently, but correct
    answers (18.7, choice id, formula result) should still match.
    """
    keys = []
    for item_match in re.finditer(r"<item\b[^>]*>.*?</item>", qti_text or "", re.I | re.S):
        item = item_match.group(0)
        qtype_match = re.search(
            r"<fieldlabel>\s*question_type\s*</fieldlabel>\s*<fieldentry>(.*?)</fieldentry>",
            item,
            re.I | re.S,
        )
        qtype = (qtype_match.group(1).strip() if qtype_match else "unknown").lower()

        answers = set()
        # Prefer conditions that award full credit.
        for cond in re.finditer(
            r"<respcondition\b[^>]*>.*?</respcondition>", item, re.I | re.S
        ):
            block = cond.group(0)
            if not re.search(
                r'<setvar[^>]*varname="SCORE"[^>]*>\s*100\s*</setvar>',
                block,
                re.I | re.S,
            ):
                continue
            for value in re.findall(r"<varequal\b[^>]*>(.*?)</varequal>", block, re.I | re.S):
                token = _normalize_answer_token(re.sub(r"<[^>]+>", "", value))
                if token:
                    answers.add(f"eq:{token}")
            gte = re.findall(r"<vargte\b[^>]*>(.*?)</vargte>", block, re.I | re.S)
            lte = re.findall(r"<varlte\b[^>]*>(.*?)</varlte>", block, re.I | re.S)
            for low, high in zip(gte, lte):
                answers.add(
                    f"range:{_normalize_answer_token(low)}..{_normalize_answer_token(high)}"
                )

        # Multiple choice / answers: labels with explicit correct metadata.
        for label in re.finditer(
            r"<response_label\b([^>]*)>(.*?)</response_label>", item, re.I | re.S
        ):
            attrs = label.group(1)
            body = label.group(2)
            ident_match = re.search(r'ident="([^"]+)"', attrs, re.I)
            if re.search(r'correct="yes"|rarea="ellipse"', attrs, re.I):
                token = ident_match.group(1) if ident_match else _normalize_answer_token(body)
                if token:
                    answers.add(f"choice:{_normalize_answer_token(token)}")

        if not answers:
            # Fallback: any varequal in the item (some QTI variants omit SCORE=100).
            for value in re.findall(r"<varequal\b[^>]*>(.*?)</varequal>", item, re.I | re.S):
                token = _normalize_answer_token(re.sub(r"<[^>]+>", "", value))
                if token:
                    answers.add(f"eq:{token}")

        if answers:
            keys.append((qtype, frozenset(answers)))

    return tuple(keys)


def answer_keys_compatible(en_keys: tuple, pt_keys: tuple) -> tuple:
    """
    Return (ok, detail).

    When PT consolidates multiple EN single-question banks, EN keys should
    appear as a subset of PT keys. When counts match, require equal multisets.
    """
    if not en_keys and not pt_keys:
        return True, "No extractable answer keys on either side."
    if not en_keys:
        return False, "EN bank has no extractable answer keys."
    if not pt_keys:
        return False, "PT bank has no extractable answer keys."

    en_set = set(en_keys)
    pt_set = set(pt_keys)
    if en_set == pt_set:
        return True, "Answer keys match."
    if en_set.issubset(pt_set):
        return True, "EN answer keys found inside PT bank (possible consolidation)."
    missing = en_set - pt_set
    return (
        False,
        f"{len(missing)} EN answer key(s) not found in PT "
        f"(EN {len(en_keys)} item key(s), PT {len(pt_keys)} item key(s)).",
    )


@dataclass
class ResourceItem:
    kind: str
    title: str
    path: str
    file_id: str = ""
    item_count: int = 0
    question_types: list = field(default_factory=list)
    sourcebank_refs: list = field(default_factory=list)
    fingerprint: tuple = field(default_factory=tuple)
    answer_keys: tuple = field(default_factory=tuple)
    structure_key: tuple = field(default_factory=tuple)


@dataclass
class ParityFinding:
    severity: str  # high | medium | low | info
    category: str
    en_title: str
    pt_title: str
    message: str


@dataclass
class ParityReport:
    en_code: str
    pt_code: str
    en_snapshot: str
    pt_snapshot: str
    findings: list
    stats: dict


def latest_extracted_dir(course_dir: str) -> Optional[str]:
    if not os.path.isdir(course_dir):
        return None
    extracted = [
        d
        for d in os.listdir(course_dir)
        if d.endswith("_extracted") and os.path.isdir(os.path.join(course_dir, d))
    ]
    if not extracted:
        return None
    extracted.sort(reverse=True)
    return os.path.join(course_dir, extracted[0])


def load_pages(snapshot_dir: str) -> list:
    wiki = os.path.join(snapshot_dir, "wiki_content")
    items = []
    if not os.path.isdir(wiki):
        return items
    for name in sorted(os.listdir(wiki)):
        if not name.endswith(".html"):
            continue
        path = os.path.join(wiki, name)
        title = extract_html_title(path)
        items.append(
            ResourceItem(
                kind="page",
                title=title,
                path=path,
                file_id=slug_from_filename(name),
                structure_key=(slug_from_filename(name),),
            )
        )
    return items


def load_quizzes(snapshot_dir: str) -> list:
    items = []
    for name in sorted(os.listdir(snapshot_dir)):
        meta = os.path.join(snapshot_dir, name, "assessment_meta.xml")
        if not os.path.isfile(meta):
            continue
        with open(meta, encoding="utf-8", errors="ignore") as handle:
            text = handle.read()
        match = re.search(r"<title>(.*?)</title>", text, re.I | re.S)
        title = match.group(1).strip() if match else name
        qti_path = os.path.join(snapshot_dir, "non_cc_assessments", f"{name}.xml.qti")
        refs = []
        if os.path.isfile(qti_path):
            with open(qti_path, encoding="utf-8", errors="ignore") as handle:
                qti = handle.read()
            refs = re.findall(r"<sourcebank_ref>(.*?)</sourcebank_ref>", qti)
        items.append(
            ResourceItem(
                kind="quiz",
                title=title,
                path=meta,
                file_id=name,
                sourcebank_refs=refs,
                structure_key=assessment_structure_key(title),
            )
        )
    return items


def load_assignments(snapshot_dir: str) -> list:
    items = []
    for name in sorted(os.listdir(snapshot_dir)):
        settings = os.path.join(snapshot_dir, name, "assignment_settings.xml")
        if not os.path.isfile(settings):
            continue
        with open(settings, encoding="utf-8", errors="ignore") as handle:
            text = handle.read()
        match = re.search(r"<title>(.*?)</title>", text, re.I | re.S)
        title = match.group(1).strip() if match else name
        if "do not publish" in title.lower() or "quality assurance" in title.lower():
            continue
        items.append(
            ResourceItem(
                kind="assignment",
                title=title,
                path=settings,
                file_id=name,
                structure_key=assessment_structure_key(title),
            )
        )
    return items


def load_question_banks(snapshot_dir: str) -> list:
    folder = os.path.join(snapshot_dir, "non_cc_assessments")
    items = []
    if not os.path.isdir(folder):
        return items
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".xml.qti"):
            continue
        path = os.path.join(folder, name)
        with open(path, encoding="utf-8", errors="ignore") as handle:
            text = handle.read()
        if "<objectbank" not in text:
            continue
        title_match = re.search(
            r"bank_title</fieldlabel>\s*<fieldentry>(.*?)</fieldentry>",
            text,
            re.I | re.S,
        )
        title = title_match.group(1).strip() if title_match else name
        qtypes = [
            q.strip()
            for q in re.findall(
                r"<fieldlabel>\s*question_type\s*</fieldlabel>\s*<fieldentry>(.*?)</fieldentry>",
                text,
                re.I | re.S,
            )
        ]
        item_count = len(re.findall(r"<item[\s>]", text))
        file_id = name.replace(".xml.qti", "")
        items.append(
            ResourceItem(
                kind="question_bank",
                title=title,
                path=path,
                file_id=file_id,
                item_count=item_count,
                question_types=qtypes,
                fingerprint=numeric_fingerprint(text),
                answer_keys=extract_answer_keys(text),
                structure_key=bank_structure_key(title),
            )
        )
    return items


def pair_by_structure(en_items: list, pt_items: list) -> tuple:
    """Greedy 1:1 pairing by structure_key, then leftover unmatched."""
    pt_by_key = defaultdict(list)
    for item in pt_items:
        pt_by_key[item.structure_key].append(item)

    matched = []
    unmatched_en = []
    used_pt = set()

    for en in en_items:
        candidates = [
            p for p in pt_by_key.get(en.structure_key, []) if id(p) not in used_pt
        ]
        if len(candidates) == 1:
            matched.append((en, candidates[0]))
            used_pt.add(id(candidates[0]))
        elif len(candidates) > 1:
            en_tokens = set(normalize_text(en.title).split())
            best = max(
                candidates,
                key=lambda p: len(en_tokens & set(normalize_text(p.title).split())),
            )
            matched.append((en, best))
            used_pt.add(id(best))
        else:
            unmatched_en.append(en)

    unmatched_pt = [p for p in pt_items if id(p) not in used_pt]
    return matched, unmatched_en, unmatched_pt


def pair_pages(en_pages: list, pt_pages: list) -> tuple:
    pt_by_slug = {p.file_id: p for p in pt_pages}
    matched = []
    unmatched_en = []
    used = set()

    for en in en_pages:
        pt_slug = KNOWN_PAGE_PAIRS.get(en.file_id)
        if pt_slug and pt_slug in pt_by_slug:
            matched.append((en, pt_by_slug[pt_slug]))
            used.add(pt_slug)
            continue
        if en.file_id in pt_by_slug:
            matched.append((en, pt_by_slug[en.file_id]))
            used.add(en.file_id)
            continue
        unmatched_en.append(en)

    unmatched_pt = [p for p in pt_pages if p.file_id not in used]
    return matched, unmatched_en, unmatched_pt


def pair_question_banks(en_banks: list, pt_banks: list) -> tuple:
    """
    MATH108X challenge:
    EN often stores one variant/question per bank; PT may consolidate.
    Match first by structure key (role/lesson/unit/Q#), then by numeric fingerprint.
    """
    matched, unmatched_en, unmatched_pt = pair_by_structure(en_banks, pt_banks)

    still_unmatched_en = []
    pt_pool = list(unmatched_pt)
    for en in unmatched_en:
        if not en.fingerprint:
            still_unmatched_en.append(en)
            continue
        best = None
        best_score = 0
        for pt in pt_pool:
            if not pt.fingerprint:
                continue
            shared = len(set(en.fingerprint) & set(pt.fingerprint))
            type_ok = (
                not en.question_types
                or not pt.question_types
                or bool(set(en.question_types) & set(pt.question_types))
            )
            if type_ok and shared > best_score and shared >= 3:
                best_score = shared
                best = pt
        if best is not None:
            matched.append((en, best))
            pt_pool.remove(best)
        else:
            still_unmatched_en.append(en)

    return matched, still_unmatched_en, pt_pool


def _bank_consolidation_note(en_code: str) -> str:
    """Courses known to consolidate EN single-question banks into fewer PT banks."""
    if en_code.upper() in {"MATH108X"}:
        return (
            f" For {en_code}, EN uses many single-question banks while PT "
            "consolidates them — confirm the question/answer exists inside "
            "a consolidated PT bank or quiz."
        )
    return ""


def compare_snapshots(en_code: str, en_snapshot: str, pt_code: str, pt_snapshot: str) -> ParityReport:
    findings = []

    en_pages = load_pages(en_snapshot)
    pt_pages = load_pages(pt_snapshot)
    en_quizzes = load_quizzes(en_snapshot)
    pt_quizzes = load_quizzes(pt_snapshot)
    en_assignments = load_assignments(en_snapshot)
    pt_assignments = load_assignments(pt_snapshot)
    en_banks = load_question_banks(en_snapshot)
    pt_banks = load_question_banks(pt_snapshot)

    page_matched, page_missing, page_extra = pair_pages(en_pages, pt_pages)
    for en in page_missing:
        findings.append(
            ParityFinding(
                "high",
                "pages",
                en.title,
                "",
                f"EN page is missing in PT (slug: {en.file_id}). Course Designers should add the PT equivalent.",
            )
        )
    for pt in page_extra:
        findings.append(
            ParityFinding(
                "medium",
                "pages",
                "",
                pt.title,
                f"PT page has no EN counterpart (slug: {pt.file_id}). Verify it is intentional.",
            )
        )
    for en, pt in page_matched:
        findings.append(
            ParityFinding("info", "pages", en.title, pt.title, "Page pair matched.")
        )

    quiz_matched, quiz_missing, quiz_extra = pair_by_structure(en_quizzes, pt_quizzes)
    for en in quiz_missing:
        findings.append(
            ParityFinding(
                "high",
                "quizzes",
                en.title,
                "",
                "EN quiz/assessment has no structural PT match. Course Designers should mirror this quiz in PT.",
            )
        )
    for pt in quiz_extra:
        findings.append(
            ParityFinding(
                "medium",
                "quizzes",
                "",
                pt.title,
                "PT quiz/assessment has no structural EN match.",
            )
        )
    for en, pt in quiz_matched:
        en_refs = len(en.sourcebank_refs)
        pt_refs = len(pt.sourcebank_refs)
        if en_refs and pt_refs and en_refs != pt_refs:
            findings.append(
                ParityFinding(
                    "high",
                    "quizzes",
                    en.title,
                    pt.title,
                    f"Matched quizzes differ in linked question-bank draws (EN {en_refs} vs PT {pt_refs}).",
                )
            )
        else:
            findings.append(
                ParityFinding(
                    "info",
                    "quizzes",
                    en.title,
                    pt.title,
                    "Quiz pair matched structurally.",
                )
            )

    asg_matched, asg_missing, asg_extra = pair_by_structure(en_assignments, pt_assignments)
    for en in asg_missing:
        findings.append(
            ParityFinding(
                "high",
                "assignments",
                en.title,
                "",
                "EN assignment is missing a PT counterpart.",
            )
        )
    for pt in asg_extra:
        findings.append(
            ParityFinding(
                "medium",
                "assignments",
                "",
                pt.title,
                "PT assignment has no EN counterpart.",
            )
        )
    for en, pt in asg_matched:
        findings.append(
            ParityFinding(
                "info", "assignments", en.title, pt.title, "Assignment pair matched."
            )
        )

    consolidation_note = _bank_consolidation_note(en_code)
    bank_matched, bank_missing, bank_extra = pair_question_banks(en_banks, pt_banks)
    for en in bank_missing:
        findings.append(
            ParityFinding(
                "high",
                "question_banks",
                en.title,
                "",
                (
                    f"EN question bank unmatched in PT "
                    f"({en.item_count} item(s); types={', '.join(en.question_types[:3]) or 'unknown'})."
                    f"{consolidation_note}"
                ),
            )
        )
    for pt in bank_extra:
        findings.append(
            ParityFinding(
                "low",
                "question_banks",
                "",
                pt.title,
                f"PT question bank unmatched to EN ({pt.item_count} item(s)).",
            )
        )
    for en, pt in bank_matched:
        ok, detail = answer_keys_compatible(en.answer_keys, pt.answer_keys)
        if not ok:
            findings.append(
                ParityFinding(
                    "high",
                    "question_banks",
                    en.title,
                    pt.title,
                    f"Matched banks differ in answer keys: {detail}",
                )
            )
        elif en.item_count != pt.item_count:
            findings.append(
                ParityFinding(
                    "medium",
                    "question_banks",
                    en.title,
                    pt.title,
                    f"Bank pair matched but item counts differ (EN {en.item_count} vs PT {pt.item_count}). {detail}",
                )
            )
        else:
            findings.append(
                ParityFinding(
                    "info",
                    "question_banks",
                    en.title,
                    pt.title,
                    f"Question bank pair matched. {detail}",
                )
            )

    actionable = [f for f in findings if f.severity != "info"]
    stats = {
        "pages_en": len(en_pages),
        "pages_pt": len(pt_pages),
        "pages_matched": len(page_matched),
        "pages_missing_in_pt": len(page_missing),
        "quizzes_en": len(en_quizzes),
        "quizzes_pt": len(pt_quizzes),
        "quizzes_matched": len(quiz_matched),
        "quizzes_missing_in_pt": len(quiz_missing),
        "assignments_en": len(en_assignments),
        "assignments_pt": len(pt_assignments),
        "assignments_matched": len(asg_matched),
        "assignments_missing_in_pt": len(asg_missing),
        "banks_en": len(en_banks),
        "banks_pt": len(pt_banks),
        "banks_matched": len(bank_matched),
        "banks_missing_in_pt": len(bank_missing),
        "actionable_findings": len(actionable),
        "high_findings": sum(1 for f in actionable if f.severity == "high"),
        "medium_findings": sum(1 for f in actionable if f.severity == "medium"),
        "low_findings": sum(1 for f in actionable if f.severity == "low"),
    }

    return ParityReport(
        en_code=en_code,
        pt_code=pt_code,
        en_snapshot=os.path.basename(en_snapshot),
        pt_snapshot=os.path.basename(pt_snapshot),
        findings=findings,
        stats=stats,
    )


def compare_course_pair(history_dir: str, en_code: str, pt_code: str = None) -> ParityReport:
    pt_code = pt_code or f"{en_code}-PT"
    en_dir = os.path.join(history_dir, en_code)
    pt_dir = os.path.join(history_dir, pt_code)
    en_snap = latest_extracted_dir(en_dir)
    pt_snap = latest_extracted_dir(pt_dir)
    if not en_snap:
        raise FileNotFoundError(f"No extracted snapshot for {en_code} under {en_dir}")
    if not pt_snap:
        raise FileNotFoundError(f"No extracted snapshot for {pt_code} under {pt_dir}")
    return compare_snapshots(en_code, en_snap, pt_code, pt_snap)


def parity_report_to_compact(report: ParityReport, max_highlights: int = 20) -> dict:
    """
    Compact payload for the weekly HTML report.
    Keeps summary stats plus a capped list of high/medium designer actions.
    """
    severity_rank = {"high": 0, "medium": 1, "low": 2}
    actionable = [
        f for f in report.findings if f.severity in {"high", "medium"}
    ]
    actionable.sort(
        key=lambda f: (
            severity_rank.get(f.severity, 9),
            f.category,
            f.en_title or f.pt_title,
        )
    )
    highlights = [
        {
            "severity": f.severity,
            "category": f.category,
            "en_title": f.en_title,
            "pt_title": f.pt_title,
            "message": f.message,
        }
        for f in actionable[:max_highlights]
    ]
    return {
        "en_code": report.en_code,
        "pt_code": report.pt_code,
        "en_snapshot": report.en_snapshot,
        "pt_snapshot": report.pt_snapshot,
        "stats": dict(report.stats),
        "highlights": highlights,
        "highlights_omitted": max(0, len(actionable) - len(highlights)),
    }


def enrich_courses_with_en_pt_parity(courses_data: list, history_dir: str) -> int:
    """
    Attach compact EN/PT parity summaries to EN and PT course rows.
    Does not alter week-over-week diff data. Returns number of pairs compared.
    """
    by_code = {c.get("course_name"): c for c in courses_data if c.get("course_name")}
    en_codes = set()
    for code in by_code:
        if code.endswith("-PT"):
            en_codes.add(code[:-3])
        else:
            en_codes.add(code)

    compared = 0
    for en_code in sorted(en_codes):
        pt_code = f"{en_code}-PT"
        en_history = os.path.join(history_dir, en_code)
        pt_history = os.path.join(history_dir, pt_code)
        if not os.path.isdir(en_history) or not os.path.isdir(pt_history):
            continue

        try:
            report = compare_course_pair(history_dir, en_code, pt_code)
            compact = parity_report_to_compact(report)
        except FileNotFoundError as exc:
            print(f"EN/PT parity skipped for {en_code}: {exc}")
            continue
        except Exception as exc:
            print(f"EN/PT parity failed for {en_code}: {exc}")
            continue

        compared += 1
        if en_code in by_code:
            by_code[en_code]["en_pt_parity"] = compact
        if pt_code in by_code:
            # Same summary on PT row so designer filters still surface it.
            by_code[pt_code]["en_pt_parity"] = compact

        actionable = compact["stats"].get("actionable_findings", 0)
        try:
            print(
                f"EN/PT parity {en_code} -> {pt_code}: "
                f"{actionable} actionable finding(s)."
            )
        except UnicodeEncodeError:
            print(
                f"EN/PT parity {en_code} to {pt_code}: "
                f"{actionable} actionable finding(s)."
            )

    return compared


def render_parity_markdown(report: ParityReport) -> str:
    lines = [
        f"# EN/PT Parity Report: {report.en_code} → {report.pt_code}",
        "",
        f"- EN snapshot: `{report.en_snapshot}`",
        f"- PT snapshot: `{report.pt_snapshot}`",
        "- English is canon. Gaps below should be reviewed by Course Designers.",
        "",
        "## Summary",
        "",
        "| Metric | EN | PT | Matched | Missing in PT |",
        "|---|---:|---:|---:|---:|",
        f"| Pages | {report.stats['pages_en']} | {report.stats['pages_pt']} | {report.stats['pages_matched']} | {report.stats['pages_missing_in_pt']} |",
        f"| Quizzes | {report.stats['quizzes_en']} | {report.stats['quizzes_pt']} | {report.stats['quizzes_matched']} | {report.stats['quizzes_missing_in_pt']} |",
        f"| Assignments | {report.stats['assignments_en']} | {report.stats['assignments_pt']} | {report.stats['assignments_matched']} | {report.stats['assignments_missing_in_pt']} |",
        f"| Question banks | {report.stats['banks_en']} | {report.stats['banks_pt']} | {report.stats['banks_matched']} | {report.stats['banks_missing_in_pt']} |",
        "",
        f"Actionable findings: **{report.stats['actionable_findings']}** "
        f"(high={report.stats['high_findings']}, medium={report.stats['medium_findings']}, low={report.stats['low_findings']})",
        "",
    ]

    by_cat = defaultdict(list)
    for finding in report.findings:
        if finding.severity == "info":
            continue
        by_cat[finding.category].append(finding)

    for category in ("pages", "quizzes", "assignments", "question_banks"):
        items = by_cat.get(category, [])
        lines.append(f"## {category.replace('_', ' ').title()}")
        lines.append("")
        if not items:
            lines.append("No actionable gaps.")
            lines.append("")
            continue
        for finding in sorted(items, key=lambda f: (f.severity, f.en_title or f.pt_title)):
            en = finding.en_title or "—"
            pt = finding.pt_title or "—"
            lines.append(
                f"- **[{finding.severity.upper()}]** EN `{en}` | PT `{pt}` — {finding.message}"
            )
        lines.append("")

    info_items = [f for f in report.findings if f.severity == "info"]
    lines.append("## Matched pairs (info)")
    lines.append("")
    lines.append(f"{len(info_items)} matched pairs found.")
    lines.append("")
    return "\n".join(lines)
