import os
import filecmp
import difflib
from bs4 import BeautifulSoup

def _get_xml_text_content(file_path):
    """Parses XML/HTML and returns stripped text to avoid noisy metadata diffs."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'lxml-xml' if file_path.endswith('.xml') else 'html.parser')
            # Extract meaningful text, ignoring scripts and styles which might contain noisy auto-generated data
            for script in soup(["script", "style"]):
                script.extract()
            # Get text and split into lines
            return soup.get_text(separator='\n').splitlines()
    except Exception:
        # Fallback to reading lines directly if parsing fails
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.readlines()

def generate_diff(old_dir: str, new_dir: str, course_id: str):
    """
    Compares two directories recursively and returns a markdown string of the differences.
    Prioritizes wiki_content (Pages) and course_settings.
    """
    if not old_dir or not os.path.exists(old_dir):
        return f"## Course {course_id}\n\n*No previous export found. All files are considered new.*\n"
        
    md_lines = [f"## Course {course_id}\n"]
    
    dcmp = filecmp.dircmp(old_dir, new_dir)
    
    changes = {
        "wiki_content": [],
        "course_settings": [],
        "other": []
    }
    
    def add_change(file_path, change_text):
        # Normalize path separators for checking
        normalized = file_path.replace('\\', '/')
        if "wiki_content" in normalized:
            changes["wiki_content"].append(change_text)
        elif "course_settings" in normalized:
            changes["course_settings"].append(change_text)
        else:
            changes["other"].append(change_text)
            
    def process_dircmp(cmp_obj, current_path=""):
        # Files only in new
        for name in cmp_obj.right_only:
            file_path = os.path.join(current_path, name)
            add_change(file_path, f"- **Added**: `{file_path}`")
            
        # Files only in old
        for name in cmp_obj.left_only:
            file_path = os.path.join(current_path, name)
            add_change(file_path, f"- **Deleted**: `{file_path}`")
            
        # Files changed
        for name in cmp_obj.diff_files:
            file_path = os.path.join(current_path, name)
            
            diff_text = []
            if name.endswith(('.xml', '.html', '.txt')):
                old_file = os.path.join(cmp_obj.left, name)
                new_file = os.path.join(cmp_obj.right, name)
                
                try:
                    lines1 = _get_xml_text_content(old_file)
                    lines2 = _get_xml_text_content(new_file)
                    
                    diff = list(difflib.unified_diff(
                        [l.strip() for l in lines1 if l.strip()],
                        [l.strip() for l in lines2 if l.strip()],
                        fromfile='Previous',
                        tofile='Current',
                        n=2,
                        lineterm=''
                    ))
                    
                    if diff:
                        diff_text.append(f"- **Modified**: `{file_path}`")
                        diff_text.append("  ```diff")
                        for line in diff[:30]:
                            diff_text.append("  " + line)
                        if len(diff) > 30:
                            diff_text.append("  ... (diff truncated)")
                        diff_text.append("  ```")
                except Exception:
                    pass
            
            if diff_text:
                add_change(file_path, "\n".join(diff_text))
            else:
                # Binary or noisy file change with no meaningful text content change
                add_change(file_path, f"- **Modified (Binary/Metadata)**: `{file_path}`")
                
        # Recursively process subdirectories
        for sub_dir, sub_cmp in cmp_obj.subdirs.items():
            process_dircmp(sub_cmp, os.path.join(current_path, sub_dir))

    process_dircmp(dcmp)
    
    has_changes = False
    
    if changes["wiki_content"]:
        md_lines.append("### Pages (wiki_content)")
        md_lines.extend(changes["wiki_content"])
        md_lines.append("")
        has_changes = True
        
    if changes["course_settings"]:
        md_lines.append("### Course Settings")
        md_lines.extend(changes["course_settings"])
        md_lines.append("")
        has_changes = True
        
    if changes["other"]:
        md_lines.append("### Other Files")
        md_lines.extend(changes["other"])
        md_lines.append("")
        has_changes = True
        
    if not has_changes:
        md_lines.append("*No meaningful content changes detected this week.*\n")
        
    return "\n".join(md_lines)
