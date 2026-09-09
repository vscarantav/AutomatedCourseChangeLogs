import os
import sys
import json
import datetime
from dateutil import parser # We need this to easily parse ISO 8601 strings from Canvas

# Add src to the path to import canvas_exporter
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(root_dir, "src"))

# pyrefly: ignore [missing-import]
from canvas_exporter import get_past_exports, save_download
from fetch_exports import (
    cleanup_old_exports,
    get_course_id_from_url,
    metadata_path_for_export,
    save_export_metadata,
)

def main():
    json_path = os.path.join(root_dir, "data", "courses.json")
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found.")
        return
        
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    courses = data.get("courses", [])
    history_dir = os.path.join(root_dir, "all_course_history")
    
    # We want exports that are at least 7 days old
    threshold_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)
    
    print(f"Starting fetch for past Canvas exports (older than 7 days) for {len(courses)} courses...")
    
    for idx, course in enumerate(courses, 1):
        code = course.get("course_code")
        url = course.get("course_url")
        
        course_id = get_course_id_from_url(url)
        if not course_id:
            continue
            
        print(f"\n[{idx}/{len(courses)}] Checking past exports for {code} (ID: {course_id})...")
        try:
            exports = get_past_exports(course_id)
            found_valid_export = False
            
            for exp in exports:
                # Check if it was exported and has an attachment
                if exp.get("workflow_state") == "exported" and "attachment" in exp:
                    created_at_str = exp.get("created_at")
                    if created_at_str:
                        created_at = parser.isoparse(created_at_str)
                        
                        # Check if it's older than our 7-day threshold
                        if created_at < threshold_date:
                            date_str = created_at.strftime("%Y-%m-%d")
                            output_file = os.path.join(history_dir, code, f"{date_str}.imscc")
                            
                            if os.path.exists(output_file):
                                print(f"  -> Already have export from {date_str}. Skipping.")
                            else:
                                print(f"  -> Found qualifying export from {date_str}. Downloading...")
                                download_url = exp["attachment"]["url"]
                                save_download(download_url, output_file)
                                cleanup_old_exports(os.path.dirname(output_file), keep=5)

                            metadata_path = metadata_path_for_export(output_file)
                            if not os.path.exists(metadata_path):
                                save_export_metadata(output_file, course_id, code, exp)
                            
                            found_valid_export = True
                            break # Max 1 per course
                            
            if not found_valid_export:
                print(f"  -> No valid exports found older than 1 week.")
                
        except Exception as e:
            print(f"Error checking {code}: {e}")

if __name__ == "__main__":
    main()
