import os
import time
from playwright.sync_api import sync_playwright

def download_course_export(course, root_dir: str, year_week: str):
    """
    course: dict with 'id' and 'url'
    Downloads IMSCC for the given course and year_week.
    Returns the path to the downloaded file.
    """
    state_path = os.path.join(root_dir, 'data', 'state.json')
    if not os.path.exists(state_path):
        raise Exception("Authentication state not found. Please run scripts/auth_setup.py first.")
        
    export_dir = os.path.join(root_dir, 'exports', course['id'], year_week)
    os.makedirs(export_dir, exist_ok=True)
    
    with sync_playwright() as p:
        # Run headless for background execution
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=state_path, accept_downloads=True)
        page = context.new_page()
        
        try:
            # Navigate to the export page directly
            export_url = f"{course['url'].rstrip('/')}/content_exports"
            print(f"Navigating to {export_url}")
            page.goto(export_url, timeout=60000)
            
            # Ensure "Course" export type is selected (usually default)
            # Click "Create Export"
            print(f"Triggering new export for course {course['id']}...")
            try:
                page.click("input[value='Create Export'], button:has-text('Create Export')", timeout=10000)
            except Exception as e:
                print(f"Could not find 'Create Export' button. It might already be exporting or page structure changed: {e}")
                
            # Wait for the export to finish. This can take several minutes.
            print("Waiting for export to complete. This may take a while...")
            
            # Look for the "New Export" download link that appears when done
            download_link_selector = "a:has-text('New Export'), a[class*='download']"
            page.wait_for_selector(download_link_selector, timeout=300000) # 5 mins timeout
            
            print("Export complete. Downloading file...")
            with page.expect_download(timeout=120000) as download_info:
                page.click(download_link_selector)
            
            download = download_info.value
            file_name = download.suggested_filename or f"export_{course['id']}_{year_week}.imscc"
            file_path = os.path.join(export_dir, file_name)
            
            download.save_as(file_path)
            print(f"Successfully downloaded to {file_path}")
            
            return file_path
            
        except Exception as e:
            print(f"Failed to download export for course {course['id']}: {e}")
            return None
        finally:
            browser.close()
