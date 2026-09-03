import os
import sys
import json
import time
import datetime

# Add src to the path to import canvas_exporter
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(root_dir, "src"))

from canvas_exporter import start_course_export, check_export_status, save_download

def get_course_id_from_url(url):
    """
    Extracts the numeric course ID from a Canvas URL.
    """
    if not url:
        return None
        
    parts = url.rstrip('/').split('/')
    try:
        return parts[-1]
    except Exception:
        return None

import shutil

def cleanup_old_exports(course_dir, keep=5):
    """
    Keeps only the most recent 'keep' extracted folders in the given directory.
    Deletes older ones to optimize storage.
    """
    if not os.path.exists(course_dir):
        return
        
    items = [d for d in os.listdir(course_dir) if d.endswith('_extracted')]
    # Sort alphabetically in descending order (newest first based on date prefix)
    items.sort(reverse=True)
    
    if len(items) > keep:
        for old_item in items[keep:]:
            old_path = os.path.join(course_dir, old_item)
            try:
                shutil.rmtree(old_path)
                print(f"Removed old extracted folder to keep history limited to 5: {old_item}")
            except Exception as e:
                print(f"Failed to remove {old_path}: {e}")

def main():
    json_path = os.path.join(root_dir, "data", "courses.json")
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found.")
        return
        
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    courses = data.get("courses", [])
    if not courses:
        print("No courses found in JSON.")
        return
        
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    history_dir = os.path.join(root_dir, "all_course_history")
    
    print(f"Starting Canvas exports for all {len(courses)} courses...")
    
    processed_count = 0
    
    pending_exports = []

    # Phase 1: Trigger all exports
    for idx, course in enumerate(courses, 1):
            
        code = course.get("course_code")
        url = course.get("course_url")
        
        course_id = get_course_id_from_url(url)
        if not course_id:
            continue
            
        output_file = os.path.join(history_dir, code, f"{today_str}.imscc")
        processed_count += 1
        
        if os.path.exists(output_file):
            print(f"Already exported today: {output_file}")
            continue
            
        print(f"[{idx}/{len(courses)}] Triggering export for {code} (ID: {course_id})...")
        try:
            export_obj = start_course_export(course_id)
            pending_exports.append({
                "code": code,
                "course_id": course_id,
                "export_id": export_obj["id"],
                "output_file": output_file
            })
            # Sleep slightly to avoid hitting Canvas API rate limits for starting jobs
            time.sleep(1) 
        except Exception as e:
            print(f"Error triggering {code}: {e}")

    # Phase 2: Poll and Download
    print(f"\nAll ({len(pending_exports)}) exports triggered! Monitoring for completion...")
    
    while pending_exports:
        print(f"\nChecking status for {len(pending_exports)} remaining exports...")
        
        # Iterate over a copy so we can safely remove completed items
        for task in pending_exports[:]:
            code = task["code"]
            c_id = task["course_id"]
            e_id = task["export_id"]
            out_file = task["output_file"]
            
            try:
                status_obj = check_export_status(c_id, e_id)
                state = status_obj.get("workflow_state")
                
                if state == "exported":
                    print(f"✅ {code} export finished! Downloading...")
                    download_url = status_obj["attachment"]["url"]
                    save_download(download_url, out_file)
                    
                    # Clean up old exports for this course
                    cleanup_old_exports(os.path.dirname(out_file), keep=5)
                    
                    pending_exports.remove(task)
                elif state == "failed":
                    print(f"❌ {code} export failed on Canvas.")
                    pending_exports.remove(task)
                else:
                    print(f"⏳ {code} is still '{state}'...")
            except Exception as e:
                print(f"Error checking status for {code}: {e}")
                
        if pending_exports:
            # Wait before checking the remaining ones again
            time.sleep(15)
            
    print("\nAll export tasks completed!")

if __name__ == "__main__":
    main()
