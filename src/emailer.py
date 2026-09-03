import smtplib
from email.message import EmailMessage
import os

def send_report(subject: str, html_content: str, report_path: str, config: dict):
    """
    Sends the HTML report via Outlook SMTP as an attachment, with a brief summary in the body.
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
    
    body = f"Hello,\n\nThe Canvas course change logs for the week are attached. Please download and open the attached HTML file in your web browser to view the interactive dashboard and detailed diffs.\n\nBest,\nAutomated Course Change Logs Bot"
    msg.set_content(body)
    
    # Attach the HTML file
    if os.path.exists(report_path):
        with open(report_path, 'rb') as f:
            file_data = f.read()
            msg.add_attachment(file_data, maintype='text', subtype='html', filename=os.path.basename(report_path))
    
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
