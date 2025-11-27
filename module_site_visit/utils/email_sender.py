# module_site_visit/utils/email_sender.py

import os
# No external library imports (like smtplib or pythoncom)

# --- HARDCODED RECIPIENT LIST (Retained for future reference) ---
INTERNAL_RECIPIENTS = ["arshith@injaaz.ae"]
# -----------------------------------------------------------------------------

def send_outlook_email(subject, body, attachments=None, to_address=None):
    """
    DUMMY FUNCTION: This function is a placeholder to allow the application 
    to boot on the Linux server without crashing due to Windows-specific code.
    It simulates sending an email by printing a log message.
    """
    print("--- DUMMY EMAIL SENDER ACTIVATED ---")
    print(f"ATTEMPTED TO SEND EMAIL (SUBJECT: {subject})")
    print(f"Internal Recipients: {INTERNAL_RECIPIENTS}")
    print(f"Client Reference: {to_address}")
    if attachments:
        print(f"Attachments Count: {len(attachments)}")
    print("------------------------------------")
    
    # Always return True and a success message so the calling code proceeds
    return True, "Email sending bypassed to ensure cloud deployment success."