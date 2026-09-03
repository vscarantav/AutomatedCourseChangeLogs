import os
import datetime
from config_loader import load_config
from scraper import download_course_export
from imscc_handler import extract_imscc
from differ import generate_diff_data
from html_reporter import generate_html_report
from emailer import send_report

def get_current_year_week():
    now = datetime.datetime.now()
    return f"{now.isocalendar()[0]}_W{now.isocalendar()[1]:02d}"

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config = load_config(root_dir)
    year_week = get_current_year_week()
    
    print(f"Starting Automated Course Change Logs for {year_week}")
    
    if not config.get("courses"):
        print("No courses found in configuration.")
        return
        
    courses_data = []
    
    for course in config["courses"]:
        print(f"\nProcessing Course: {course['name']} ({course['id']})")
        
        export_base = os.path.join(root_dir, 'exports', course['id'])
        current_export_dir = os.path.join(export_base, year_week)
        current_extract_dir = os.path.join(current_export_dir, 'extracted')
        
        # Skip download if already exists
        if os.path.exists(current_extract_dir):
            print(f"Data for {year_week} already extracted for {course['id']}. Skipping download.")
        else:
            imscc_path = download_course_export(course, root_dir, year_week)
            if not imscc_path:
                print(f"Failed to download export for {course['id']}")
                courses_data.append({"course_name": f"{course['name']} ({course['id']})", "has_changes": False, "error": "Failed to download"})
                continue
                
            try:
                extract_imscc(imscc_path)
            except Exception as e:
                print(f"Failed to extract export for {course['id']}: {e}")
                courses_data.append({"course_name": f"{course['name']} ({course['id']})", "has_changes": False, "error": f"Failed to extract: {e}"})
                continue
            
        # Find previous week
        try:
            existing_weeks = sorted([d for d in os.listdir(export_base) if os.path.isdir(os.path.join(export_base, d))])
        except Exception:
            existing_weeks = []
            
        previous_extract_dir = None
        if len(existing_weeks) > 1:
            if year_week in existing_weeks:
                current_idx = existing_weeks.index(year_week)
                if current_idx > 0:
                    prev_week_folder = existing_weeks[current_idx - 1]
                    prev_candidate = os.path.join(export_base, prev_week_folder, 'extracted')
                    if os.path.exists(prev_candidate):
                        previous_extract_dir = prev_candidate
                        
        course_data = generate_diff_data(previous_extract_dir, current_extract_dir, f"{course['name']} ({course['id']})")
        courses_data.append(course_data)
        
    full_report_html = generate_html_report(year_week, courses_data)
    
    reports_dir = os.path.join(root_dir, 'reports')
    os.makedirs(reports_dir, exist_ok=True)
    report_path = os.path.join(reports_dir, f"report_{year_week}.html")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(full_report_html)
        
    print(f"\nReport saved to {report_path}")
    
    # Pass html string and file path to emailer
    send_report(f"Canvas Course Changes - {year_week}", full_report_html, report_path, config)
    print("Done.")

if __name__ == "__main__":
    main()
