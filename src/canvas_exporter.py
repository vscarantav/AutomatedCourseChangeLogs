import os
import time
from urllib.parse import quote

import requests
from dotenv import load_dotenv

load_dotenv()

CANVAS_API_KEY = os.getenv("CANVAS_API_KEY")
CANVAS_API_URL = os.getenv("CANVAS_API_URL", "https://canvas.instructure.com")
CONNECT_TIMEOUT = 15
READ_TIMEOUT = 60
LIST_READ_TIMEOUT = 20
DOWNLOAD_READ_TIMEOUT = 180
MAX_REQUEST_ATTEMPTS = 3


def _canvas_request(method, url, **kwargs):
    """Makes a bounded Canvas request and retries transient failures."""
    kwargs.setdefault("timeout", (CONNECT_TIMEOUT, READ_TIMEOUT))

    for attempt in range(1, MAX_REQUEST_ATTEMPTS + 1):
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except (requests.Timeout, requests.ConnectionError):
            if attempt == MAX_REQUEST_ATTEMPTS:
                raise
            time.sleep(attempt * 2)

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
    
    response = _canvas_request("POST", url, headers=headers, data=data)
    return response.json()

def check_export_status(course_id, export_id):
    """
    Checks the status of an export.
    """
    url = f"{CANVAS_API_URL}/api/v1/courses/{course_id}/content_exports/{export_id}"
    headers = {
        "Authorization": f"Bearer {CANVAS_API_KEY}"
    }
    
    response = _canvas_request("GET", url, headers=headers)
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
    
    response = requests.get(
        url,
        headers=headers,
        timeout=(CONNECT_TIMEOUT, LIST_READ_TIMEOUT)
    )
    if response.status_code == 404:
        return []
    response.raise_for_status()
    return response.json()


def get_page_revisions(course_id, page_url):
    """Returns every revision for a Canvas course page."""
    encoded_page_url = quote(str(page_url), safe="")
    next_url = (
        f"{CANVAS_API_URL}/api/v1/courses/{course_id}/pages/"
        f"{encoded_page_url}/revisions"
    )
    params = {"per_page": 100}
    headers = {"Authorization": f"Bearer {CANVAS_API_KEY}"}
    revisions = []

    while next_url:
        response = _canvas_request(
            "GET",
            next_url,
            headers=headers,
            params=params,
        )
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("Canvas page revisions response was not a list.")

        revisions.extend(payload)
        next_url = response.links.get("next", {}).get("url")
        params = None

    return revisions


def _get_paginated_array(url, params=None):
    """Returns every item from a Canvas endpoint whose payload is a JSON array."""
    headers = {"Authorization": f"Bearer {CANVAS_API_KEY}"}
    items = []
    next_url = url
    next_params = dict(params or {})
    next_params.setdefault("per_page", 100)

    while next_url:
        response = _canvas_request(
            "GET",
            next_url,
            headers=headers,
            params=next_params,
        )
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("Canvas list response was not a JSON array.")
        items.extend(payload)
        next_url = response.links.get("next", {}).get("url")
        next_params = None

    return items


def get_course_files(course_id):
    """Returns course files with uploader/last-content-editor metadata."""
    url = f"{CANVAS_API_URL}/api/v1/courses/{course_id}/files"
    return _get_paginated_array(url, {"include[]": "user"})


def get_course_folders(course_id):
    """Returns course folders so IMSCC file paths can be matched exactly."""
    url = f"{CANVAS_API_URL}/api/v1/courses/{course_id}/folders"
    return _get_paginated_array(url)


def get_discussion_topics(course_id):
    """Returns course discussion topics, including each topic creator name."""
    url = f"{CANVAS_API_URL}/api/v1/courses/{course_id}/discussion_topics"
    return _get_paginated_array(url)


def get_course_audit_events(course_id, start_time, end_time):
    """Returns course-record audit events and linked users for a time window."""
    headers = {"Authorization": f"Bearer {CANVAS_API_KEY}"}
    next_url = f"{CANVAS_API_URL}/api/v1/audit/course/courses/{course_id}"
    params = {
        "start_time": start_time,
        "end_time": end_time,
        "per_page": 100,
    }
    events = []
    users = {}

    while next_url:
        response = _canvas_request(
            "GET",
            next_url,
            headers=headers,
            params=params,
        )
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Canvas course audit response was not a JSON object.")

        events.extend(payload.get("events", []))
        for user in payload.get("linked", {}).get("users", []):
            user_id = user.get("id")
            if user_id is not None:
                users[str(user_id)] = user

        next_url = payload.get("links", {}).get("next")
        params = None

    return {"events": events, "users": users}

def save_download(download_url, output_path):
    """
    Downloads the file from the given URL and saves it to output_path.
    """
    print(f"Downloading file to {output_path}...")
    response = _canvas_request(
        "GET",
        download_url,
        stream=True,
        timeout=(CONNECT_TIMEOUT, DOWNLOAD_READ_TIMEOUT)
    )
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    partial_path = f"{output_path}.part"
    try:
        with open(partial_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        os.replace(partial_path, output_path)
    finally:
        response.close()
        if os.path.exists(partial_path):
            os.remove(partial_path)
            
    print(f"Download complete: {output_path}")
