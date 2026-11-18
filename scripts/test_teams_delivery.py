import argparse
import os
import sys


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from config_loader import load_config
from teams_transport import send_teams_transport_report


def parse_args():
    parser = argparse.ArgumentParser(
        description="Send one guarded HTML report to the Teams email workflow."
    )
    parser.add_argument(
        "--report",
        default=os.path.join(ROOT_DIR, "reports", "Test 11-18.html"),
    )
    parser.add_argument(
        "--recipient",
        help="Must exactly match TEAMS_TEST_RECIPIENT from .env.",
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="Actually send. Without this flag, only validate and print the plan.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    report_path = os.path.abspath(args.report)
    if not os.path.isfile(report_path):
        raise FileNotFoundError(report_path)

    config = load_config(ROOT_DIR)
    allowed_recipient = config.get("teams_test_recipient")
    if not allowed_recipient:
        raise RuntimeError("Set TEAMS_TEST_RECIPIENT in .env before sending.")
    recipient = args.recipient or allowed_recipient
    config["teams_transport_enabled"] = args.send

    print(f"Report: {report_path}")
    print(f"Recipient: {recipient}")
    print("Designer email delivery: disabled")
    if not args.send:
        print("Dry run only. Re-run with --send to deliver one transport email.")
        return

    send_teams_transport_report(report_path, config, recipient)
    print("Teams transport email sent successfully.")


if __name__ == "__main__":
    main()
