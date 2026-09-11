import os
import json
import datetime
import tempfile
from config_loader import load_config
from imscc_handler import extract_imscc
from differ import generate_diff_data
from content_attributor import attribute_course_changes
from page_attributor import course_id_from_url
from html_reporter import generate_html_report
from emailer import send_report
from link_auditor import find_inaccessible_google_exports
from parity_comparer import enrich_courses_with_en_pt_parity


def snapshot_date_from_directory(directory_name):
    suffix = "_extracted"
    if directory_name.endswith(suffix):
        return directory_name[:-len(suffix)]
    return directory_name


def get_test_recipient(config):
    recipient = config.get("test_email")
    if not recipient:
        return None
    return str(recipient).strip() or None


def week_start_date(day=None):
    """Monday of the given day's ISO week (the saved weekly report identity)."""
    day = day or datetime.date.today()
    return day - datetime.timedelta(days=day.weekday())


def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config = load_config(root_dir)
    
    json_path = os.path.join(root_dir, "data", "courses.json")
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found.")
        return
        
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    courses = data.get("courses", [])
    history_dir = os.path.join(root_dir, "all_course_history")
    
    report_date = week_start_date().strftime("%Y-%m-%d")
    print(f"Starting Automated Course Change Logs for week of {report_date}")
    
    if not courses:
        print("No courses found in JSON.")
        return
        
    courses_data = []
    
    for course in courses:
        course_code = course.get("course_code")
        print(f"\nProcessing Course: {course_code}")
        
        course_dir = os.path.join(history_dir, course_code)
        
        if not os.path.exists(course_dir):
            print(f"No history found for {course_code}. Run fetch scripts first.")
            continue
            
        # First, find any new .imscc files and extract them (this will auto-delete them)
        imscc_files = [f for f in os.listdir(course_dir) if f.endswith('.imscc')]
        for imscc in imscc_files:
            imscc_path = os.path.join(course_dir, imscc)
            try:
                extract_imscc(imscc_path)
            except Exception as e:
                print(f"Failed to extract {imscc}: {e}")
                
        # Now find all extracted directories
        extracted_dirs = [d for d in os.listdir(course_dir) if d.endswith('_extracted') and os.path.isdir(os.path.join(course_dir, d))]
        extracted_dirs.sort(reverse=True) # Newest first (relies on YYYY-MM-DD prefix)
        
        if len(extracted_dirs) < 2:
            print(f"Not enough history for {course_code} to run a diff (needs at least 2 exports).")
            continue
            
        current_extract_dir = os.path.join(course_dir, extracted_dirs[0])
        previous_extract_dir = os.path.join(course_dir, extracted_dirs[1])
        
        print(f"Comparing {extracted_dirs[1]} -> {extracted_dirs[0]}")
        
        course_data = generate_diff_data(previous_extract_dir, current_extract_dir, course_code)
        course_data["comparison_period"] = {
            "previous_date": snapshot_date_from_directory(extracted_dirs[1]),
            "current_date": snapshot_date_from_directory(extracted_dirs[0]),
        }
        course_data["course_url"] = course.get("course_url", "")
        canvas_course_id = course_id_from_url(course.get("course_url"))
        try:
            attribution_stats = attribute_course_changes(
                course_data,
                canvas_course_id,
                previous_extract_dir,
                current_extract_dir,
            )
            if attribution_stats["items_checked"]:
                print(
                    "Content attribution: "
                    f"{attribution_stats['items_attributed']}/"
                    f"{attribution_stats['items_checked']} changes attributed."
                )
        except Exception as e:
            print(f"Content attribution failed for {course_code}: {e}")

        try:
            link_issues = find_inaccessible_google_exports(current_extract_dir)
            course_data["inaccessible_google_exports"] = link_issues
            if link_issues:
                print(
                    f"Inaccessible Google export links: {len(link_issues)} "
                    "flagged for Course Designers."
                )
        except Exception as e:
            print(f"Google link audit failed for {course_code}: {e}")
            course_data["inaccessible_google_exports"] = []

        course_data["designer"] = course.get("course_designer", "Unknown")
        courses_data.append(course_data)

    print("\nRunning EN/PT parity checks (English is canon)...")
    try:
        pairs = enrich_courses_with_en_pt_parity(courses_data, history_dir)
        print(f"EN/PT parity compared {pairs} course pair(s).")
    except Exception as e:
        print(f"EN/PT parity enrichment failed: {e}")
        
    full_report_html = generate_html_report(report_date, courses_data, default_designer="all")
    
    reports_dir = os.path.join(root_dir, 'reports')
    os.makedirs(reports_dir, exist_ok=True)
    # One weekly report only (re-runs in the same week overwrite this file)
    master_report_path = os.path.join(reports_dir, f"report_{report_date}.html")
    with open(master_report_path, 'w', encoding='utf-8') as f:
        f.write(full_report_html)
        
    print(f"\nWeekly report saved to {master_report_path}")
    
    # Send personalized emails to each designer (temp files only; not saved to reports/)
    unique_designers = {}
    for c in courses:
        name = c.get("course_designer")
        email = c.get("designer_email")
        if name and email and name not in unique_designers:
            unique_designers[name] = email
            
    for designer_name, designer_email in unique_designers.items():
        print(f"\nGenerating personalized report for {designer_name}...")
        designer_html = generate_html_report(report_date, courses_data, default_designer=designer_name)
        
        recipient = get_test_recipient(config)
        if not recipient:
            print(
                "TEST_EMAIL is not configured. Skipping email to prevent "
                f"delivery to {designer_name}."
            )
            continue

        safe_name = designer_name.replace(' ', '_').replace('.', '')
        with tempfile.TemporaryDirectory() as tmp_dir:
            designer_report_path = os.path.join(
                tmp_dir, f"report_{report_date}_{safe_name}.html"
            )
            with open(designer_report_path, 'w', encoding='utf-8') as f:
                f.write(designer_html)

            print(f"Sending email to {recipient} (Intended for: {designer_name})...")
            send_report(
                f"Canvas Course Changes - {report_date} - {designer_name}",
                designer_html,
                designer_report_path,
                config,
                recipient_email=recipient,
                designer_name=designer_name,
            )
        
    print("\nDone.")

if __name__ == "__main__":
    main()
