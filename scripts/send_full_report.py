"""Runs the weekly pipeline and emails the all-courses report to one recipient.

Designer delivery is suppressed: main's send_report is replaced before main()
runs, so no personalized report leaves the machine.
"""
import argparse
import os
import sys

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_path = os.path.join(root_dir, 'src')
scripts_path = os.path.join(root_dir, 'scripts')

if src_path not in sys.path:
    sys.path.insert(0, src_path)
if scripts_path not in sys.path:
    sys.path.insert(0, scripts_path)

# pyrefly: ignore [missing-import]
import fetch_exports
# pyrefly: ignore [missing-import]
import main as main_module
# pyrefly: ignore [missing-import]
from config_loader import load_config
# pyrefly: ignore [missing-import]
from emailer import send_report


def suppress_designer_emails():
    def _skip(subject, html_content, report_path, config, recipient_email=None, designer_name=None):
        print(f"  Suppressed designer email ({designer_name} <{recipient_email}>).")

    main_module.send_report = _skip


def run(recipient, fetch=True):
    if fetch:
        print("Fetching today's Canvas exports...")
        fetch_exports.main()

    suppress_designer_emails()

    print("\nGenerating course change reports...")
    main_module.main()

    report_date = main_module.week_start_date().strftime("%Y-%m-%d")
    report_path = os.path.join(root_dir, 'reports', f"report_{report_date}.html")
    if not os.path.exists(report_path):
        print(f"Error: {report_path} was not generated. No email sent.")
        return 1

    with open(report_path, 'r', encoding='utf-8') as f:
        report_html = f.read()

    send_report(
        f"Canvas Course Changes (All Courses) - {report_date}",
        report_html,
        report_path,
        load_config(root_dir),
        recipient_email=recipient,
        designer_name="Vinicius",
    )
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--to', required=True, help='The only address that receives the report.')
    parser.add_argument('--skip-fetch', action='store_true', help='Reuse the exports already on disk.')
    args = parser.parse_args()

    sys.exit(run(args.to, fetch=not args.skip_fetch))
