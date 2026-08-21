import smtplib
from email.message import EmailMessage

def send_report(subject: str, markdown_content: str, config: dict):
    """
    Sends the markdown report via Outlook SMTP.
    """
    sender_email = config.get("outlook_email")
    sender_password = config.get("outlook_password")
    recipients = config.get("shareholders_emails")
    
    if not sender_email or not sender_password or not recipients:
        print("Email configuration is incomplete. Skipping email notification.")
        return
        
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = ", ".join(recipients)
    
    # Simple plain text email, though markdown is quite readable
    msg.set_content(markdown_content)
    
    print(f"Sending email to {recipients}...")
    try:
        # Outlook SMTP settings
        with smtplib.SMTP('smtp-mail.outlook.com', 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        print("Email sent successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")
