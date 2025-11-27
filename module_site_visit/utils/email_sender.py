# module_site_visit/utils/email_sender.py

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# --- HARDCODED RECIPIENT LIST (The only addresses that receive the email) ---
INTERNAL_RECIPIENTS = ["arshith@injaaz.ae"]
# -----------------------------------------------------------------------------

# --- CONFIGURATION (Reads secure credentials from Render Environment Variables) ---
# IMPORTANT: You MUST set these three variables in your Render Environment dashboard.
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.office365.com") # Example for Office 365
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587)) 
SMTP_USERNAME = os.environ.get("SMTP_USERNAME") # Your sender email (e.g., info@yourdomain.com)
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD") # The App Password for the sender email
# --------------------------------------------------------------------------------

def send_outlook_email(subject, body, attachments=None, to_address=None):
    """
    Sends email via SMTP (cross-platform) to INTERNAL_RECIPIENTS.
    The client's address (to_address) is ignored for primary sending but is used 
    to add context to the email body.
    """
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        error_msg = "SMTP credentials (USERNAME/PASSWORD) are missing in Render environment variables."
        print(f"ERROR: {error_msg}")
        return False, error_msg

    try:
        # Create a multipart message object
        msg = MIMEMultipart()
        msg['From'] = SMTP_USERNAME
        msg['To'] = "; ".join(INTERNAL_RECIPIENTS)
        msg['Subject'] = subject

        # Append client info to the body for context (since we're only emailing internally)
        client_email_info = f"\nClient Email (For Reference): {to_address if to_address and to_address.strip() else 'N/A'}"
        full_body = body + client_email_info
        
        # Attach the body text
        msg.attach(MIMEText(full_body, 'plain'))

        # Handle attachments list
        if attachments:
            for file_path in attachments:
                if os.path.exists(file_path):
                    part = MIMEBase('application', 'octet-stream')
                    with open(file_path, 'rb') as file:
                        part.set_payload(file.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(file_path)}"')
                    msg.attach(part)
                else:
                    print(f"Attachment file not found: {file_path}")

        # Connect to the SMTP Server
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()  # Upgrade connection to secure TLS
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        
        # Send the email
        text = msg.as_string()
        server.sendmail(SMTP_USERNAME, INTERNAL_RECIPIENTS, text)
        server.quit()
        
        return True, f"Email sent successfully via SMTP to internal list: {msg['To']}."

    except Exception as e:
        error_msg = f"Email sending failed (SMTP error): {e}"
        print(f"ERROR: {error_msg}")
        return False, error_msg