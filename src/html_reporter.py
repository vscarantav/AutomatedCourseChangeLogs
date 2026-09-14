import html
import json
from datetime import datetime
from urllib.parse import urlparse


def safe_http_url(value):
    if not value:
        return None

    candidate = str(value).strip()
    parsed = urlparse(candidate)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    return html.escape(candidate, quote=True)


def format_display_date(value):
    """Format YYYY-MM-DD dates as 'Sep 11, 2026'."""
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    try:
        return (
            datetime.strptime(text[:10], "%Y-%m-%d")
            .strftime("%b %d, %Y")
            .replace(" 0", " ")
        )
    except ValueError:
        return text


def generate_course_context_html(course):
    course_name = html.escape(str(course.get("course_name", "Unknown course")))
    course_url = safe_http_url(course.get("course_url"))

    if course_url:
        course_title = (
            f"<a class='course-live-link' href='{course_url}' target='_blank' "
            "rel='noopener noreferrer' onclick='event.stopPropagation()' "
            "title='Open live course in Canvas'>"
            f"{course_name} <span aria-hidden='true'>&#8599;</span></a>"
        )
    else:
        course_title = f"<span class='course-name'>{course_name}</span>"

    comparison = course.get("comparison_period") or {}
    previous_date = format_display_date(comparison.get("previous_date"))
    current_date = format_display_date(comparison.get("current_date"))
    comparison_html = ""
    if previous_date and current_date:
        previous_date = html.escape(previous_date)
        current_date = html.escape(current_date)
        comparison_html = (
            "<span class='comparison-period'>"
            f"Compared today's Canvas version ({current_date}) with snapshot "
            f"from {previous_date}</span>"
        )

    return (
        "<div class='course-context'>"
        f"<div class='course-title-row'>{course_title}</div>"
        f"{comparison_html}</div>"
    )


def link_issue_label(issue):
    """Prefer Canvas-visible title; fall back to relative path."""
    title = (issue or {}).get("display_title") or ""
    title = str(title).strip()
    if title:
        return title
    return (issue or {}).get("relative_path") or "Unknown resource"


def generate_impact_badge_html(impact):
    if impact not in {"Low", "Medium", "High"}:
        return ""
    impact_color = {"Low": "#4caf50", "Medium": "#ffb74d", "High": "#e57373"}[impact]
    return (
        f"<span class='impact-badge' style='background: {impact_color}22; "
        f"color: {impact_color}; border: 1px solid {impact_color};'>"
        f"Impact: {impact}</span>"
    )


def generate_en_pt_parity_html(parity, compact=False):
    """Render a compact EN-canon vs PT parity block for designers."""
    if not parity:
        return ""

    stats = parity.get("stats") or {}
    actionable = int(stats.get("actionable_findings") or 0)
    if actionable <= 0 and not parity.get("highlights"):
        return ""

    en_code = html.escape(str(parity.get("en_code", "")))
    pt_code = html.escape(str(parity.get("pt_code", "")))
    high = int(stats.get("high_findings") or 0)
    medium = int(stats.get("medium_findings") or 0)
    pages_missing = int(stats.get("pages_missing_in_pt") or 0)
    quizzes_missing = int(stats.get("quizzes_missing_in_pt") or 0)
    assignments_missing = int(stats.get("assignments_missing_in_pt") or 0)
    banks_missing = int(stats.get("banks_missing_in_pt") or 0)

    rows = []
    for item in parity.get("highlights") or []:
        severity = html.escape(str(item.get("severity", "")).upper())
        category = html.escape(str(item.get("category", "")).replace("_", " "))
        en_title = html.escape(item.get("en_title") or "—")
        pt_title = html.escape(item.get("pt_title") or "—")
        message = html.escape(item.get("message") or "")
        rows.append(
            "<li style='margin-bottom: 0.45rem;'>"
            f"<strong>[{severity}]</strong> {category}: "
            f"EN <code>{en_title}</code> → PT <code>{pt_title}</code> — {message}"
            "</li>"
        )

    omitted = int(parity.get("highlights_omitted") or 0)
    if omitted:
        rows.append(f"<li><em>+ {omitted} more gap(s) in the full parity details</em></li>")

    list_html = ""
    if rows:
        list_html = (
            "<ul style='margin: 0.75rem 0 0; padding-left: 1.25rem;'>"
            + "".join(rows)
            + "</ul>"
        )

    summary = (
        f"{actionable} gap(s) where Portuguese may not reflect English "
        f"(high={high}, medium={medium}). "
        f"Missing in PT — pages: {pages_missing}, quizzes: {quizzes_missing}, "
        f"assignments: {assignments_missing}, question banks: {banks_missing}."
    )

    margin = "margin-bottom: 1rem;" if compact else "margin-bottom: 1.5rem;"
    return f"""
    <div class="parity-block" style="background: rgba(100, 181, 246, 0.08); border-left: 4px solid #64b5f6; padding: 1rem; {margin} border-radius: 4px;">
        <strong style="color: #64b5f6;">EN/PT Parity ({en_code} → {pt_code}):</strong>
        English is canon. Course Designers should align PT with EN when gaps appear.
        <p style="margin: 0.5rem 0 0; color: var(--text-muted); font-size: 0.9rem;">{summary}</p>
        {list_html}
    </div>
    """


def generate_attribution_html(item):
    attribution = item.get("attribution")
    if not attribution:
        return "", ""

    actors = attribution.get("actors", [])
    unique_names = list(dict.fromkeys(
        actor.get("name", "Unknown user") for actor in actors
    ))
    verb = attribution.get("verb", "Changed by")

    if len(unique_names) == 1:
        badge_text = f"{verb} {unique_names[0]}"
        badge_class = "attribution-known"
    elif len(unique_names) > 1:
        badge_text = f"{verb} {len(unique_names)} people"
        badge_class = "attribution-known"
    elif attribution.get("unattributed_revision_count", 0):
        badge_text = "Canvas/system change"
        badge_class = "attribution-system"
    else:
        badge_text = "Editor Unavailable"
        badge_class = "attribution-unavailable"

    badge_html = (
        f"<span class='label {badge_class}'>"
        f"{html.escape(badge_text)}</span>"
    )

    # Skip the generic "Attribution status / no editor exposed" explainer.
    if (
        attribution.get("status") == "unavailable"
        and not actors
        and not attribution.get("unattributed_revision_count")
    ):
        return badge_html, ""

    default_source_labels = {
        "canvas_page_revisions": "Canvas page history",
        "canvas_files_api": "Canvas file metadata",
        "canvas_discussions_api": "Canvas discussion metadata",
        "canvas_course_audit_api": "Canvas course audit log",
    }
    source_label = attribution.get("source_label") or default_source_labels.get(
        attribution.get("source", "canvas_page_revisions"),
        "Attribution details",
    )
    source_label = html.escape(str(source_label))
    details = [f"<div class='attribution-details'><strong>{source_label}</strong>"]
    if actors:
        details.append("<ul>")
        for actor in actors:
            name = html.escape(str(actor.get("name", "Unknown user")))
            changed_at = html.escape(str(actor.get("changed_at", "Unknown time")))
            profile_url = actor.get("profile_url")
            if profile_url:
                safe_url = html.escape(str(profile_url), quote=True)
                name = (
                    f"<a href='{safe_url}' target='_blank' rel='noopener noreferrer'>"
                    f"{name}</a>"
                )
            details.append(f"<li>{name} — {changed_at}</li>")
        details.append("</ul>")

    unattributed_count = attribution.get("unattributed_revision_count", 0)
    if unattributed_count:
        details.append(
            f"<p>{unattributed_count} matching revision(s) had no Canvas user "
            "and may have been produced by an import or system process.</p>"
        )

    reason = attribution.get("reason")
    if reason:
        details.append(f"<p>{html.escape(str(reason))}</p>")

    if attribution.get("window_precision") == "date_fallback":
        details.append(
            "<p><em>Attribution used date-only snapshot boundaries because exact "
            "export metadata was unavailable.</em></p>"
        )

    details.append("</div>")
    return badge_html, "".join(details)

def generate_file_item_html(item):
    labels_html = "".join([f"<span class='label label-{l.lower().replace('/', '-').replace(' ', '-')}'>{l}</span>" for l in item["labels"]])
    attribution_badge, attribution_details = generate_attribution_html(item)
    display_title = html.escape(item.get('file_title', item['file_path']))
    safe_summary = html.escape(item.get('ai_summary', ''))
    
    out = f"""
    <div class="file-item">
        <div class="file-header" onclick="toggleFile(this)" style="cursor: pointer; display: flex; justify-content: space-between; align-items: center; padding: 0.5rem; background: rgba(255,255,255,0.02); border-radius: 4px;">
            <div style="display: flex; align-items: center; gap: 0.8rem; flex-wrap: wrap;">
                <span class="status status-{item['status'].split(' ')[0].lower()}">{item['status']}</span>
                <span class="file-path">{display_title}</span>
                {labels_html}
                {attribution_badge}
            </div>
            <span class="file-icon" style="color: var(--text-muted); font-size: 0.8rem;">▼</span>
        </div>
    """
    
    if item["diff_lines"] or attribution_details:
        ai_html = ""
        if safe_summary:
            ai_html = f"<div class='ai-summary' style='background: rgba(187, 134, 252, 0.1); border-left: 3px solid var(--accent); padding: 0.8rem; margin-top: 0.5rem; font-size: 0.9rem; border-radius: 4px;'><strong>AI Summary:</strong> {safe_summary}</div>"
        
        out += f"<div class='diff-views-container' style='display: none; padding-top: 1rem;'>{attribution_details}{ai_html}"
        if item["diff_lines"]:
            out += "<pre class='diff-block'>"
            for line in item["diff_lines"]:
                line_safe = line.replace('<', '&lt;').replace('>', '&gt;')
                if line.startswith('+++') or line.startswith('---'):
                    out += f"<div class='diff-meta'>{line_safe}</div>"
                elif line.startswith('+'):
                    out += f"<div class='diff-add'>{line_safe}</div>"
                elif line.startswith('-'):
                    out += f"<div class='diff-remove'>{line_safe}</div>"
                elif line.startswith('@@'):
                    out += f"<div class='diff-chunk'>{line_safe}</div>"
                else:
                    out += f"<div class='diff-context'>{line_safe}</div>"
            out += "</pre>"
        out += "</div>"
        
    out += "</div>"
    return out

def generate_html_report(year_week: str, courses_data: list, default_designer: str = "all"):
    designers = sorted(list(set(c.get("designer", "Unknown") for c in courses_data if c.get("designer"))))
    
    total_courses = len(courses_data)
    courses_with_changes = sum(1 for c in courses_data if c.get("has_changes", False))
    courses_with_link_issues = sum(
        1 for c in courses_data if c.get("inaccessible_google_exports")
    )
    total_link_issues = sum(
        len(c.get("inaccessible_google_exports") or []) for c in courses_data
    )
    
    total_changes_by_category = {
        "manifest": 0, "assignments": 0, "pages": 0, "quizzes_banks": 0,
        "course_settings": 0, "rubrics": 0, "discussions": 0, "files_media": 0, "other": 0
    }
    
    for c in courses_data:
        cats = c.get("categories", {})
        for k, v in cats.items():
            if k in total_changes_by_category:
                total_changes_by_category[k] += len(v)
                
    category_titles = {
        "manifest": "Modules page",
        "assignments": "Assignments",
        "pages": "Pages",
        "quizzes_banks": "Quizzes & Question Banks",
        "course_settings": "Course Settings",
        "rubrics": "Rubrics",
        "discussions": "Discussions",
        "files_media": "Files & Media",
        "other": "Other Files"
    }

    # -----------------------------------------
    # TAB: RAW LOGS BY COURSE
    # -----------------------------------------
    impact_order = {"High": 0, "Medium": 1, "Low": 2}
    courses_by_impact = sorted(
        courses_data,
        key=lambda c: (
            impact_order.get(c.get("course_ai_impact"), 3),
            0 if c.get("has_changes") else 1,
            str(c.get("course_name", "")),
        ),
    )

    logs_course_html = ""
    for c in courses_by_impact:
        designer = c.get("designer", "Unknown")
        course_name = c['course_name']
        course_context_html = generate_course_context_html(c)
        
        has_changes_str = 'true' if c.get("has_changes", False) else 'false'
        has_link_issues = 'true' if c.get("inaccessible_google_exports") else 'false'
        impact_badge = generate_impact_badge_html(c.get("course_ai_impact", ""))
        change_total = sum(len(items) for items in c.get("categories", {}).values())
        change_count_html = (
            f"<span class='course-change-count'>{change_total} change"
            f"{'' if change_total == 1 else 's'}</span>"
        )
        link_count = len(c.get("inaccessible_google_exports") or [])
        link_badge = ""
        if link_count:
            link_badge = (
                f"<span class='link-issue-badge'>{link_count} Google export link"
                f"{'' if link_count == 1 else 's'}</span>"
            )
        logs_course_html += f"""
        <div class='course-section accordion' data-designer='{designer}' data-course='{course_name}' data-has-changes='{has_changes_str}' data-link-issues='{has_link_issues}'>
            <div class="accordion-header course-accordion-header" onclick="toggleAccordion(this)">
                {course_context_html}
                <div class="course-header-meta">{change_count_html}{link_badge}{impact_badge}<span class="icon">▼</span></div>
            </div>
            <div class="accordion-content">
        """
        
        streak = c.get("zero_changes_streak", 0)
        if streak >= 5:
            logs_course_html += f"""
            <div style="background: rgba(255, 152, 0, 0.1); border-left: 4px solid #ff9800; padding: 1rem; margin-bottom: 1.5rem; border-radius: 4px;">
                <strong style="color: #ff9800;">⚠️ Maintenance Recommendation:</strong> This course has had zero changes for {streak} consecutive weeks. Course Designers are recommended to check standard pages and resources to ensure course material is being actively maintained.
            </div>
            """
        elif streak > 0:
            logs_course_html += f"<p style='color: var(--text-muted); font-size: 0.9rem; margin-top: -10px;'><em>No changes for {streak} consecutive weeks.</em></p>"

        link_issues = c.get("inaccessible_google_exports") or []
        if link_issues:
            logs_course_html += """
            <div style="background: rgba(229, 115, 115, 0.1); border-left: 4px solid #e57373; padding: 1rem; margin-bottom: 1.5rem; border-radius: 4px;">
                <strong style="color: #e57373;">Student Access Issue:</strong>
                Google Doc/Sheet links that export as downloadable files (docx/xlsx) instead of published web documents.
                Students typically cannot open these. Replace them with published links (<code>/pub</code> or <code>/pubhtml</code>).
                <ul style="margin: 0.75rem 0 0; padding-left: 1.25rem;">
            """
            for issue in link_issues[:25]:
                safe_url = html.escape(issue.get("url", ""), quote=True)
                safe_title = html.escape(link_issue_label(issue))
                safe_issue = html.escape(issue.get("issue", ""))
                logs_course_html += (
                    f"<li style='margin-bottom: 0.4rem;'><strong>{safe_title}</strong><br>"
                    f"<a href='{safe_url}' target='_blank' rel='noopener noreferrer' "
                    f"style='color: var(--accent); word-break: break-all;'>{safe_url}</a><br>"
                    f"<span style='color: var(--text-muted); font-size: 0.85rem;'>{safe_issue}</span></li>"
                )
            if len(link_issues) > 25:
                logs_course_html += (
                    f"<li><em>+ {len(link_issues) - 25} more link(s)</em></li>"
                )
            logs_course_html += "</ul></div>"

        if c.get("is_new"):
            logs_course_html += "<p><em>No previous export found. All files considered new.</em></p></div></div>"
            continue
            
        if not c.get("has_changes"):
            logs_course_html += "<p><em>No meaningful content changes detected this week.</em></p></div></div>"
            continue
            
        for cat_key, cat_title in category_titles.items():
            items = c["categories"].get(cat_key, [])
            if not items:
                continue

            category_ai_summary = (c.get("category_ai_summaries") or {}).get(cat_key, "")
            category_ai_html = ""
            if category_ai_summary:
                category_ai_html = (
                    "<div class='ai-summary' style='background: rgba(187, 134, 252, 0.1); "
                    "border-left: 3px solid var(--accent); padding: 0.8rem; margin-bottom: 1rem; "
                    "font-size: 0.9rem; border-radius: 4px;'>"
                    f"<strong>AI Summary:</strong> {category_ai_summary}</div>"
                )
                
            logs_course_html += f"""
            <div class="accordion" data-category="{cat_key}">
                <div class="accordion-header cat-accordion-header" onclick="toggleAccordion(this)">
                    <span>{cat_title} ({len(items)} changes)</span>
                    <span class="icon">▼</span>
                </div>
                <div class="accordion-content">
                    {category_ai_html}
            """
            for item in items:
                logs_course_html += generate_file_item_html(item)
            logs_course_html += "</div></div>"
            
        logs_course_html += "</div></div>"

    # -----------------------------------------
    # CSS & JS
    # -----------------------------------------
    css = """
    :root {
        --bg: #121212; --surface: #1e1e1e; --surface-hover: #2a2a2a;
        --text: #e0e0e0; --text-muted: #9e9e9e; --accent: #bb86fc;
        --add-bg: rgba(76, 175, 80, 0.15); --add-text: #81c784;
        --rem-bg: rgba(244, 67, 54, 0.15); --rem-text: #e57373;
        --border: #333;
    }
    body {
        font-family: 'Inter', -apple-system, sans-serif;
        background-color: var(--bg); color: var(--text);
        margin: 0; padding: 0;
    }
    .nav {
        background: rgba(30, 30, 30, 0.8); backdrop-filter: blur(10px);
        position: sticky; top: 0; z-index: 100; padding: 1rem 2rem;
        border-bottom: 1px solid var(--border);
        display: flex; gap: 2rem; align-items: center; justify-content: space-between;
    }
    .nav-left { display: flex; gap: 2rem; align-items: center; }
    .nav h1 { margin: 0; font-size: 1.2rem; color: var(--accent); }
    .nav-links button, .nav-actions button {
        background: none; border: none; color: var(--text-muted);
        font-size: 1rem; cursor: pointer; padding: 0.5rem 1rem;
        border-radius: 4px; transition: 0.2s;
    }
    .nav-links button:hover, .nav-actions button:hover { background: var(--surface-hover); color: var(--text); }
    .nav-links button.active { color: var(--accent); background: rgba(187, 134, 252, 0.1); }
    
    .container { padding: 2rem; max-width: 1200px; margin: 0 auto; }
    .tab-content { display: none; }
    .tab-content.active { display: block; animation: fadeIn 0.3s; }
    
    @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
    
    .metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
    .metric-card {
        background: var(--surface); padding: 1.5rem; border-radius: 12px;
        border: 1px solid var(--border); text-align: center;
    }
    .metric-value { font-size: 2rem; font-weight: bold; color: var(--accent); }
    .metric-label { color: var(--text-muted); font-size: 0.9rem; margin-top: 0.5rem; }
    
    .category-stats { background: var(--surface); padding: 1.5rem; border-radius: 12px; border: 1px solid var(--border); }
    .cat-row { display: flex; justify-content: space-between; padding: 0.8rem 0.5rem; border-bottom: 1px solid var(--border); border-radius: 4px; }
    .cat-row:last-child { border-bottom: none; }
    
    .accordion { margin-bottom: 1rem; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; background: var(--surface); }
    .accordion-header {
        padding: 1rem; cursor: pointer; display: flex; justify-content: space-between;
        align-items: center; gap: 1rem;
        background: rgba(255,255,255,0.02); transition: 0.2s; font-weight: 600;
    }
    .course-accordion-header { background: rgba(187, 134, 252, 0.05); font-size: 1.1rem; }
    .course-header-meta { display: flex; align-items: center; gap: 0.75rem; flex-shrink: 0; }
    .course-change-count { color: var(--text-muted); font-size: 0.9rem; font-weight: 600; white-space: nowrap; }
    .link-issue-badge { background: rgba(229, 115, 115, 0.15); color: #e57373; border: 1px solid #e57373; padding: 0.3rem 0.8rem; border-radius: 20px; font-weight: bold; font-size: 0.8rem; white-space: nowrap; }
    .parity-badge { background: rgba(100, 181, 246, 0.15); color: #64b5f6; border: 1px solid #64b5f6; padding: 0.3rem 0.8rem; border-radius: 20px; font-weight: bold; font-size: 0.8rem; white-space: nowrap; }
    .impact-badge { padding: 0.3rem 0.8rem; border-radius: 20px; font-weight: bold; font-size: 0.85rem; white-space: nowrap; }
    .course-context { min-width: 0; }
    .course-title-row { line-height: 1.3; }
    .course-live-link { color: var(--accent); text-decoration: none; }
    .course-live-link:hover { text-decoration: underline; }
    .comparison-period { display: block; margin-top: 0.25rem; color: var(--text-muted); font-size: 0.78rem; font-weight: 400; }
    .cat-accordion-header { background: rgba(255, 255, 255, 0.02); }
    .accordion-header:hover { background: var(--surface-hover); }
    .accordion-content { display: none; padding: 1rem; border-top: 1px solid var(--border); }
    
    .course-insight { background: var(--surface); padding: 1.5rem; border-radius: 12px; border: 1px solid var(--border); margin-bottom: 1rem; position: relative; cursor: pointer; transition: 0.2s; }
    .course-insight:hover { border-color: var(--accent); background: var(--surface-hover); }
    
    .file-item { margin-bottom: 1.5rem; }
    .status { padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.8rem; font-weight: bold; }
    .status-modified { background: #ffb74d; color: #000; }
    .status-added { background: #81c784; color: #000; }
    .status-deleted { background: #e57373; color: #000; }
    .label { font-size: 0.75rem; padding: 0.2rem 0.5rem; border-radius: 12px; border: 1px solid var(--text-muted); color: var(--text-muted); background: rgba(255,255,255,0.05); }
    .attribution-known { border-color: #64b5f6; color: #90caf9; background: rgba(33, 150, 243, 0.12); }
    .attribution-system { border-color: #ffb74d; color: #ffcc80; background: rgba(255, 152, 0, 0.12); }
    .attribution-unavailable { border-color: #757575; color: #bdbdbd; }
    .attribution-details { background: rgba(33, 150, 243, 0.08); border-left: 3px solid #64b5f6; padding: 0.8rem; margin-bottom: 0.8rem; border-radius: 4px; font-size: 0.9rem; }
    .attribution-details ul { margin: 0.5rem 0 0; padding-left: 1.5rem; }
    .attribution-details p { margin: 0.5rem 0 0; color: var(--text-muted); }
    
    .diff-block {
        background: #000; padding: 1rem; border-radius: 6px; overflow-x: auto;
        font-family: monospace; font-size: 0.85rem; line-height: 1.4; margin: 0;
    }
    .diff-add { background: var(--add-bg); color: var(--add-text); display: block; }
    .diff-remove { background: var(--rem-bg); color: var(--rem-text); display: block; }
    .diff-meta { color: #569cd6; font-weight: bold; }
    .diff-chunk { color: #4ec9b0; }
    .diff-context { color: #cccccc; }
    """
    
    js = """
    function switchTab(tabId, el) {
        document.querySelectorAll('.tab-content').forEach(e => e.classList.remove('active'));
        document.querySelectorAll('.nav-links button').forEach(e => e.classList.remove('active'));
        document.getElementById(tabId).classList.add('active');
        if (el) {
            el.classList.add('active');
        } else {
            document.querySelector(`button[onclick*="${tabId}"]`).classList.add('active');
        }
    }
    
    function toggleAccordion(header) {
        const content = header.nextElementSibling;
        const icon = header.querySelector('.icon');
        if (content.style.display === 'block') {
            content.style.display = 'none';
            if(icon) icon.textContent = '▼';
        } else {
            content.style.display = 'block';
            if(icon) icon.textContent = '▲';
        }
    }
    
    function toggleFile(header) {
        const content = header.nextElementSibling;
        if (!content || !content.classList.contains('diff-views-container')) return;
        
        const icon = header.querySelector('.file-icon');
        if (content.style.display === 'block') {
            content.style.display = 'none';
            if (icon) icon.textContent = '▼';
        } else {
            content.style.display = 'block';
            if (icon) icon.textContent = '▲';
        }
    }
    
    function openCourse(courseName) {
        switchTab('logs-course', null);
        document.querySelectorAll('#logs-course .course-section').forEach(acc => {
            const content = acc.querySelector('.accordion-content');
            const icon = acc.querySelector('.icon');
            if (acc.getAttribute('data-course') === courseName && acc.style.display !== 'none') {
                content.style.display = 'block';
                if(icon) icon.textContent = '▲';
                setTimeout(() => acc.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
            } else {
                content.style.display = 'none';
                if(icon) icon.textContent = '▼';
            }
        });
    }
    
    function filterDesigner(designer) {
        let scanned = 0;
        let changed = 0;
        let totalFiles = 0;
        const catTotals = {};
        
        document.querySelectorAll('.course-insight').forEach(el => {
            el.style.display = (designer === 'all' || el.getAttribute('data-designer') === designer) ? 'block' : 'none';
        });
        
        document.querySelectorAll('#logs-course .course-section').forEach(el => {
            if (designer === 'all' || el.getAttribute('data-designer') === designer) {
                el.style.display = 'block';
                scanned++;
                if (el.getAttribute('data-has-changes') === 'true') {
                    changed++;
                }
                el.querySelectorAll('[data-category]').forEach(cat => {
                    const catKey = cat.getAttribute('data-category');
                    const count = cat.querySelectorAll('.file-item').length;
                    catTotals[catKey] = (catTotals[catKey] || 0) + count;
                    totalFiles += count;
                });
            } else {
                el.style.display = 'none';
            }
        });
        
        const elScanned = document.getElementById('metric-scanned');
        if (elScanned) elScanned.textContent = scanned;
        const elChanged = document.getElementById('metric-changed');
        if (elChanged) elChanged.textContent = changed;
        const elModified = document.getElementById('metric-modified');
        if (elModified) elModified.textContent = totalFiles;
        
        document.querySelectorAll('.cat-row strong').forEach(el => {
            const catKey = el.id.replace('metric-cat-', '');
            el.textContent = catTotals[catKey] || 0;
        });
    }
    
    document.addEventListener('DOMContentLoaded', () => {
        const dFilter = document.getElementById('designerFilter');
        if (dFilter) {
            dFilter.value = '{default_designer}';
            filterDesigner('{default_designer}');
        }
    });
    """
    
    # -----------------------------------------
    # DASHBOARD HTML
    # -----------------------------------------
    dashboard_html = f"""
    <div class="metric-grid">
        <div class="metric-card">
            <div class="metric-value" id="metric-scanned">{{total_courses}}</div>
            <div class="metric-label">Courses Scanned</div>
        </div>
        <div class="metric-card">
            <div class="metric-value" id="metric-changed">{{courses_with_changes}}</div>
            <div class="metric-label">Courses w/ Changes</div>
        </div>
        <div class="metric-card">
            <div class="metric-value" id="metric-modified">{{sum(total_changes_by_category.values())}}</div>
            <div class="metric-label">Total Pages Modified</div>
        </div>
    </div>
    """
    
    insights_courses = [c for c in courses_data if c.get("has_changes") and c.get("course_ai_summary")]
    
    # Sort by impact: High -> Medium -> Low
    insights_courses.sort(key=lambda c: impact_order.get(c.get("course_ai_impact", "Medium"), 1))
    
    insights_html = ""
    for c in insights_courses:
        impact = c.get("course_ai_impact", "Medium")
        impact_badge = generate_impact_badge_html(impact)
        course_context_html = generate_course_context_html(c)
        
        insights_html += f"""
        <div class="course-insight" data-designer="{c.get('designer', 'Unknown')}" onclick="openCourse('{c['course_name']}')">
            <div style="margin-top: 0; color: var(--accent); width: 80%; font-size: 1.17rem; font-weight: 600;">{course_context_html}</div>
            <span style="position: absolute; top: 1.5rem; right: 1.5rem;">{impact_badge}</span>
            <p style="margin-bottom: 0; line-height: 1.6;">{c['course_ai_summary']}</p>
        </div>
        """
            
    if insights_html:
        dashboard_html += "<h2>Course Insights</h2><p style='color: var(--text-muted); font-size: 0.9rem;'>Click a course to jump directly to its raw logs.</p>" + insights_html

    link_issue_courses = [
        c for c in courses_data if c.get("inaccessible_google_exports")
    ]
    if link_issue_courses:
        dashboard_html += (
            "<h2 style='margin-top: 3rem;'>Google Export Link Issues</h2>"
            "<p style='color: var(--text-muted); font-size: 0.9rem;'>"
            f"{total_link_issues} inaccessible Google Doc/Sheet export link(s) across "
            f"{courses_with_link_issues} course(s). These download as docx/xlsx instead of "
            "published web documents, so students often cannot open them. "
            "Use published <code>/pub</code> or <code>/pubhtml</code> links.</p>"
        )
        for c in link_issue_courses:
            issues = c.get("inaccessible_google_exports") or []
            course_context_html = generate_course_context_html(c)
            dashboard_html += f"""
            <div class="course-insight" data-designer="{c.get('designer', 'Unknown')}" onclick="openCourse('{c['course_name']}')">
                <div style="margin-top: 0; color: var(--accent); width: 80%; font-size: 1.17rem; font-weight: 600;">{course_context_html}</div>
                <span class="link-issue-badge" style="position: absolute; top: 1.5rem; right: 1.5rem;">{len(issues)} link{'s' if len(issues) != 1 else ''}</span>
                <ul style="margin: 0.75rem 0 0; padding-left: 1.25rem;">
            """
            for issue in issues[:8]:
                safe_url = html.escape(issue.get("url", ""), quote=True)
                safe_title = html.escape(link_issue_label(issue))
                dashboard_html += (
                    f"<li style='margin-bottom: 0.35rem;'><strong>{safe_title}</strong> — "
                    f"<a href='{safe_url}' target='_blank' rel='noopener noreferrer' "
                    f"style='color: var(--accent); word-break: break-all;' "
                    f"onclick='event.stopPropagation()'>{safe_url}</a></li>"
                )
            if len(issues) > 8:
                dashboard_html += f"<li><em>+ {len(issues) - 8} more</em></li>"
            dashboard_html += "</ul></div>"

    # EN/PT parity temporarily disabled — re-enable with enrichment in main.py.
    parity_tab_html = ""
    parity_tab_button = ""
    parity_tab_panel = ""
    # parity_gap_courses = [
    #     c for c in courses_data
    #     if int(((c.get("en_pt_parity") or {}).get("stats") or {}).get("actionable_findings") or 0) > 0
    #     and not str(c.get("course_name", "")).endswith("-PT")
    # ]
    # if not parity_gap_courses:
    #     parity_gap_courses = [
    #         c for c in courses_data
    #         if int(((c.get("en_pt_parity") or {}).get("stats") or {}).get("actionable_findings") or 0) > 0
    #     ]
    #     seen_pairs = set()
    #     deduped = []
    #     for c in parity_gap_courses:
    #         en_code = (c.get("en_pt_parity") or {}).get("en_code")
    #         if en_code in seen_pairs:
    #             continue
    #         seen_pairs.add(en_code)
    #         deduped.append(c)
    #     parity_gap_courses = deduped
    #
    # if parity_gap_courses:
    #     parity_tab_html = (
    #         "<h2>EN/PT Parity Gaps</h2>"
    #         "<p style='color: var(--text-muted); font-size: 0.9rem;'>"
    #         "Course Designers should mirror EN pages, quizzes, assignments, "
    #         "and question/answer coverage in Portuguese.</p>"
    #     )
    #     for c in parity_gap_courses:
    #         parity = c.get("en_pt_parity") or {}
    #         course_context_html = generate_course_context_html(c)
    #         actionable = int((parity.get("stats") or {}).get("actionable_findings") or 0)
    #         parity_tab_html += f"""
    #         <div class="course-insight" data-designer="{c.get('designer', 'Unknown')}" onclick="openCourse('{c['course_name']}')">
    #             <div style="margin-top: 0; color: var(--accent); width: 75%; font-size: 1.17rem; font-weight: 600;">{course_context_html}</div>
    #             <span class="parity-badge" style="position: absolute; top: 1.5rem; right: 1.5rem;">{actionable} gap{'s' if actionable != 1 else ''}</span>
    #             {generate_en_pt_parity_html(parity, compact=True)}
    #         </div>
    #         """
    # else:
    #     parity_tab_html = (
    #         "<h2>EN/PT Parity Gaps</h2>"
    #         "<p style='color: var(--text-muted);'>No EN/PT parity gaps were detected for courses in this report.</p>"
    #     )
    # parity_tab_button = '<button onclick="switchTab(\'parity-tab\', this)">EN/PT Parity</button>'
    # parity_tab_panel = f'<div id="parity-tab" class="tab-content">{parity_tab_html}</div>'

    dashboard_html += """
    <h2 style='margin-top: 3rem;'>Changes by Category</h2>
    <div class="category-stats">
    """
    for k, title in category_titles.items():
        val = total_changes_by_category.get(k, 0)
        dashboard_html += f"<div class='cat-row'><span>{title}</span><strong id='metric-cat-{k}'>{val}</strong></div>"
    dashboard_html += "</div>"
    
    js = js.replace('{default_designer}', default_designer)

    report_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Course Change Logs - {year_week}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
    <style>{css}</style>
</head>
<body>
    <nav class="nav">
        <div class="nav-left">
            <h1>Canvas Change Logs</h1>
            <div class="nav-links">
                <button class="active" onclick="switchTab('dashboard', this)">Dashboard</button>
                <button onclick="switchTab('logs-course', this)">Raw Logs by Course</button>
                {parity_tab_button}
            </div>
        </div>
        <div class="nav-actions">
            <select id="designerFilter" onchange="filterDesigner(this.value)" style="padding: 0.5rem; background: var(--surface); color: var(--text); border: 1px solid var(--border); border-radius: 4px; cursor: pointer; outline: none;">
                <option value="all">Filter by Course Designer (All)</option>
                {"".join([f'<option value="{d}">{d}</option>' for d in designers])}
            </select>
        </div>
    </nav>
    <div class="container">
        <div id="dashboard" class="tab-content active">
            {dashboard_html}
        </div>
        <div id="logs-course" class="tab-content">
            {logs_course_html}
        </div>
        {parity_tab_panel}
    </div>
    <script>{js}</script>
</body>
</html>"""
    return report_html
