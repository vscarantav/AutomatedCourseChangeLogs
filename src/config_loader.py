import os
import json
from dotenv import load_dotenv

def load_config(root_dir: str):
    """Loads configuration from environment variables and courses from data/courses.json"""
    load_dotenv(os.path.join(root_dir, '.env'))
    
    config = {
        "smtp_email": os.getenv("SMTP_EMAIL", os.getenv("OUTLOOK_EMAIL")),
        "smtp_password": os.getenv("SMTP_PASSWORD", os.getenv("OUTLOOK_PASSWORD")),
        "shareholders_emails": [e.strip() for e in os.getenv("SHAREHOLDERS_EMAILS", "").split(",") if e.strip()],
        "test_email": os.getenv("TEST_EMAIL"),
        "courses": []
    }
    
    courses_path = os.path.join(root_dir, 'data', 'courses.json')
    try:
        with open(courses_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            config["courses"] = data.get("courses", [])
    except FileNotFoundError:
        print(f"Warning: {courses_path} not found.")
        
    return config
