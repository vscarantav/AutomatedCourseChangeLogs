import os
import datetime
from config_loader import load_config
from scraper import download_course_export
from imscc_handler import extract_imscc
from differ import generate_diff
from emailer import send_report

def get_current_year_week():
    now = datetime.datetime.now()
    # Returns Year_WWeek (e.g. 2026_W34)
    return f"{now.isocalendar()[0]}_W{now.isocalendar()[1]:02d}"

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config = load_config(root_dir)
    year_week = get_current_year_week()
    
    print(f"Starting Automated Course Change Logs for {year_week}")
    
    if not config["courses"]:
        print("No courses found in configuration.")
        return
        
    report_lines = [f"# Canvas Course Change Logs - {year_week}\n"]
    
    for course in config["courses"]:
        print(f"\nProcessing Course: {course['name']} ({course['id']})")
        
        export_base = os.path.join(root_dir, 'exports', course['id'])
        current_export_dir = os.path.join(export_base, year_week)
        current_extract_dir = os.path.join(current_export_dir, 'extracted')
        
        # Skip download if already exists (handles re-runs in the same week)
        if os.path.exists(current_extract_dir):
            print(f"Data for {year_week} already extracted for {course['id']}. Skipping download.")
        else:
            # 1. Download
            imscc_path = download_course_export(course, root_dir, year_week)
            if not imscc_path:
                report_lines.append(f"## Course {course['name']} ({course['id']})\n*Failed to download export.*\n")
                continue
                
            # 2. Extract
            try:
                extract_imscc(imscc_path)
            except Exception as e:
                report_lines.append(f"## Course {course['name']} ({course['id']})\n*Failed to extract export: {e}*\n")
                continue
            
        # 3. Diff
        # Find the previous week's extraction
        existing_weeks = sorted([d for d in os.listdir(export_base) if os.path.isdir(os.path.join(export_base, d))])
        
        previous_extract_dir = None
        if len(existing_weeks) > 1:
            # Since sorted chronologically, the one right before current week is at index -2
            # Wait, if we just ran it, it's at -1. If we skipped download because it existed, it's still -1
            # Let's find the current week index
            if year_week in existing_weeks:
                current_idx = existing_weeks.index(year_week)
                if current_idx > 0:
                    prev_week_folder = existing_weeks[current_idx - 1]
                    prev_candidate = os.path.join(export_base, prev_week_folder, 'extracted')
                    if os.path.exists(prev_candidate):
                        previous_extract_dir = prev_candidate
                        
        diff_md = generate_diff(previous_extract_dir, current_extract_dir, f"{course['name']} ({course['id']})")
        report_lines.append(diff_md)
        
    # Combine report
    full_report = "\n".join(report_lines)
    
    # Save report locally
    reports_dir = os.path.join(root_dir, 'reports')
    os.makedirs(reports_dir, exist_ok=True)
    report_path = os.path.join(reports_dir, f"report_{year_week}.md")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(full_report)
        
    print(f"\nReport saved to {report_path}")
    
    # Send email
    send_report(f"Canvas Course Changes - {year_week}", full_report, config)
    print("Done.")

if __name__ == "__main__":
    main()
