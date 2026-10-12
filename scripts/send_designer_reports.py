import os
import sys
import json
import tempfile
import datetime

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_path = os.path.join(root_dir, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from config_loader import load_config
from emailer import send_report


def week_start_date(day=None):
    day = day or datetime.date.today()
    return day - datetime.timedelta(days=day.weekday())


def get_designer_recipient(designer_email):
    if not designer_email:
        return None
    return str(designer_email).strip() or None


def main():
    config = load_config(root_dir)
    report_date = week_start_date().strftime("%Y-%m-%d")
    report_path = os.path.join(root_dir, 'reports', f"report_{report_date}.html")

    if not os.path.exists(report_path):
        print(f"Error: {report_path} not found.")
        sys.exit(1)

    with open(report_path, 'r', encoding='utf-8') as f:
        master_report_html = f.read()

    json_path = os.path.join(root_dir, "data", "courses.json")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    courses = data.get("courses", [])
    unique_designers = {}
    for c in courses:
        name = c.get("course_designer")
        email = c.get("designer_email")
        if name and email and name not in unique_designers:
            unique_designers[name] = email

    print(f"Found {len(unique_designers)} unique designers:")
    for name, email in unique_designers.items():
        print(f"  - {name} <{email}>")

    for designer_name, designer_email in unique_designers.items():
        recipient = get_designer_recipient(designer_email)
        if not recipient:
            print(f"No valid email for {designer_name}. Skipping.")
            continue

        print(f"\nPreparing filtered report for {designer_name} ({recipient})...")
        designer_html = master_report_html.replace(
            "dFilter.value = 'all';",
            f"dFilter.value = '{designer_name}';"
        ).replace(
            "filterDesigner('all');",
            f"filterDesigner('{designer_name}');"
        )

        safe_name = designer_name.replace(' ', '_').replace('.', '')
        with tempfile.TemporaryDirectory() as tmp_dir:
            designer_report_path = os.path.join(
                tmp_dir, f"report_{report_date}_{safe_name}.html"
            )
            with open(designer_report_path, 'w', encoding='utf-8') as f:
                f.write(designer_html)

            print(f"Sending email to {designer_name} <{recipient}>...")
            send_report(
                f"Canvas Course Changes - {report_date}",
                designer_html,
                designer_report_path,
                config,
                recipient_email=recipient,
                designer_name=designer_name,
            )

    print("\nAll designer reports sent successfully!")


if __name__ == "__main__":
    main()
