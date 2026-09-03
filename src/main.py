import os
import json
import datetime
from config_loader import load_config
from imscc_handler import extract_imscc
from differ import generate_diff_data
from html_reporter import generate_html_report
from emailer import send_report

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
    
    report_date = datetime.datetime.now().strftime("%Y-%m-%d")
    print(f"Starting Automated Course Change Logs for {report_date}")
    
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
        course_data["designer"] = course.get("course_designer", "Unknown")
        courses_data.append(course_data)
        
    full_report_html = generate_html_report(report_date, courses_data, default_designer="all")
    
    reports_dir = os.path.join(root_dir, 'reports')
    os.makedirs(reports_dir, exist_ok=True)
    master_report_path = os.path.join(reports_dir, f"report_{report_date}_Master.html")
    with open(master_report_path, 'w', encoding='utf-8') as f:
        f.write(full_report_html)
        
    print(f"\nMaster report saved to {master_report_path}")
    
    # Send personalized emails to each designer
    unique_designers = {}
    for c in courses:
        name = c.get("course_designer")
        email = c.get("designer_email")
        if name and email and name not in unique_designers:
            unique_designers[name] = email
            
    for designer_name, designer_email in unique_designers.items():
        print(f"\nGenerating personalized report for {designer_name}...")
        designer_html = generate_html_report(report_date, courses_data, default_designer=designer_name)
        
        safe_name = designer_name.replace(' ', '_').replace('.', '')
        designer_report_path = os.path.join(reports_dir, f"report_{report_date}_{safe_name}.html")
        
        with open(designer_report_path, 'w', encoding='utf-8') as f:
            f.write(designer_html)
            
        recipient = config.get("test_email")
        if designer_name == "Jen H.":
            recipient = designer_email
        elif not recipient:
            recipient = designer_email
            
        print(f"Sending email to {recipient} (Intended for: {designer_name})...")
        send_report(f"Canvas Course Changes - {report_date} - {designer_name}", designer_html, designer_report_path, config, recipient_email=recipient)
        
    print("\nDone.")

if __name__ == "__main__":
    main()
