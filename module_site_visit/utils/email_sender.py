import pythoncom
import win32com.client as win32
import os

# --- HARDCODED RECIPIENT LIST (The only addresses that receive the email) ---
INTERNAL_RECIPIENTS = ["arshith@injaaz.ae"]
# Note: You can add as many addresses as you need to this list.
# -----------------------------------------------------------------------------


def send_outlook_email(subject, body, attachments=None, to_address=None):
    """
    Sends Outlook email ONLY to the hardcoded INTERNAL_RECIPIENTS list.
    The client's address (to_address) is ignored for sending but is used 
    to add context to the email body.
    """

    try:
        pythoncom.CoInitialize() 

        # --- Recipient String Creation ---
        # Join all internal emails into a semicolon-separated string for Outlook
        internal_to_string = "; ".join(INTERNAL_RECIPIENTS)

        # --- Outlook Object Creation ---
        outlook = win32.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)

        # Set the main recipient to the internal list
        mail.To = internal_to_string 
        
        # We can append the client's email to the body so the internal team knows 
        # who was meant to receive it.
        client_email_info = f"\nClient Email (For Reference): {to_address if to_address and to_address.strip() else 'N/A'}"
        
        mail.Subject = subject
        mail.Body = body + client_email_info # Append client email reference
        # mail.CC is left empty

        # Handle attachments list
        if attachments:
            for file_path in attachments:
                if os.path.exists(file_path):
                    try:
                        mail.Attachments.Add(file_path)
                    except Exception as e:
                        print(f"Attachment failed: {file_path} -> {e}")
                else:
                    print(f"Attachment file not found: {file_path}")

        # mail.Display() # Use this to test if the recipient list works
        mail.Send()
        
        return True, f"Email sent successfully to internal list: {internal_to_string}."

    except Exception as e:
        return False, f"Email sending failed (Outlook error): {e}"

    finally:
        pythoncom.CoUninitialize()