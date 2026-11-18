import os
import sys
import unittest
from unittest.mock import Mock, patch


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from emailer import build_email_body, send_report
from main import get_designer_recipient, week_start_date
from teams_transport import send_teams_transport_report


class EmailDeliveryTests(unittest.TestCase):
    def test_delivery_uses_the_designers_own_address(self):
        self.assertEqual(get_designer_recipient(" heidi@byui.edu "), "heidi@byui.edu")

    def test_missing_designer_email_fails_closed(self):
        self.assertIsNone(get_designer_recipient(None))
        self.assertIsNone(get_designer_recipient("  "))

    def test_email_greeting_uses_course_designer_name(self):
        body = build_email_body("Heidi E.")

        self.assertTrue(body.startswith("Hi Heidi E.,\n\n"))
        self.assertNotIn("{Designer Name}", body)

    def test_week_start_date_is_monday(self):
        import datetime

        wednesday = datetime.date(2026, 9, 10)
        self.assertEqual(week_start_date(wednesday), datetime.date(2026, 9, 7))
        self.assertEqual(week_start_date(datetime.date(2026, 9, 7)), datetime.date(2026, 9, 7))

    @patch("emailer.smtplib.SMTP")
    def test_designer_email_is_disabled_by_default(self, smtp):
        sent = send_report("Subject", "", "missing.html", {}, "designer@example.com")

        self.assertFalse(sent)
        smtp.assert_not_called()

    @patch("teams_transport.smtplib.SMTP")
    def test_teams_transport_is_limited_to_configured_recipient(self, smtp):
        smtp.return_value.__enter__.return_value = smtp_server = Mock()
        report_path = os.path.join(ROOT_DIR, "tests", "fixtures", "transport_test.html")
        sent = send_teams_transport_report(
            report_path,
            {
                "teams_transport_enabled": True,
                "teams_test_recipient": "owner@example.com",
                "smtp_email": "sender@example.com",
                "smtp_password": "secret",
            },
            "owner@example.com",
        )

        self.assertTrue(sent)
        smtp_server.send_message.assert_called_once()
        message = smtp_server.send_message.call_args.args[0]
        self.assertEqual(message["To"], "owner@example.com")
        self.assertEqual(message.get_filename(), None)
        self.assertEqual(message.iter_attachments().__next__().get_filename(), "transport_test.html")

    def test_teams_transport_rejects_other_recipient(self):
        with self.assertRaises(ValueError):
            send_teams_transport_report(
                "missing.html",
                {
                    "teams_transport_enabled": True,
                    "teams_test_recipient": "owner@example.com",
                },
                "someone-else@example.com",
            )


if __name__ == "__main__":
    unittest.main()
