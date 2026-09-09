import os
from collections import defaultdict
from urllib.parse import unquote, urlparse

from canvas_exporter import (
    get_course_audit_events,
    get_course_files,
    get_course_folders,
    get_discussion_topics,
)
from page_attributor import (
    _load_snapshot_boundary,
    _parse_canvas_datetime,
    attribute_page_changes,
)


UNAVAILABLE_REASONS = {
    "manifest": (
        "The Canvas Modules API and IMSCC manifest do not expose the user who "
        "last edited module structure."
    ),
    "assignments": (
        "The Canvas Assignments API and IMSCC export expose modification data "
        "but not the responsible editor."
    ),
    "quizzes_banks": (
        "The Canvas quiz and question-bank APIs and IMSCC export do not expose "
        "the responsible editor."
    ),
    "course_settings": (
        "This settings artifact has no editor identity in the standard Canvas "
        "API or IMSCC export."
    ),
    "rubrics": (
        "The Canvas Rubrics API and IMSCC export do not expose the user who "
        "last edited a rubric definition."
    ),
    "discussions": (
        "The Canvas Discussions API exposes a topic creator but not the user "
        "who last edited an existing topic."
    ),
    "files_media": (
        "No matching Canvas file with reliable editor metadata was found."
    ),
    "other": (
        "Neither the standard Canvas API nor the IMSCC export exposes an editor "
        "for this artifact."
    ),
}

COURSE_AUDIT_FILES = {
    "course_settings/course_settings.xml",
    "course_settings/context.xml",
}


def _safe_profile_url(value):
    if not value:
        return None
    parsed = urlparse(str(value))
    return str(value) if parsed.scheme in {"http", "https"} else None


def _actor_from_user(user, changed_at=None):
    if not isinstance(user, dict):
        return None

    name = (
        user.get("display_name")
        or user.get("name")
        or user.get("short_name")
        or user.get("sortable_name")
    )
    if not name:
        return None

    return {
        "user_id": user.get("id"),
        "name": name,
        "profile_url": _safe_profile_url(user.get("html_url")),
        "changed_at": changed_at,
        "revision_id": None,
    }


def _unavailable_attribution(category, window_start, window_end, reason=None):
    return {
        "status": "unavailable",
        "source": "canvas_api_and_imscc",
        "source_label": "Attribution status",
        "window_start": window_start.isoformat() if window_start else None,
        "window_end": window_end.isoformat() if window_end else None,
        "actors": [],
        "unattributed_revision_count": 0,
        "reason": reason or UNAVAILABLE_REASONS.get(category, UNAVAILABLE_REASONS["other"]),
    }


def _normalize_path(value):
    return unquote(str(value or "").replace("\\", "/").strip("/")).casefold()


def _relative_folder_path(folder):
    full_name = _normalize_path(folder.get("full_name"))
    if full_name == "course files":
        return ""
    prefix = "course files/"
    return full_name[len(prefix):] if full_name.startswith(prefix) else full_name


def _unique_records(records):
    unique = {}
    for record in records:
        key = record.get("id")
        if key is None:
            key = id(record)
        unique[str(key)] = record
    return list(unique.values())


def _build_file_indices(files, folders):
    folder_paths = {
        str(folder.get("id")): _relative_folder_path(folder)
        for folder in folders
        if folder.get("id") is not None
    }
    exact_paths = defaultdict(list)
    basenames = defaultdict(list)

    for file_record in files:
        name = file_record.get("display_name") or file_record.get("filename")
        if not name:
            continue
        normalized_name = _normalize_path(name)
        folder_path = folder_paths.get(str(file_record.get("folder_id")), "")
        relative_path = "/".join(part for part in (folder_path, normalized_name) if part)
        exact_paths[relative_path].append(file_record)
        basenames[os.path.basename(normalized_name)].append(file_record)

    return exact_paths, basenames


def _matching_file(item, exact_paths, basenames):
    relative_path = _normalize_path(item.get("file_path"))
    prefix = "web_resources/"
    if relative_path.startswith(prefix):
        relative_path = relative_path[len(prefix):]

    matches = _unique_records(exact_paths.get(relative_path, []))
    if len(matches) == 1:
        return matches[0], None
    if len(matches) > 1:
        return None, "Multiple Canvas files matched the IMSCC path."

    matches = _unique_records(basenames.get(os.path.basename(relative_path), []))
    if len(matches) == 1:
        return matches[0], None
    if len(matches) > 1:
        return None, "Multiple Canvas files shared this filename, so attribution was ambiguous."
    return None, "The IMSCC file could not be matched to a current Canvas file."


def _time_in_window(value, window_start, window_end):
    if not value or not window_start or not window_end:
        return False
    try:
        changed_at = _parse_canvas_datetime(value)
    except (TypeError, ValueError):
        return False
    return bool(changed_at and window_start < changed_at <= window_end)


def _attribute_file_items(
    items,
    canvas_course_id,
    window_start,
    window_end,
    file_fetcher,
    folder_fetcher,
):
    if not items:
        return

    try:
        files = file_fetcher(canvas_course_id)
        folders = folder_fetcher(canvas_course_id)
        exact_paths, basenames = _build_file_indices(files, folders)
    except Exception as error:
        reason = f"Canvas Files API lookup failed: {error}"
        for item in items:
            item["attribution"] = _unavailable_attribution(
                "files_media", window_start, window_end, reason
            )
        return

    for item in items:
        attribution = item["attribution"]
        if item.get("status") == "Deleted":
            attribution["reason"] = (
                "Deleted files cannot be matched reliably to current Canvas file metadata."
            )
            continue

        file_record, mismatch_reason = _matching_file(item, exact_paths, basenames)
        if not file_record:
            attribution["reason"] = mismatch_reason
            continue

        changed_at = file_record.get("modified_at") or file_record.get("updated_at")
        if not _time_in_window(changed_at, window_start, window_end):
            attribution["reason"] = (
                "Canvas file metadata did not place its latest content change inside "
                "the export comparison window."
            )
            continue

        actor = _actor_from_user(file_record.get("user"), changed_at)
        if not actor:
            attribution["reason"] = (
                "Canvas matched the file but did not return its uploader or last "
                "content editor."
            )
            continue

        attribution.update({
            "status": "attributed",
            "source": "canvas_files_api",
            "source_label": "Canvas file metadata",
            "verb": "Changed by",
            "actors": [actor],
            "canvas_file_id": file_record.get("id"),
            "reason": (
                "Canvas identifies this user as the file uploader or last content "
                "editor; full file revision history is not available."
            ),
        })


def _discussion_actor(topic):
    author = topic.get("author")
    if isinstance(author, dict):
        actor = _actor_from_user(author, topic.get("posted_at"))
        if actor:
            return actor

    creator_name = topic.get("user_name")
    if not creator_name:
        return None
    return {
        "user_id": None,
        "name": creator_name,
        "profile_url": None,
        "changed_at": topic.get("posted_at"),
        "revision_id": None,
    }


def _attribute_discussion_items(
    items,
    canvas_course_id,
    window_start,
    window_end,
    discussion_fetcher,
):
    if not items:
        return

    added_items = [item for item in items if item.get("status") == "Added"]
    if not added_items:
        return

    try:
        topics = discussion_fetcher(canvas_course_id)
    except Exception as error:
        reason = f"Canvas Discussions API lookup failed: {error}"
        for item in added_items:
            item["attribution"]["reason"] = reason
        return

    topics_by_title = defaultdict(list)
    for topic in topics:
        topics_by_title[str(topic.get("title", "")).strip().casefold()].append(topic)

    for item in added_items:
        title = str(item.get("file_title", "")).strip().casefold()
        matches = _unique_records(topics_by_title.get(title, []))
        attribution = item["attribution"]
        if len(matches) != 1:
            attribution["reason"] = (
                "The added discussion could not be matched uniquely to a current "
                "Canvas topic."
            )
            continue

        topic = matches[0]
        posted_at = topic.get("posted_at")
        if not _time_in_window(posted_at, window_start, window_end):
            attribution["reason"] = (
                "Canvas matched the discussion, but its creation time was outside "
                "the export comparison window."
            )
            continue

        actor = _discussion_actor(topic)
        if not actor:
            attribution["reason"] = (
                "Canvas matched the discussion but did not return its creator."
            )
            continue

        attribution.update({
            "status": "attributed",
            "source": "canvas_discussions_api",
            "source_label": "Canvas discussion metadata",
            "verb": "Created by",
            "actors": [actor],
            "canvas_discussion_id": topic.get("id"),
            "reason": (
                "Canvas exposes the creator of a new discussion topic but not a "
                "revision history for later edits."
            ),
        })


def _event_actor(event, users):
    user_id = event.get("links", {}).get("user")
    user = users.get(str(user_id)) if user_id is not None else None
    return _actor_from_user(user, event.get("created_at"))


def _attribute_course_setting_items(
    items,
    canvas_course_id,
    window_start,
    window_end,
    audit_fetcher,
):
    audit_items = [
        item for item in items
        if _normalize_path(item.get("file_path")) in COURSE_AUDIT_FILES
    ]
    if not audit_items or not window_start or not window_end:
        return

    try:
        audit = audit_fetcher(
            canvas_course_id,
            window_start.isoformat(),
            window_end.isoformat(),
        )
    except Exception as error:
        reason = f"Canvas Course Audit API lookup failed: {error}"
        for item in audit_items:
            item["attribution"]["reason"] = reason
        return

    actors = []
    seen = set()
    for event in audit.get("events", []):
        if event.get("event_type") != "updated":
            continue
        if not _time_in_window(event.get("created_at"), window_start, window_end):
            continue
        actor = _event_actor(event, audit.get("users", {}))
        if not actor:
            continue
        key = (actor.get("user_id"), actor.get("changed_at"))
        if key not in seen:
            seen.add(key)
            actors.append(actor)

    for item in audit_items:
        attribution = item["attribution"]
        if not actors:
            attribution["reason"] = (
                "No user-backed Canvas course update event matched the export "
                "comparison window."
            )
            continue
        attribution.update({
            "status": "attributed",
            "source": "canvas_course_audit_api",
            "source_label": "Canvas course audit log",
            "verb": "Changed by",
            "actors": actors,
            "reason": (
                "Canvas course audit events identify course-level settings editors; "
                "they do not cover every specialized settings object."
            ),
        })


def attribute_course_changes(
    course_data,
    canvas_course_id,
    previous_snapshot_dir,
    current_snapshot_dir,
    page_revision_fetcher=None,
    file_fetcher=get_course_files,
    folder_fetcher=get_course_folders,
    discussion_fetcher=get_discussion_topics,
    audit_fetcher=get_course_audit_events,
):
    """Adds the strongest standard-API attribution available to every diff item."""
    window_start, _ = _load_snapshot_boundary(previous_snapshot_dir, is_end=False)
    window_end, _ = _load_snapshot_boundary(current_snapshot_dir, is_end=True)

    all_items = []
    categories = course_data.get("categories", {})
    for category, items in categories.items():
        all_items.extend(items)
        if category == "pages":
            continue
        for item in items:
            item["attribution"] = _unavailable_attribution(
                category, window_start, window_end
            )

    if not canvas_course_id:
        reason = "The course has no usable Canvas course URL for API attribution."
        for item in all_items:
            item["attribution"] = _unavailable_attribution(
                "other", window_start, window_end, reason
            )
        stats = {
            "items_checked": len(all_items),
            "items_attributed": 0,
            "items_unavailable": len(all_items),
        }
        course_data["attribution_summary"] = stats
        return stats

    page_kwargs = {}
    if page_revision_fetcher is not None:
        page_kwargs["revision_fetcher"] = page_revision_fetcher
    attribute_page_changes(
        course_data,
        canvas_course_id,
        previous_snapshot_dir,
        current_snapshot_dir,
        **page_kwargs,
    )

    _attribute_file_items(
        categories.get("files_media", []),
        canvas_course_id,
        window_start,
        window_end,
        file_fetcher,
        folder_fetcher,
    )
    _attribute_discussion_items(
        categories.get("discussions", []),
        canvas_course_id,
        window_start,
        window_end,
        discussion_fetcher,
    )
    _attribute_course_setting_items(
        categories.get("course_settings", []),
        canvas_course_id,
        window_start,
        window_end,
        audit_fetcher,
    )

    attributed = sum(
        item.get("attribution", {}).get("status") == "attributed"
        for item in all_items
    )
    stats = {
        "items_checked": len(all_items),
        "items_attributed": attributed,
        "items_unavailable": len(all_items) - attributed,
    }
    course_data["attribution_summary"] = stats
    return stats
