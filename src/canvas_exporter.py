import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

CANVAS_API_KEY = os.getenv("CANVAS_API_KEY")
CANVAS_API_URL = os.getenv("CANVAS_API_URL", "https://canvas.instructure.com")

def start_course_export(course_id):
    """
    Triggers a new export for the given course_id.
    Returns the ContentExport object (which contains id and progress_url).
    """
    url = f"{CANVAS_API_URL}/api/v1/courses/{course_id}/content_exports"
    headers = {
        "Authorization": f"Bearer {CANVAS_API_KEY}"
    }
    data = {
        "export_type": "common_cartridge"
    }
    
    response = requests.post(url, headers=headers, data=data)
    response.raise_for_status()
    return response.json()

def check_export_status(course_id, export_id):
    """
    Checks the status of an export.
    """
    url = f"{CANVAS_API_URL}/api/v1/courses/{course_id}/content_exports/{export_id}"
    headers = {
        "Authorization": f"Bearer {CANVAS_API_KEY}"
    }
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def download_export(course_id, max_retries=60, sleep_time=10):
    """
    Triggers an export, polls until complete, and returns the download URL.
    max_retries=60 with sleep_time=10 means it will wait up to 10 minutes.
    """
    print(f"Starting export for course {course_id}...")
    export_obj = start_course_export(course_id)
    export_id = export_obj["id"]
    
    print(f"Export {export_id} started. Waiting for completion...")
    
    for attempt in range(max_retries):
        status_obj = check_export_status(course_id, export_id)
        state = status_obj.get("workflow_state")
        
        if state == "exported":
            print(f"Export {export_id} finished successfully.")
            return status_obj["attachment"]["url"]
        elif state == "failed":
            raise Exception(f"Export {export_id} failed on Canvas.")
            
        print(f"[{attempt + 1}/{max_retries}] Status is '{state}', waiting {sleep_time} seconds...")
        time.sleep(sleep_time)
        
    raise Exception(f"Export timed out after {max_retries * sleep_time} seconds.")

def get_past_exports(course_id):
    """
    Fetches the list of past content exports for the course.
    """
    url = f"{CANVAS_API_URL}/api/v1/courses/{course_id}/content_exports"
    headers = {
        "Authorization": f"Bearer {CANVAS_API_KEY}"
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code == 404:
        return []
    response.raise_for_status()
    return response.json()

def save_download(download_url, output_path):
    """
    Downloads the file from the given URL and saves it to output_path.
    """
    print(f"Downloading file to {output_path}...")
    response = requests.get(download_url, stream=True)
    response.raise_for_status()
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            
    print(f"Download complete: {output_path}")
