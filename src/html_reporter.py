import json

def generate_html_report(year_week: str, courses_data: list):
    """
    Generates a beautiful HTML report with Dashboard and Logs tabs.
    courses_data is a list of dictionaries returned by generate_diff_data.
    """
    
    # Calculate some stats for the dashboard
    total_courses = len(courses_data)
    courses_with_changes = sum(1 for c in courses_data if c.get("has_changes", False))
    
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

    # Build the Raw Logs HTML
    logs_html = ""
    for c in courses_data:
        logs_html += f"<div class='course-section'><h2>{c['course_name']}</h2>"
        
        streak = c.get("zero_changes_streak", 0)
        if streak >= 5:
            logs_html += f"""
            <div style="background: rgba(255, 152, 0, 0.1); border-left: 4px solid #ff9800; padding: 1rem; margin-bottom: 1.5rem; border-radius: 4px;">
                <strong style="color: #ff9800;">⚠️ Maintenance Recommendation:</strong> This course has had zero changes for {streak} consecutive weeks. Designers are recommended to check standard pages and resources to ensure course material is being actively maintained.
            </div>
            """
        elif streak > 0:
            logs_html += f"<p style='color: var(--text-muted); font-size: 0.9rem; margin-top: -10px;'><em>No changes for {streak} consecutive weeks.</em></p>"

        if c.get("is_new"):
            logs_html += "<p><em>No previous export found. All files considered new.</em></p></div>"
            continue
            
        if not c.get("has_changes"):
            logs_html += "<p><em>No meaningful content changes detected this week.</em></p></div>"
            continue
            
        for cat_key, cat_title in category_titles.items():
            items = c["categories"].get(cat_key, [])
            if not items:
                continue
                
            logs_html += f"""
            <div class="accordion" data-category="{cat_key}">
                <div class="accordion-header" onclick="toggleAccordion(this)">
                    <span>{cat_title} ({len(items)} changes)</span>
                    <span class="icon">▼</span>
                </div>
                <div class="accordion-content">
            """
            
            for item in items:
                labels_html = "".join([f"<span class='label label-{l.lower().replace('/', '-').replace(' ', '-')}'>{l}</span>" for l in item["labels"]])
                
                # Make the header clickable
                display_title = item.get('file_title', item['file_path'])
                logs_html += f"""
                <div class="file-item">
                    <div class="file-header" onclick="toggleFile(this)" style="cursor: pointer; display: flex; justify-content: space-between; align-items: center; padding: 0.5rem; background: rgba(255,255,255,0.02); border-radius: 4px;">
                        <div style="display: flex; align-items: center; gap: 0.8rem; flex-wrap: wrap;">
                            <span class="status status-{item['status'].split(' ')[0].lower()}">{item['status']}</span>
                            <span class="file-path">{display_title}</span>
                            {labels_html}
                        </div>
                        <span class="file-icon" style="color: var(--text-muted); font-size: 0.8rem;">▼</span>
                    </div>
                """
                if item["diff_lines"]:
                    ai_html = ""
                    if item.get("ai_summary"):
                        ai_html = f"<div class='ai-summary' style='background: rgba(187, 134, 252, 0.1); border-left: 3px solid var(--accent); padding: 0.8rem; margin-top: 0.5rem; font-size: 0.9rem; border-radius: 4px;'><strong>AI Summary:</strong> {item['ai_summary']}</div>"
                    
                    # Default to display: none for a compact list
                    logs_html += f"<div class='diff-views-container' style='display: none; padding-top: 1rem;'>{ai_html}"
                    
                    # Single Unified Diff View
                    logs_html += "<pre class='diff-block'>"
                    for line in item["diff_lines"]:
                        line_safe = line.replace('<', '&lt;').replace('>', '&gt;')
                        if line.startswith('+++') or line.startswith('---'):
                            logs_html += f"<div class='diff-meta'>{line_safe}</div>"
                        elif line.startswith('+'):
                            logs_html += f"<div class='diff-add'>{line_safe}</div>"
                        elif line.startswith('-'):
                            logs_html += f"<div class='diff-remove'>{line_safe}</div>"
                        elif line.startswith('@@'):
                            logs_html += f"<div class='diff-chunk'>{line_safe}</div>"
                        else:
                            logs_html += f"<div class='diff-context'>{line_safe}</div>"
                    logs_html += "</pre>"
                    
                    logs_html += "</div>"
                logs_html += "</div>"
                
            logs_html += """
                </div>
            </div>
            """
        logs_html += "</div>"
        
    # CSS & JS
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
    .nav-actions button { border: 1px solid var(--border); color: var(--text); }
    
    .container { padding: 2rem; max-width: 1200px; margin: 0 auto; }
    .tab-content { display: none; }
    .tab-content.active { display: block; animation: fadeIn 0.3s; }
    
    @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
    
    /* Dashboard */
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
    .cat-row:hover { background: rgba(255, 255, 255, 0.05); }
    
    /* Logs */
    .course-section { margin-bottom: 3rem; }
    .course-section h2 { border-bottom: 2px solid var(--accent); padding-bottom: 0.5rem; display: inline-block; }
    
    .accordion { margin-bottom: 1rem; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; background: var(--surface); }
    .accordion-header {
        padding: 1rem; cursor: pointer; display: flex; justify-content: space-between;
        background: rgba(255,255,255,0.02); transition: 0.2s; font-weight: 600;
    }
    .accordion-header:hover { background: var(--surface-hover); }
    .accordion-content { display: none; padding: 1rem; border-top: 1px solid var(--border); }
    
    .file-item { margin-bottom: 1.5rem; }
    .file-header { display: flex; align-items: center; gap: 0.8rem; margin-bottom: 0.5rem; flex-wrap: wrap; }
    .file-path { font-family: monospace; font-size: 0.9rem; }
    .status { padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.8rem; font-weight: bold; }
    .status-modified { background: #ffb74d; color: #000; }
    .status-added { background: #81c784; color: #000; }
    .status-deleted { background: #e57373; color: #000; }
    
    .label { font-size: 0.75rem; padding: 0.2rem 0.5rem; border-radius: 12px; border: 1px solid var(--text-muted); color: var(--text-muted); background: rgba(255,255,255,0.05); }
    
    /* Diff View */
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
    function switchTab(tabId) {
        document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
        document.querySelectorAll('.nav-links button').forEach(el => el.classList.remove('active'));
        document.getElementById(tabId).classList.add('active');
        event.currentTarget.classList.add('active');
    }
    function toggleAccordion(header) {
        const content = header.nextElementSibling;
        const icon = header.querySelector('.icon');
        if (content.style.display === 'block') {
            content.style.display = 'none';
            icon.textContent = '▼';
        } else {
            content.style.display = 'block';
            icon.textContent = '▲';
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
    function openCategory(catKey) {
        switchTab('logs');
        document.querySelectorAll('.accordion').forEach(acc => {
            const content = acc.querySelector('.accordion-content');
            const icon = acc.querySelector('.icon');
            if (acc.getAttribute('data-category') === catKey) {
                content.style.display = 'block';
                if(icon) icon.textContent = '▲';
            } else {
                content.style.display = 'none';
                if(icon) icon.textContent = '▼';
            }
        });
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
    """
    
    # Dashboard HTML
    dashboard_html = f"""
    <div class="metric-grid">
        <div class="metric-card">
            <div class="metric-value">{total_courses}</div>
            <div class="metric-label">Courses Scanned</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{courses_with_changes}</div>
            <div class="metric-label">Courses w/ Changes</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{sum(total_changes_by_category.values())}</div>
            <div class="metric-label">Total Files Modified</div>
        </div>
    </div>
    
    """
    
    # Course Insights Section
    insights_html = ""
    for c in courses_data:
        if c.get("has_changes") and c.get("course_ai_summary"):
            impact = c.get("course_ai_impact", "Medium")
            impact_color = {"Low": "#4caf50", "Medium": "#ffb74d", "High": "#e57373"}.get(impact, "#ffb74d")
            
            insights_html += f"""
            <div style="background: var(--surface); padding: 1.5rem; border-radius: 12px; border: 1px solid var(--border); margin-bottom: 1rem; position: relative;">
                <h3 style="margin-top: 0; color: var(--accent); width: 80%;">{c['course_name']}</h3>
                <span style="position: absolute; top: 1.5rem; right: 1.5rem; background: {impact_color}22; color: {impact_color}; padding: 0.3rem 0.8rem; border-radius: 20px; font-weight: bold; font-size: 0.85rem; border: 1px solid {impact_color};">Impact: {impact}</span>
                <p style="margin-bottom: 0; line-height: 1.6;">{c['course_ai_summary']}</p>
            </div>
            """
            
    if insights_html:
        dashboard_html += "<h2>Course Insights</h2>" + insights_html

    dashboard_html += """
    <h2 style='margin-top: 3rem;'>Changes by Category</h2>
    <div class="category-stats">
    """
    for k, title in category_titles.items():
        val = total_changes_by_category.get(k, 0)
        dashboard_html += f"<div class='cat-row' onclick=\"openCategory('{k}')\" style=\"cursor: pointer;\"><span>{title}</span><strong>{val}</strong></div>"
    dashboard_html += "</div>"

    html = f"""<!DOCTYPE html>
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
                <button class="active" onclick="switchTab('dashboard')">Dashboard</button>
                <button onclick="switchTab('logs')">Raw Logs</button>
            </div>
        </div>
    </nav>
    <div class="container">
        <div id="dashboard" class="tab-content active">
            {dashboard_html}
        </div>
        <div id="logs" class="tab-content">
            {logs_html}
        </div>
    </div>
    <script>{js}</script>
</body>
</html>"""
    return html
