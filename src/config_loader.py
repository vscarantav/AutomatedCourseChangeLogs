import os
import json
from dotenv import load_dotenv


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_config(root_dir: str):
    """Loads configuration from environment variables and courses from data/courses.json"""
    load_dotenv(os.path.join(root_dir, '.env'))
    
    config = {
        "smtp_email": os.getenv("SMTP_EMAIL", os.getenv("OUTLOOK_EMAIL")),
        "smtp_password": os.getenv("SMTP_PASSWORD", os.getenv("OUTLOOK_PASSWORD")),
        "shareholders_emails": [e.strip() for e in os.getenv("SHAREHOLDERS_EMAILS", "").split(",") if e.strip()],
        "test_email": os.getenv("TEST_EMAIL"),
        # Designer email is retained as a backup path but is fail-closed by default.
        "email_delivery_enabled": _env_flag("EMAIL_DELIVERY_ENABLED", False),
        # Teams transport emails have a separate, explicit enable switch.
        "teams_transport_enabled": _env_flag("TEAMS_TRANSPORT_ENABLED", False),
        "teams_test_recipient": os.getenv("TEAMS_TEST_RECIPIENT"),
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
