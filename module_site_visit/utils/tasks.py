# module_site_visit/utils/tasks.py (serve PDF locally; no Cloudinary upload)
import os
import json
import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Import local generators
from .pdf_generator import generate_visit_pdf
from .excel_writer import create_report_workbook

# Email helper
from module_site_visit.utils.email_sender import send_outlook_email

# Ensure you can access redis_conn (import from routes or create it here)
try:
    from module_site_visit.routes import redis_conn
except Exception:
    import redis as _redis
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    redis_conn = _redis.from_url(REDIS_URL, decode_responses=True)


def _external_generated_url(filename):
    """Construct external URL for generated files served by Flask app."""
    base = os.environ.get('APP_BASE_URL', 'http://127.0.0.1:5002')
    return f"{base.rstrip('/')}/site-visit/generated/{filename}"


def generate_and_send_report(report_id, visit_info, final_items, generated_dir):
    """
    Background job: generate excel/pdf, do NOT upload PDF to Cloudinary (serve locally),
    update Redis status, and send email with links.
    """
    status_key = f"report:{report_id}"
    try:
        # Mark processing status early so the client can poll
        try:
            if redis_conn is not None:
                redis_conn.set(status_key, json.dumps({"status": "processing", "started_at": datetime.utcnow().isoformat()}))
        except Exception as e:
            logger.warning(f"Could not set processing status in Redis: {e}")

        # 1) Create Excel & PDF locally
        try:
            excel_path, excel_filename = create_report_workbook(generated_dir, visit_info, final_items)
            logger.info(f"Excel generated: {excel_path}")
        except Exception as e:
            err = f"Excel generation failed: {e}"
            logger.exception(err)
            if redis_conn is not None:
                redis_conn.set(status_key, json.dumps({"status": "failed", "error": err}))
            return

        # 2) Generate PDF locally (do not upload to Cloudinary)
        try:
            # request local-only PDF (upload_to_cloudinary=False)
            pdf_result = generate_visit_pdf(visit_info, final_items, generated_dir, upload_to_cloudinary=False)
            # pdf_result expected to be (pdf_path, pdf_filename)
            if isinstance(pdf_result, (list, tuple)) and len(pdf_result) == 2:
                pdf_path, pdf_filename = pdf_result
                logger.info(f"PDF generated: {pdf_path}")
                signed_pdf_url = None
            else:
                err = "pdf_generator returned unexpected result shape"
                logger.warning(err)
                if redis_conn is not None:
                    redis_conn.set(status_key, json.dumps({"status": "failed", "error": err}))
                return
        except Exception as e:
            err = f"PDF generation failed: {e}"
            logger.exception(err)
            if redis_conn is not None:
                redis_conn.set(status_key, json.dumps({"status": "failed", "error": err}))
            return

        # 3) Build public URLs for excel & pdf (serve both via Flask /generated route)
        excel_url = None
        pdf_url = None
        if excel_filename and excel_path and os.path.exists(excel_path):
            excel_url = _external_generated_url(excel_filename)
        if pdf_filename and pdf_path and os.path.exists(pdf_path):
            pdf_url = _external_generated_url(pdf_filename)

        # 4) Update final status in Redis
        final_status = {
            "status": "done" if pdf_url or excel_url else "failed",
            "pdf_url": pdf_url,
            "excel_url": excel_url,
            "completed_at": datetime.utcnow().isoformat()
        }
        try:
            if redis_conn is not None:
                redis_conn.set(status_key, json.dumps(final_status))
        except Exception as e:
            logger.warning(f"Could not set final status in Redis: {e}")

        # 5) Send email containing the links and attach local files if desired
        try:
            recipient = visit_info.get('email') if isinstance(visit_info, dict) else None
            subject = f"INJAAZ Site Visit Report - {visit_info.get('building_name','Unknown') if isinstance(visit_info, dict) else 'Unknown'}"
            body_lines = ["Your report has been generated."]
            if pdf_url:
                body_lines.append(f"Download PDF: {pdf_url}")
            if excel_url:
                body_lines.append(f"Download Excel: {excel_url}")
            body = "\n".join(body_lines)

            attachments = []
            if pdf_path and os.path.exists(pdf_path):
                attachments.append(pdf_path)
            if excel_path and os.path.exists(excel_path):
                attachments.append(excel_path)

            try:
                send_outlook_email(subject, body, attachments, recipient)
            except Exception as e:
                logger.warning(f"Email send failed: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error while preparing/sending email: {e}")

    except Exception as e:
        err = f"Report job error: {e}"
        logger.exception(err)
        try:
            if redis_conn is not None:
                redis_conn.set(status_key, json.dumps({"status": "failed", "error": err}))
        except Exception:
            pass