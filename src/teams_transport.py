import mimetypes
import os
import smtplib
from email.message import EmailMessage


SUBJECT_PREFIX = "[COURSE-CHANGE-TEAMS]"


def send_teams_transport_report(
    report_path: str,
    config: dict,
    recipient_email: str,
    subject: str | None = None,
) -> bool:
    """Email one HTML report to the mailbox that drives the Teams workflow.

    This is deliberately separate from designer email delivery. It fails closed
    unless Teams transport is explicitly enabled and the recipient exactly
    matches the configured Teams test recipient.
    """
    if not config.get("teams_transport_enabled", False):
        raise RuntimeError("Teams transport email is disabled.")

    recipient = str(recipient_email or "").strip()
    allowed_recipient = str(config.get("teams_test_recipient") or "").strip()
    if not recipient or recipient.casefold() != allowed_recipient.casefold():
        raise ValueError("Recipient does not match TEAMS_TEST_RECIPIENT.")

    if not os.path.isfile(report_path):
        raise FileNotFoundError(report_path)
    if not report_path.lower().endswith(".html"):
        raise ValueError("Teams transport accepts HTML reports only.")

    sender_email = config.get("smtp_email")
    sender_password = config.get("smtp_password")
    if not sender_email or not sender_password:
        raise RuntimeError("SMTP_EMAIL and SMTP_PASSWORD are required.")

    filename = os.path.basename(report_path)
    message = EmailMessage()
    message["Subject"] = subject or f"{SUBJECT_PREFIX} {filename}"
    message["From"] = sender_email
    message["To"] = recipient
    message.set_content(
        "This message transports an automated course-change report to the "
        "Microsoft Teams delivery workflow. The attached HTML report is also "
        "the backup copy if the Teams workflow fails."
    )

    content_type, _ = mimetypes.guess_type(filename)
    maintype, subtype = (content_type or "text/html").split("/", 1)
    with open(report_path, "rb") as report_file:
        message.add_attachment(
            report_file.read(),
            maintype=maintype,
            subtype=subtype,
            filename=filename,
        )

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(message)

    return True
