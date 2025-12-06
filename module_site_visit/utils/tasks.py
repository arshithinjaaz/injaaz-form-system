import os
import json
import time
import traceback
import cloudinary.uploader
import redis
from rq import get_current_job

from .pdf_generator import generate_visit_pdf
from .email_sender import send_outlook_email

REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

def _set_report_status(visit_id, status_obj):
    key = f"report:{visit_id}"
    redis_client.set(key, json.dumps(status_obj))

def generate_and_send_report(visit_id, visit_info, items, output_dir):
    """
    Background job:
      - generate PDF from Cloudinary image URLs (items[*]['image_urls'])
      - upload PDF to Cloudinary (raw)
      - send email with attachment or link
      - save final status to Redis under key report:{visit_id}
    """
    job = get_current_job()
    try:
        _set_report_status(visit_id, {"status": "in_progress", "progress": "Starting PDF generation", "job_id": job.get_id()})

        # 1) Generate PDF (local file path)
        pdf_path, pdf_filename = generate_visit_pdf(visit_info, items, output_dir)

        _set_report_status(visit_id, {"status": "in_progress", "progress": "Uploading PDF to Cloudinary", "job_id": job.get_id()})

        # 2) Upload to Cloudinary as raw (resource_type='raw')
        upload_res = cloudinary.uploader.upload(
            pdf_path,
            resource_type='raw',
            folder='site_reports',
            public_id=f"{visit_id}_{int(time.time())}"
        )
        pdf_url = upload_res.get('secure_url')

        # 3) Try to send email (best-effort)
        try:
            subject = f"INJAAZ Site Visit Report for {visit_info.get('building_name','Unknown')}"
            body = f"Your site visit report is ready: {pdf_url}"
            send_outlook_email(subject, body, attachments=[pdf_path], recipient=visit_info.get('email'))
        except Exception as e:
            # Log email failure but continue
            print(f"WARNING: Email sending failed: {e}")

        # 4) Finalize status
        _set_report_status(visit_id, {"status": "done", "pdf_url": pdf_url, "filename": pdf_filename, "job_id": job.get_id()})

        # Optional: cleanup local pdf
        try:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
        except Exception:
            pass

    except Exception as e:
        tb = traceback.format_exc()
        print(f"ERROR in generate_and_send_report: {tb}")
        _set_report_status(visit_id, {"status": "failed", "error": str(e), "job_id": job.get_id()})
        raise