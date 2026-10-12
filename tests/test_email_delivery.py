import os
import sys
import unittest


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from emailer import build_email_body
from main import get_designer_recipient, week_start_date


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


if __name__ == "__main__":
    unittest.main()
