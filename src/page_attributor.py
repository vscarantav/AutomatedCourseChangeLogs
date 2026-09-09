import datetime
import json
import os
from urllib.parse import unquote, urlparse

from canvas_exporter import get_page_revisions


def course_id_from_url(course_url):
    """Extracts the Canvas course ID from a configured course URL."""
    if not course_url:
        return None

    parts = [part for part in urlparse(course_url).path.split("/") if part]
    try:
        courses_index = parts.index("courses")
        course_id = parts[courses_index + 1]
    except (ValueError, IndexError):
        return None

    return course_id if course_id.isdigit() else None


def _parse_canvas_datetime(value):
    if not value:
        return None
    parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)


def _snapshot_stem(snapshot_dir):
    directory_name = os.path.basename(os.path.normpath(snapshot_dir))
    if directory_name.endswith("_extracted"):
        return directory_name[:-len("_extracted")]
    return directory_name


def _load_snapshot_boundary(snapshot_dir, is_end):
    """Loads an exact export boundary, falling back to its date-based name."""
    stem = _snapshot_stem(snapshot_dir)
    course_dir = os.path.dirname(os.path.normpath(snapshot_dir))
    metadata_path = os.path.join(course_dir, f"{stem}.metadata.json")

    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, "r", encoding="utf-8") as metadata_file:
                metadata = json.load(metadata_file)
            boundary = _parse_canvas_datetime(metadata.get("export_created_at"))
            if boundary:
                return boundary, "export_metadata"
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass

    try:
        snapshot_date = datetime.date.fromisoformat(stem)
    except ValueError:
        return None, "unavailable"

    boundary_time = datetime.time.max if is_end else datetime.time.min
    boundary = datetime.datetime.combine(
        snapshot_date,
        boundary_time,
        tzinfo=datetime.timezone.utc,
    )
    return boundary, "date_fallback"


def _page_url_from_file_path(file_path):
    normalized = file_path.replace("\\", "/")
    filename = normalized.rsplit("/", 1)[-1]
    page_url, extension = os.path.splitext(filename)
    if extension.lower() != ".html":
        return None
    return unquote(page_url)


def _actor_from_revision(revision):
    editor = revision.get("edited_by")
    if not editor:
        return None

    name = (
        editor.get("display_name")
        or editor.get("name")
        or editor.get("short_name")
        or f"Canvas user {editor.get('id', 'unknown')}"
    )
    profile_url = editor.get("html_url")
    if profile_url and urlparse(profile_url).scheme not in ("http", "https"):
        profile_url = None

    return {
        "user_id": editor.get("id"),
        "name": name,
        "profile_url": profile_url,
        "changed_at": revision.get("updated_at"),
        "revision_id": revision.get("revision_id"),
    }


def attribute_page_changes(
    course_data,
    canvas_course_id,
    previous_snapshot_dir,
    current_snapshot_dir,
    revision_fetcher=get_page_revisions,
):
    """Adds Canvas page-revision attribution to page diff items in place."""
    page_items = course_data.get("categories", {}).get("pages", [])
    if not page_items:
        return {"pages_checked": 0, "pages_attributed": 0, "pages_unavailable": 0}

    window_start, start_source = _load_snapshot_boundary(
        previous_snapshot_dir,
        is_end=False,
    )
    window_end, end_source = _load_snapshot_boundary(
        current_snapshot_dir,
        is_end=True,
    )
    window_precision = (
        "exact"
        if start_source == end_source == "export_metadata"
        else "date_fallback"
    )
    stats = {
        "pages_checked": 0,
        "pages_attributed": 0,
        "pages_unavailable": 0,
    }

    for item in page_items:
        stats["pages_checked"] += 1
        page_url = _page_url_from_file_path(item.get("file_path", ""))
        attribution = {
            "status": "unavailable",
            "source": "canvas_page_revisions",
            "source_label": "Canvas page history",
            "verb": "Changed by",
            "page_url": page_url,
            "window_start": window_start.isoformat() if window_start else None,
            "window_end": window_end.isoformat() if window_end else None,
            "window_precision": window_precision,
            "revision_count": 0,
            "unattributed_revision_count": 0,
            "actors": [],
        }
        item["attribution"] = attribution

        if item.get("status") == "Deleted":
            attribution["reason"] = (
                "Deleted pages are no longer available through the Page Revisions API."
            )
            stats["pages_unavailable"] += 1
            continue

        if not page_url:
            attribution["reason"] = "The IMSCC page URL could not be determined."
            stats["pages_unavailable"] += 1
            continue

        if not window_start or not window_end or window_end <= window_start:
            attribution["reason"] = "The export comparison window is unavailable."
            stats["pages_unavailable"] += 1
            continue

        try:
            revisions = revision_fetcher(canvas_course_id, page_url)
            matching_revisions = []
            for revision in revisions:
                try:
                    revision_time = _parse_canvas_datetime(revision.get("updated_at"))
                except (ValueError, TypeError):
                    continue
                if revision_time and window_start < revision_time <= window_end:
                    matching_revisions.append(revision)
        except Exception as error:
            attribution["status"] = "error"
            attribution["reason"] = f"Canvas revision lookup failed: {error}"
            stats["pages_unavailable"] += 1
            continue

        actors = []
        seen_events = set()
        unattributed_count = 0
        for revision in sorted(
            matching_revisions,
            key=lambda value: value.get("updated_at", ""),
        ):
            actor = _actor_from_revision(revision)
            if not actor:
                unattributed_count += 1
                continue
            event_key = (
                actor.get("user_id"),
                actor.get("changed_at"),
                actor.get("revision_id"),
            )
            if event_key not in seen_events:
                seen_events.add(event_key)
                actors.append(actor)

        attribution["revision_count"] = len(matching_revisions)
        attribution["unattributed_revision_count"] = unattributed_count
        attribution["actors"] = actors

        if actors:
            attribution["status"] = "attributed"
            stats["pages_attributed"] += 1
        elif matching_revisions:
            attribution["reason"] = (
                "Canvas recorded matching revisions without an editor, usually "
                "because they came from an import or system process."
            )
            stats["pages_unavailable"] += 1
        else:
            attribution["reason"] = "No Canvas page revision matched the export window."
            stats["pages_unavailable"] += 1

    course_data["page_attribution_summary"] = stats
    return stats
