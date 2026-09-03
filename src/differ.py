import os
import filecmp
import difflib
import re
from bs4 import BeautifulSoup

def _get_xml_text_content(file_path):
    """Parses XML/HTML and returns text. HTML is stripped of tags, XML retains tags for schema readability."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            if file_path.endswith('.xml'):
                # Return raw lines but stripped of whitespace
                return [line.strip() for line in f.readlines() if line.strip()]
            else:
                soup = BeautifulSoup(f.read(), 'html.parser')
                for script in soup(["script", "style"]):
                    script.extract()
                return soup.get_text(separator='\n').splitlines()
    except Exception:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.readlines()

def get_semantic_labels(diff_lines):
    """Parses diff lines to assign semantic labels."""
    labels = set()
    for line in diff_lines:
        if line.startswith('+') or line.startswith('-'):
            if line.startswith('+++') or line.startswith('---'):
                continue
            text = line[1:].lower()
            
            # Content Change
            if re.search(r'<[p|span|div|a|h\d][^>]*>|&[a-z]+;', text) or (re.search(r'\w{4,}', text) and not re.search(r'^\s*[{}"\',:_-]+\s*$', text) and 'require_lockdown_browser' not in text):
                labels.add("Content Change")
            
            # Grading Rule
            if 'points_possible' in text or 'grading_type' in text or 'rubric' in text or 'weight' in text:
                labels.add("Grading Rule")
                
            # Date/Restriction
            if 'due_at' in text or 'unlock_at' in text or 'lock_at' in text or 'require_lockdown_browser' in text:
                labels.add("Date/Restriction")
                
            # Metadata/System
            if 'last_modified' in text or 'id="' in text or 'identifier="' in text:
                labels.add("Metadata/System")
                
    if not labels:
        labels.add("Metadata/System")
    
    return sorted(list(labels))

def generate_diff_data(old_dir: str, new_dir: str, course_id: str):
    """
    Compares two directories recursively and returns a structured dictionary of differences.
    """
    data = {
        "course_name": course_id,
        "is_new": False,
        "has_changes": False,
        "categories": {
            "manifest": [],
            "assignments": [],
            "pages": [],
            "quizzes_banks": [],
            "course_settings": [],
            "rubrics": [],
            "discussions": [],
            "files_media": [],
            "other": []
        }
    }
    
    if not old_dir or not os.path.exists(old_dir):
        data["is_new"] = True
        return data
        
    dcmp = filecmp.dircmp(old_dir, new_dir)
    
    def add_change(file_path, status, diff_lines=None, labels=None, ai_summary=""):
        normalized = file_path.replace('\\', '/')
        
        file_title = file_path
        try:
            target_path = os.path.join(new_dir, file_path)
            if status == "Deleted":
                target_path = os.path.join(old_dir, file_path)
            
            if os.path.exists(target_path) and target_path.endswith(('.xml', '.html')):
                with open(target_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    match = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
                    if match and match.group(1).strip():
                        file_title = match.group(1).strip()
        except:
            pass
        
        category = "other"
        if normalized == "imsmanifest.xml":
            category = "manifest"
        elif "wiki_content" in normalized:
            category = "pages"
        elif "non_cc_assessments" in normalized or normalized.endswith("assessment_meta.xml") or normalized.endswith("assessment_qti.xml"):
            category = "quizzes_banks"
        elif normalized == "course_settings/rubrics.xml":
            category = "rubrics"
        elif "course_settings" in normalized:
            category = "course_settings"
        elif "discussion_topics" in normalized:
            category = "discussions"
        elif "web_resources" in normalized:
            category = "files_media"
        else:
            if re.match(r'^[a-f0-9]{32}', normalized) or "assignment" in normalized:
                category = "assignments"
                
        data["categories"][category].append({
            "file_path": file_path,
            "file_title": file_title,
            "status": status,
            "labels": labels or [],
            "diff_lines": diff_lines or [],
            "ai_summary": ai_summary
        })
        data["has_changes"] = True
            
    def process_dircmp(cmp_obj, current_path=""):
        for name in cmp_obj.right_only:
            add_change(os.path.join(current_path, name), "Added")
            
        for name in cmp_obj.left_only:
            add_change(os.path.join(current_path, name), "Deleted")
            
        for name in cmp_obj.diff_files:
            file_path = os.path.join(current_path, name)
            diff_lines = []
            labels = []
            status = "Modified (Binary/Metadata)"
            
            if name.endswith(('.xml', '.html', '.txt', '.qti', '.json')):
                old_file = os.path.join(cmp_obj.left, name)
                new_file = os.path.join(cmp_obj.right, name)
                
                try:
                    def clean_lines(lines):
                        cleaned = []
                        # Allow optional XML wrappers around the metadata to effectively filter them out
                        uuid_pattern = re.compile(r'^(<[^>]+>)?\s*[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\s*(</[^>]+>)?$', re.IGNORECASE)
                        canvas_id_pattern = re.compile(r'^(<[^>]+>)?\s*g[a-f0-9]{32}\s*(</[^>]+>)?$', re.IGNORECASE)
                        timestamp_pattern = re.compile(r'^(<[^>]+>)?\s*\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}Z)?\s*(</[^>]+>)?$')
                        
                        for l in lines:
                            l = l.strip()
                            if not l:
                                continue
                            if 'require_lockdown_browser' in l:
                                continue
                            if uuid_pattern.match(l):
                                continue
                            if canvas_id_pattern.match(l):
                                continue
                            if timestamp_pattern.match(l):
                                continue
                            cleaned.append(l)
                        return cleaned
                        
                    lines1 = clean_lines(_get_xml_text_content(old_file))
                    lines2 = clean_lines(_get_xml_text_content(new_file))
                    
                    diff = list(difflib.unified_diff(
                        lines1,
                        lines2,
                        fromfile='Previous',
                        tofile='Current',
                        n=2,
                        lineterm=''
                    ))
                    
                    if not diff:
                        continue
                        
                    labels = get_semantic_labels(diff)
                    
                    from ai_summarizer import summarize_change
                    page_content = "\n".join(lines2)
                    ai_summary = summarize_change(page_content, diff, name)
                    
                    # Trim extremely long diffs for display
                    if len(diff) > 30:
                        diff_lines = diff[:30]
                        diff_lines.append("... (diff truncated)")
                    else:
                        diff_lines = diff
                    status = "Modified"
                except Exception:
                    pass
            
            add_change(file_path, status, diff_lines, labels, ai_summary=locals().get('ai_summary', ''))
                
        for sub_dir, sub_cmp in cmp_obj.subdirs.items():
            process_dircmp(sub_cmp, os.path.join(current_path, sub_dir))

    process_dircmp(dcmp)
    
    # Generate Course-Level AI Summary
    all_file_summaries = []
    for cat_items in data["categories"].values():
        for item in cat_items:
            if item.get("ai_summary"):
                all_file_summaries.append(item["ai_summary"])
                
    if all_file_summaries:
        try:
            from ai_summarizer import summarize_course_changes
            course_ai_data = summarize_course_changes(all_file_summaries)
            data["course_ai_summary"] = course_ai_data.get("summary", "")
            data["course_ai_impact"] = course_ai_data.get("impact", "N/A")
        except Exception:
            pass
    
    # State tracking
    export_base = os.path.dirname(os.path.dirname(new_dir))
    state_file = os.path.join(export_base, 'state.json')
    
    zero_changes_streak = 0
    if os.path.exists(state_file):
        try:
            import json
            with open(state_file, 'r') as f:
                state = json.load(f)
                zero_changes_streak = state.get('zero_changes_streak', 0)
        except Exception:
            pass
            
    if data["has_changes"]:
        zero_changes_streak = 0
    else:
        if not data["is_new"]:
            zero_changes_streak += 1
            
    data["zero_changes_streak"] = zero_changes_streak
    
    try:
        import json
        with open(state_file, 'w') as f:
            json.dump({'zero_changes_streak': zero_changes_streak}, f)
    except Exception:
        pass
        
    return data

def generate_diff(old_dir: str, new_dir: str, course_id: str):
    """
    Legacy wrapper for markdown output. Not used if using HTML reporter, 
    but kept for backwards compatibility.
    """
    data = generate_diff_data(old_dir, new_dir, course_id)
    if data["is_new"]:
        return f"## Course {course_id}\n\n*No previous export found. All files are considered new.*\n"
        
    md_lines = [f"## Course {course_id}\n"]
    
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
    
    for key, title in category_titles.items():
        items = data["categories"][key]
        if items:
            md_lines.append(f"### {title}")
            for item in items:
                labels_str = f" **[{']['.join(item['labels'])}]**" if item['labels'] else ""
                md_lines.append(f"- **{item['status']}**: `{item['file_path']}`{labels_str}")
                if item['diff_lines']:
                    md_lines.append("  ```diff")
                    for line in item['diff_lines']:
                        md_lines.append("  " + line)
                    md_lines.append("  ```")
            md_lines.append("")
        
    if not data["has_changes"]:
        md_lines.append("*No meaningful content changes detected this week.*\n")
        
    return "\n".join(md_lines)
