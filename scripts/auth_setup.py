import os
from playwright.sync_api import sync_playwright

def setup_auth():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(root_dir, 'data')
    os.makedirs(data_dir, exist_ok=True)
    state_path = os.path.join(data_dir, 'state.json')
    
    with sync_playwright() as p:
        # Launch non-headless browser so user can login manually
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        print("Opening Canvas Login page. Please log in manually.")
        page.goto("https://byui.instructure.com/login/canvas")
        
        # Wait for the user to login and navigate to dashboard
        input("Press Enter here in the terminal once you have successfully logged in and see your dashboard...")
        
        # Save the session cookies and state
        context.storage_state(path=state_path)
        print(f"Auth state saved successfully to {state_path}")
        browser.close()

if __name__ == "__main__":
    setup_auth()
