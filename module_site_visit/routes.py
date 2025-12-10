import os
import logging
import json
import time
import traceback
import tempfile
from datetime import datetime
from flask import Blueprint, render_template, jsonify, request, url_for, send_from_directory

# Cloudinary SDK (we'll initialize lazily)
import cloudinary
import cloudinary.uploader
import cloudinary.api

# Redis + RQ (initialized lazily)
import redis
from rq import Queue
from redis.exceptions import RedisError

# --- CORE IMPORTS ---
from .utils.email_sender import send_outlook_email
from .utils.excel_writer import create_report_workbook
# IMPORTANT: pdf_generator is updated to stream URLs rather than expect local files
from .utils.pdf_generator import generate_visit_pdf
# Note: background task will be imported on-demand where required

# --- CONFIGURATION (Loaded from environment variables; DO NOT hardcode secrets in production) ---
CLOUDINARY_UPLOAD_PRESET = os.environ.get('CLOUDINARY_UPLOAD_PRESET', 'render_site_upload')

logger = logging.getLogger(__name__)

# NOTE: Do not perform network connections at import time.
# Instead, define lazy initializer / getter functions below.

def init_cloudinary():
    """
    Lazily configure Cloudinary. Safe to call multiple times.
    Returns True if configured, False otherwise.
    """
    if getattr(init_cloudinary, "_configured", None) is not None:
        return init_cloudinary._configured

    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME', '')
    api_key = os.environ.get('CLOUDINARY_API_KEY', '')
    api_secret = os.environ.get('CLOUDINARY_API_SECRET', '')

    if not cloud_name or not api_key or not api_secret:
        logger.warning("Cloudinary env vars missing; server-side uploads will likely fail.")
        init_cloudinary._configured = False
        return False

    try:
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret
        )
        init_cloudinary._configured = True
        logger.info("Cloudinary initialized.")
        return True
    except Exception:
        logger.exception("Cloudinary initialization failed.")
        init_cloudinary._configured = False
        return False

def get_redis_conn():
    """
    Lazily return a Redis connection (cached). Returns None if not available.
    Safe to call multiple times.
    """
    if getattr(get_redis_conn, "_conn", None) is not None:
        return get_redis_conn._conn

    redis_url = os.environ.get('REDIS_URL')
    if not redis_url:
        logger.warning("REDIS_URL not set; background jobs will not run.")
        get_redis_conn._conn = None
        return None

    try:
        conn = redis.from_url(redis_url, socket_connect_timeout=5, decode_responses=True)
        # Try a quick ping to validate connectivity
        conn.ping()
        get_redis_conn._conn = conn
        logger.info(f"Connected to Redis: {redis_url.split('@')[-1] if '@' in redis_url else redis_url}")
        return conn
    except RedisError:
        logger.exception("Failed to connect to Redis (lazy init). Background jobs disabled.")
        get_redis_conn._conn = None
        return None
    except Exception:
        logger.exception("Unexpected error connecting to Redis.")
        get_redis_conn._conn = None
        return None

def get_rq_queue():
    """
    Lazily return an RQ Queue bound to the Redis connection, or None if Redis unavailable.
    """
    if getattr(get_rq_queue, "_queue", None) is not None:
        return get_rq_queue._queue

    conn = get_redis_conn()
    if conn is None:
        get_rq_queue._queue = None
        return None

    try:
        q = Queue('default', connection=conn)
        get_rq_queue._queue = q
        return q
    except Exception:
        logger.exception("Failed to create RQ queue with Redis connection.")
        get_rq_queue._queue = None
        return None

# --- Utility: Cloudinary upload helper that uses lazy init
def upload_base64_to_cloudinary(base64_string, public_id_prefix):
    """
    Uploads a base64 string (signature) directly to Cloudinary and returns the secure URL.
    Accepts data URI (data:image/png;base64,....) or raw base64.
    """
    if not base64_string:
        return None

    if not init_cloudinary():
        logger.warning("Cloudinary not configured; skipping upload.")
        return None

    try:
        upload_result = cloudinary.uploader.upload(
            file=base64_string,
            folder="signatures",
            public_id=f"{public_id_prefix}_{int(time.time())}"
        )
        return upload_result.get('secure_url')
    except Exception as e:
        logger.exception(f"Cloudinary signature upload failed for {public_id_prefix}: {e}")
        return None

# =================================================================
# --- TEMPORARY STATE MANAGEMENT (Placeholder) ---
# =================================================================
def save_report_state(report_id, data):
    temp_record_path = os.path.join(tempfile.gettempdir(), f"{report_id}.json")
    with open(temp_record_path, 'w') as f:
        json.dump(data, f)

def get_report_state(report_id):
    temp_record_path = os.path.join(tempfile.gettempdir(), f"{report_id}.json")
    if not os.path.exists(temp_record_path):
        return None
    try:
        with open(temp_record_path, 'r') as f:
            record = json.load(f)
        return record
    finally:
        # Keep behavior consistent with original: remove after reading
        if os.path.exists(temp_record_path):
            os.remove(temp_record_path)

# =================================================================
# --- PATH AND BLUEPRINT CONFIGURATION ---
# =================================================================
BLUEPRINT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(BLUEPRINT_DIR)

TEMPLATE_ABSOLUTE_PATH = os.path.join(BLUEPRINT_DIR, 'templates')
DROPDOWN_DATA_PATH = os.path.join(BLUEPRINT_DIR, 'dropdown_data.json')

GENERATED_DIR_NAME = "generated"
GENERATED_DIR = os.path.join(BASE_DIR, GENERATED_DIR_NAME)

site_visit_bp = Blueprint(
    'site_visit_bp',
    __name__,
    template_folder=TEMPLATE_ABSOLUTE_PATH,
    static_folder='static'
)

# ========== Routes ==========
@site_visit_bp.route('/form')
def index():
    return render_template('site_visit_form.html')

@site_visit_bp.route('/dropdowns')
def get_dropdown_data():
    try:
        with open(DROPDOWN_DATA_PATH, 'r') as f:
            data = json.load(f)
        return jsonify(data)
    except FileNotFoundError:
        logger.error(f"Dropdown data file not found at: {DROPDOWN_DATA_PATH}")
        return jsonify({"error": "Dropdown data file not found"}), 404
    except json.JSONDecodeError:
        logger.error(f"Could not decode JSON: {DROPDOWN_DATA_PATH}")
        return jsonify({"error": "Invalid JSON data"}), 500

# 3. Metadata submit route (uploads signatures)
@site_visit_bp.route('/api/submit/metadata', methods=['POST'])
def submit_metadata():
    """
    Accepts visit metadata + signatures. Returns a visit_id and cloudinary info
    that the client uses to upload photos/signatures. This version is robust
    when Cloudinary env vars are missing: it still returns a visit_id and the
    cloudinary_cloud_name field (possibly empty), so the client can handle it.
    """
    try:
        data = request.json or {}
        visit_info = data.get('visit_info', {})
        processed_items = data.get('report_items', [])
        signatures = data.get('signatures', {})

        # Create a stable visit id regardless of Cloudinary availability
        report_id = f"report-{int(time.time())}"

        # Attempt signature uploads if Cloudinary is configured
        tech_sig = signatures.get('tech_signature')
        opman_sig = signatures.get('opMan_signature')

        tech_sig_url = None
        opMan_sig_url = None

        try:
            if init_cloudinary():
                tech_sig_url = upload_base64_to_cloudinary(tech_sig, 'tech_sig') if tech_sig else None
                opMan_sig_url = upload_base64_to_cloudinary(opman_sig, 'opman_sig') if opman_sig else None
            else:
                logger.warning("Cloudinary not configured; signature uploads skipped.")
        except Exception as e:
            logger.exception("Signature upload attempt failed: %s", e)

        visit_info['tech_signature_url'] = tech_sig_url
        visit_info['opMan_signature_url'] = opMan_sig_url

        # Persist minimal state for later steps
        save_report_state(report_id, {
            'visit_info': visit_info,
            'report_items': processed_items,
            'photo_urls': []
        })

        # Always return cloudinary fields (possibly empty) and visit id so front-end can proceed
        cloudinary_name = os.environ.get('CLOUDINARY_CLOUD_NAME', '')
        upload_preset = os.environ.get('CLOUDINARY_UPLOAD_PRESET', CLOUDINARY_UPLOAD_PRESET)

        return jsonify({
            "status": "success",
            "visit_id": report_id,
            "cloudinary_cloud_name": cloudinary_name,
            "cloudinary_upload_preset": upload_preset,
        })

    except Exception as e:
        error_details = traceback.format_exc()
        logger.exception("ERROR (Metadata): %s", error_details)
        return jsonify({"error": f"Failed to process metadata: {str(e)}"}), 500

# 4. Update photos route (receives client-side uploaded Cloudinary URLs)
@site_visit_bp.route('/api/submit/update-photos', methods=['POST'])
def update_photos():
    report_id = request.args.get('visit_id')
    if not report_id:
        return jsonify({"error": "Missing visit_id"}), 400

    record = get_report_state(report_id)
    if not record:
        return jsonify({"error": "Report record not found (Server restarted or session expired)."}), 500

    try:
        data = request.json
        photo_urls = data.get('photo_urls', [])
        record['photo_urls'] = photo_urls
        save_report_state(report_id, record)
        return jsonify({"status": "success"})
    except Exception as e:
        error_details = traceback.format_exc()
        logger.exception(f"ERROR (Update Photos): {error_details}")
        return jsonify({"error": f"Failed to update photo URLs: {str(e)}"}), 500

# 5. Finalize and generate report (enqueue background job for PDF + Excel + email)
@site_visit_bp.route('/api/submit/finalize', methods=['GET'])
def finalize_report():
    report_id = request.args.get('visit_id')
    if not report_id:
        return jsonify({"error": "Missing visit_id parameter for finalization."}), 400

    record = get_report_state(report_id)
    if not record:
        return jsonify({"error": "Report record not found (Server restarted or session expired)."}), 500

    try:
        visit_info = record.get('visit_info', {})
        final_items = record.get('report_items', [])
        final_photo_urls = record.get('photo_urls', [])

        # Normalize visit_info
        if isinstance(visit_info, str):
            try:
                visit_info = json.loads(visit_info)
            except Exception:
                visit_info = {"raw_visit_info": visit_info}

        if visit_info is None:
            visit_info = {}

        email_recipient = visit_info.get('email')

        # Build URL map
        url_map = {}
        for url_data in final_photo_urls:
            try:
                key = (int(url_data.get('item_index', 0)), int(url_data.get('photo_index', 0)))
                url_map[key] = url_data.get('photo_url')
            except Exception:
                continue

        for item_index, item in enumerate(final_items):
            image_urls = []
            for photo_index in range(int(item.get('photo_count', 0))):
                key = (item_index, photo_index)
                photo_url = url_map.get(key)
                if photo_url:
                    image_urls.append(photo_url)
                else:
                    logger.warning(f"Missing photo URL for item {item_index}, photo {photo_index}. Key: {key}")

            item['image_urls'] = image_urls
            item.pop('photo_count', None)

        os.makedirs(GENERATED_DIR, exist_ok=True)

        # Create Excel synchronously
        excel_path, excel_filename = create_report_workbook(GENERATED_DIR, visit_info, final_items)

        # Attempt to get an RQ queue lazily
        q = get_rq_queue()

        if q is None:
            # Fallback: synchronous generation (not ideal in production)
            logger.warning("Redis/RQ not available. Generating PDF synchronously.")
            pdf_path, pdf_filename = generate_visit_pdf(visit_info, final_items, GENERATED_DIR)

            subject = f"INJAAZ Site Visit Report for {visit_info.get('building_name', 'Unknown')} - {datetime.now().strftime('%Y-%m-%d')}"
            body = f"The site visit report for {visit_info.get('building_name', 'Unknown')} on {datetime.now().strftime('%Y-%m-%d')} has been generated and is attached."

            attachments = [p for p in [excel_path, pdf_path] if p and os.path.exists(p)]
            try:
                email_status, msg = send_outlook_email(subject, body, attachments, email_recipient)
                logger.info("EMAIL_STATUS: %s", msg)
            except Exception as e:
                logger.exception("Email sending failed in synchronous fallback: %s", e)

            return jsonify({
                "status": "success",
                "excel_url": url_for('site_visit_bp.download_generated', filename=excel_filename, _external=True),
                "pdf_url": url_for('site_visit_bp.download_generated', filename=pdf_filename, _external=True)
            })

        # Enqueue job if queue is available
        try:
            from .utils.tasks import generate_and_send_report
        except Exception:
            logger.exception("CRITICAL ERROR: Could not import background task generate_and_send_report.")
            raise

        try:
            job = q.enqueue(
                generate_and_send_report,
                report_id,
                visit_info,
                final_items,
                GENERATED_DIR,
                job_timeout=1800  # 30 minutes
            )
        except Exception:
            logger.exception("Failed to enqueue generate_and_send_report job.")
            raise

        # Store initial status in Redis if available
        conn = get_redis_conn()
        try:
            if conn is not None:
                conn.set(f"report:{report_id}", json.dumps({"status": "pending", "job_id": job.get_id()}))
        except Exception:
            logger.exception("Could not set initial report status in Redis.")

        return jsonify({
            "status": "accepted",
            "visit_id": report_id,
            "job_id": job.get_id(),
            "status_url": url_for('site_visit_bp.report_status', visit_id=report_id, _external=True)
        }), 202

    except Exception as e:
        error_details = traceback.format_exc()
        logger.exception(f"ERROR (Finalize): {error_details}")
        return jsonify({
            "status": "error",
            "error": f"Internal server error: Failed to process report. Reason: {type(e).__name__}: {str(e)}"
        }), 500

# 6. Report status endpoint to poll background job progress/result
@site_visit_bp.route('/api/report-status', methods=['GET'])
def report_status():
    visit_id = request.args.get('visit_id')
    if not visit_id:
        return jsonify({"error": "Missing visit_id"}), 400

    conn = get_redis_conn()
    if conn is None:
        return jsonify({"status": "error", "message": "Redis not configured on server."}), 500

    key = f"report:{visit_id}"
    result = conn.get(key)
    if not result:
        return jsonify({"status": "unknown", "message": "No record found. The job may not have been started."}), 404

    try:
        data = json.loads(result)
        return jsonify({"status": "ok", "report": data})
    except Exception:
        return jsonify({"status": "ok", "report_raw": result})

# 7. Serve generated files
@site_visit_bp.route('/generated/<path:filename>')
def download_generated(filename):
    return send_from_directory(GENERATED_DIR, filename, as_attachment=True)