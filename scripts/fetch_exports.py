import os
import sys
import json
import time
import datetime

# Add src to the path to import canvas_exporter
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(root_dir, "src"))

# pyrefly: ignore [missing-import]
from canvas_exporter import (
    start_course_export,
    check_export_status,
    get_past_exports,
    save_download,
)

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


def find_export_created_today(course_id, today):
    """Returns today's newest reusable Common Cartridge export, if one exists."""
    exports = get_past_exports(course_id)
    candidates = []

    for export in exports:
        if export.get("export_type") != "common_cartridge":
            continue
        if export.get("workflow_state") == "failed":
            continue

        created_at = export.get("created_at")
        if not created_at:
            continue

        try:
            export_date = datetime.datetime.fromisoformat(
                created_at.replace("Z", "+00:00")
            ).astimezone().date()
        except ValueError:
            continue

        if export_date == today:
            candidates.append(export)

    if not candidates:
        return None

    return max(candidates, key=lambda export: export.get("created_at", ""))


def metadata_path_for_export(output_file):
    return f"{os.path.splitext(output_file)[0]}.metadata.json"


def save_export_metadata(output_file, course_id, course_code, export_obj):
    """Stores the exact Canvas export boundary used for later attribution."""
    metadata_path = metadata_path_for_export(output_file)
    partial_path = f"{metadata_path}.part"
    metadata = {
        "course_id": str(course_id),
        "course_code": course_code,
        "export_id": export_obj.get("id"),
        "export_type": export_obj.get("export_type"),
        "workflow_state": export_obj.get("workflow_state"),
        "export_created_at": export_obj.get("created_at"),
        "downloaded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
    try:
        with open(partial_path, "w", encoding="utf-8") as metadata_file:
            json.dump(metadata, metadata_file, indent=2)
            metadata_file.write("\n")
        os.replace(partial_path, metadata_path)
    finally:
        if os.path.exists(partial_path):
            os.remove(partial_path)

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
        
    today = datetime.datetime.now().astimezone().date()
    today_str = today.isoformat()
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
            metadata_path = metadata_path_for_export(output_file)
            if not os.path.exists(metadata_path):
                try:
                    export_obj = find_export_created_today(course_id, today)
                    if export_obj:
                        save_export_metadata(output_file, course_id, code, export_obj)
                        print(f"Backfilled export metadata: {metadata_path}")
                    else:
                        print(f"No same-day Canvas export metadata found for {code}.")
                except Exception as e:
                    print(f"Could not backfill export metadata for {code}: {e}")
            continue
            
        print(f"[{idx}/{len(courses)}] Checking export for {code} (ID: {course_id})...")
        try:
            export_obj = find_export_created_today(course_id, today)
            if export_obj:
                print(
                    f"Reusing today's export {export_obj['id']} "
                    f"({export_obj.get('workflow_state', 'unknown')}) for {code}."
                )
            else:
                print(f"Triggering a new export for {code}...")
                export_obj = start_course_export(course_id)

            if (
                export_obj.get("workflow_state") == "exported"
                and export_obj.get("attachment", {}).get("url")
            ):
                print(f"Today's export for {code} is ready. Downloading now...")
                save_download(export_obj["attachment"]["url"], output_file)
                save_export_metadata(output_file, course_id, code, export_obj)
                cleanup_old_exports(os.path.dirname(output_file), keep=5)
                time.sleep(1)
                continue

            pending_exports.append({
                "code": code,
                "course_id": course_id,
                "export_id": export_obj["id"],
                "output_file": output_file,
                "status_errors": 0,
            })
            # Sleep slightly to avoid hitting Canvas API rate limits.
            time.sleep(1)
        except Exception as e:
            print(f"Error preparing export for {code}: {e}")

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
                    save_export_metadata(out_file, c_id, code, status_obj)
                    
                    # Clean up old exports for this course
                    cleanup_old_exports(os.path.dirname(out_file), keep=5)
                    
                    pending_exports.remove(task)
                elif state == "failed":
                    print(f"❌ {code} export failed on Canvas.")
                    pending_exports.remove(task)
                else:
                    print(f"⏳ {code} is still '{state}'...")
            except Exception as e:
                task["status_errors"] += 1
                print(f"Error checking status for {code}: {e}")
                if task["status_errors"] >= 5:
                    print(f"Giving up on {code} after 5 consecutive status errors.")
                    pending_exports.remove(task)
                
        if pending_exports:
            # Wait before checking the remaining ones again
            time.sleep(15)
            
    print("\nAll export tasks completed!")

if __name__ == "__main__":
    main()
