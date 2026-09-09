import smtplib
from email.message import EmailMessage
import os


def build_email_body(designer_name):
    greeting_name = str(designer_name).strip() if designer_name else "Course Designer"
    return (
        f"Hi {greeting_name},\n\n"
        "The Canvas course change logs for the week are attached for your review. "
        "Please reach out if you have any questions.\n\n"
        "Best,\n"
        "Vinicius Tavares"
    )


def send_report(
    subject: str,
    html_content: str,
    report_path: str,
    config: dict,
    recipient_email: str = None,
    designer_name: str = None,
):
    """
    Sends the HTML report via SMTP as an attachment, with a brief summary in the body.
    """
    sender_email = config.get("smtp_email")
    sender_password = config.get("smtp_password")
    
    # If a specific recipient is provided, use it. Otherwise, fallback to the list of shareholders
    if recipient_email:
        recipients = [recipient_email]
    else:
        recipients = config.get("shareholders_emails", [])
    
    if not sender_email or not sender_password or not recipients:
        print("Email configuration is incomplete. Skipping email notification.")
        return
        
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = ", ".join(recipients)
    
    msg.set_content(build_email_body(designer_name))
    
    # Zip and attach the HTML file to bypass strict enterprise email filters
    if os.path.exists(report_path):
        import zipfile
        zip_path = report_path.replace('.html', '.zip')
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(report_path, os.path.basename(report_path))
            
        with open(zip_path, 'rb') as f:
            file_data = f.read()
            msg.add_attachment(file_data, maintype='application', subtype='zip', filename=os.path.basename(zip_path))
            
        # Clean up the zip file after reading
        try:
            os.remove(zip_path)
        except Exception:
            pass
    
    print(f"Sending email to {recipients}...")
    try:
        # Gmail SMTP settings
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        print("Email sent successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")
