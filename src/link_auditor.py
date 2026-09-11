"""
Detect Google Doc/Sheet links that students cannot reliably open.

Flag export-as-file links (docx/xlsx) instead of published web views:
  - docs.google.com/.../export?format=docx
  - docs.google.com/spreadsheets/.../export?format=xlsx

Published links (/pub, /pubhtml) are considered OK.
"""

from __future__ import annotations

import html as html_lib
import os
import re
from urllib.parse import parse_qs, unquote, urlparse


URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.I)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
TEXT_EXTENSIONS = {".html", ".xml", ".qti", ".txt", ".json"}


def normalize_url(url: str) -> str:
    cleaned = html_lib.unescape(url or "").strip()
    cleaned = cleaned.rstrip(").,;]}>\"'")
    return cleaned


def is_inaccessible_google_export(url: str) -> bool:
    """
    True when a Google Docs/Sheets/Drive URL forces a file download export
    (docx/xlsx) rather than a published student-facing view.
    """
    cleaned = normalize_url(url)
    if not cleaned:
        return False

    low = cleaned.lower()
    parsed = urlparse(cleaned)
    host = (parsed.netloc or "").lower()
    path = unquote(parsed.path or "").lower()
    query = {
        key.lower(): [value.lower() for value in values]
        for key, values in parse_qs(parsed.query).items()
    }

    if "docs.google.com" in host:
        formats = query.get("format", [])
        if "export" in path or "export?" in low:
            return any(fmt in {"docx", "xlsx"} for fmt in formats)
        return "format=docx" in low or "format=xlsx" in low

    if "drive.google.com" in host:
        # Direct file-download endpoints are also not published web docs.
        return "export=download" in low or ("uc" in path and "export" in low)

    return False


def describe_export_issue(url: str) -> str:
    low = normalize_url(url).lower()
    if "format=docx" in low:
        return "Google Doc export link (docx). Students need a published document link (/pub), not an export download."
    if "format=xlsx" in low:
        return "Google Sheet export link (xlsx). Students need a published workbook link (/pubhtml), not an export download."
    if "drive.google.com" in low and "export=download" in low:
        return "Google Drive direct download link. Prefer a published Docs/Sheets link students can open in the browser."
    return "Google export/download link that students may not be able to open. Use a published document/workbook link."


def _clean_title(raw: str) -> str:
    text = html_lib.unescape(re.sub(r"<[^>]+>", " ", raw or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _title_from_text(text: str) -> str:
    match = TITLE_RE.search(text or "")
    if not match:
        return ""
    return _clean_title(match.group(1))


def _title_near_url(text: str, url: str) -> str:
    """
    For module_meta / dense XML, prefer the nearest preceding <title>.
    """
    idx = (text or "").find(url)
    if idx < 0:
        # Try without &amp; vs & differences.
        idx = text.find(html_lib.escape(url, quote=True))
    if idx < 0:
        return ""

    window = text[max(0, idx - 2500):idx]
    titles = list(TITLE_RE.finditer(window))
    if not titles:
        return ""
    return _clean_title(titles[-1].group(1))


def resolve_canvas_display_title(snapshot_dir: str, relative_path: str, text: str, url: str) -> str:
    """
    Best-effort Canvas-visible title for the resource containing the link.
    """
    rel = (relative_path or "").replace("\\", "/")
    basename = os.path.basename(rel)
    parent = os.path.dirname(rel)

    # 1) Nearby title in the same file (modules / weblinks).
    nearby = _title_near_url(text, url)
    if nearby:
        return nearby

    # 2) File-level <title> (pages, syllabus, assessment_meta, assignment HTML).
    file_title = _title_from_text(text)
    if file_title and file_title.lower() not in {"untitled", "document"}:
        return file_title

    # 3) Sibling Canvas metadata in the same resource folder.
    if parent and snapshot_dir:
        for sibling in ("assessment_meta.xml", "assignment_settings.xml"):
            sibling_path = os.path.join(snapshot_dir, parent, sibling)
            if not os.path.isfile(sibling_path):
                continue
            try:
                with open(sibling_path, encoding="utf-8", errors="ignore") as handle:
                    sibling_title = _title_from_text(handle.read())
                if sibling_title:
                    return sibling_title
            except OSError:
                pass

        # Linked HTML body in the same folder.
        try:
            for name in os.listdir(os.path.join(snapshot_dir, parent)):
                if not name.endswith(".html"):
                    continue
                html_path = os.path.join(snapshot_dir, parent, name)
                try:
                    with open(html_path, encoding="utf-8", errors="ignore") as handle:
                        html_title = _title_from_text(handle.read(20000))
                    if html_title:
                        return html_title
                except OSError:
                    continue
        except OSError:
            pass

    # 4) Friendly fallbacks for known course-setting files.
    if basename == "module_meta.xml":
        return "Modules"
    if basename == "syllabus.html":
        return "Syllabus"
    if "wiki_content/" in rel:
        slug = os.path.splitext(basename)[0].replace("-", " ").strip()
        return slug.title() if slug else basename

    return basename


def find_inaccessible_google_exports(snapshot_dir: str) -> list:
    """
    Scan an extracted IMSCC snapshot for inaccessible Google export links.
    Returns dicts with url, file_path, relative_path, display_title, issue.
    """
    findings = []
    seen = set()
    if not snapshot_dir or not os.path.isdir(snapshot_dir):
        return findings

    for dirpath, _, filenames in os.walk(snapshot_dir):
        for filename in filenames:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in TEXT_EXTENSIONS and not filename.endswith(".xml.qti"):
                continue
            path = os.path.join(dirpath, filename)
            try:
                with open(path, encoding="utf-8", errors="ignore") as handle:
                    text = handle.read()
            except OSError:
                continue

            for match in URL_RE.finditer(text):
                url = normalize_url(match.group(0))
                if not is_inaccessible_google_export(url):
                    continue
                rel = os.path.relpath(path, snapshot_dir).replace("\\", "/")
                key = (url, rel)
                if key in seen:
                    continue
                seen.add(key)
                findings.append(
                    {
                        "url": url,
                        "file_path": path,
                        "relative_path": rel,
                        "display_title": resolve_canvas_display_title(
                            snapshot_dir, rel, text, url
                        ),
                        "issue": describe_export_issue(url),
                    }
                )

    findings.sort(
        key=lambda item: (
            (item.get("display_title") or "").lower(),
            item["relative_path"],
            item["url"],
        )
    )
    return findings
