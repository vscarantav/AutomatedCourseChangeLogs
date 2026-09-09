import os
import sys
import unittest


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from emailer import build_email_body
from main import get_test_recipient


class EmailDeliveryTests(unittest.TestCase):
    def test_all_testing_delivery_uses_configured_test_recipient(self):
        config = {"test_email": "tav20001@byui.edu"}

        self.assertEqual(get_test_recipient(config), "tav20001@byui.edu")

    def test_missing_test_recipient_fails_closed(self):
        self.assertIsNone(get_test_recipient({}))
        self.assertIsNone(get_test_recipient({"test_email": "  "}))

    def test_email_greeting_uses_course_designer_name(self):
        body = build_email_body("Heidi E.")

        self.assertTrue(body.startswith("Hi Heidi E.,\n\n"))
        self.assertNotIn("{Designer Name}", body)


if __name__ == "__main__":
    unittest.main()
