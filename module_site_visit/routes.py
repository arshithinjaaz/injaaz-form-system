import os
import json
import time
import traceback
import tempfile
from datetime import datetime
from flask import Blueprint, render_template, jsonify, request, url_for, send_from_directory

# NEW: Import the Cloudinary SDK
import cloudinary
import cloudinary.uploader
import cloudinary.api

# NEW: Redis + RQ for background jobs
import redis
from rq import Queue

# --- CORE IMPORTS ---
# Assuming these are relative imports from the module's sub-directories
from .utils.email_sender import send_outlook_email
from .utils.excel_writer import create_report_workbook
# IMPORTANT: pdf_generator is updated to stream URLs rather than expect local files
from .utils.pdf_generator import generate_visit_pdf

# --- CONFIGURATION (Loaded from environment variables; DO NOT hardcode secrets in production) ---
CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME', '')
CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY', '')
CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET', '')
CLOUDINARY_UPLOAD_PRESET = os.environ.get('CLOUDINARY_UPLOAD_PRESET', 'render_site_upload')

# Redis / RQ config
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# Validate config
if not CLOUDINARY_CLOUD_NAME or not CLOUDINARY_API_KEY or not CLOUDINARY_API_SECRET:
    print("WARNING: One or more Cloudinary environment variables are not set. "
          "Server-side Cloudinary upload may fail. Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET.")

# Initialize Cloudinary (required for server-side upload of signatures)
try:
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET
    )
    print("Cloudinary configuration applied.")
except Exception as e:
    print(f"CRITICAL ERROR: Cloudinary initialization failed: {e}")

# Initialize Redis connection and RQ queue
try:
    redis_conn = redis.from_url(REDIS_URL, decode_responses=True)
    q = Queue('default', connection=redis_conn)
    print("Connected to Redis for background jobs.")
except Exception as e:
    redis_conn = None
    q = None
    print(f"WARNING: Could not connect to Redis at {REDIS_URL}: {e}")

# =================================================================
# --- CLOUDINARY SIGNATURE UPLOAD UTILITY ---
# =================================================================
def upload_base64_to_cloudinary(base64_string, public_id_prefix):
    """
    Uploads a base64 string (signature) directly to Cloudinary and returns the secure URL.
    Accepts data URI (data:image/png;base64,....) or raw base64.
    """
    if not base64_string:
        return None

    try:
        upload_result = cloudinary.uploader.upload(
            file=base64_string,
            folder="signatures",
            public_id=f"{public_id_prefix}_{int(time.time())}"
        )
        return upload_result.get('secure_url')
    except Exception as e:
        print(f"ERROR: Cloudinary signature upload failed for {public_id_prefix}: {e}")
        return None

# =================================================================
# --- TEMPORARY STATE MANAGEMENT (Placeholder) ---
# =================================================================
def save_report_state(report_id, data):
    """Saves report state (placeholder using temp files)."""
    temp_record_path = os.path.join(tempfile.gettempdir(), f"{report_id}.json")
    with open(temp_record_path, 'w') as f:
        json.dump(data, f)

def get_report_state(report_id):
    """Retrieves and deletes report state (placeholder using temp files)."""
    temp_record_path = os.path.join(tempfile.gettempdir(), f"{report_id}.json")
    if not os.path.exists(temp_record_path):
        return None
    try:
        with open(temp_record_path, 'r') as f:
            record = json.load(f)
        return record
    finally:
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
        print(f"ERROR: Dropdown data file not found at: {DROPDOWN_DATA_PATH}")
        return jsonify({"error": "Dropdown data file not found"}), 404
    except json.JSONDecodeError:
        print(f"ERROR: Could not decode JSON data in: {DROPDOWN_DATA_PATH}")
        return jsonify({"error": "Invalid JSON data"}), 500

# 3. Metadata submit route (uploads signatures)
@site_visit_bp.route('/api/submit/metadata', methods=['POST'])
def submit_metadata():
    try:
        data = request.json
        visit_info = data.get('visit_info', {})
        processed_items = data.get('report_items', [])
        signatures = data.get('signatures', {})

        tech_sig_url = upload_base64_to_cloudinary(signatures.get('tech_signature'), 'tech_sig')
        opMan_sig_url = upload_base64_to_cloudinary(signatures.get('opMan_signature'), 'opman_sig')

        visit_info['tech_signature_url'] = tech_sig_url
        visit_info['opMan_signature_url'] = opMan_sig_url

        report_id = f"report-{int(time.time())}"

        save_report_state(report_id, {
            'visit_info': visit_info,
            'report_items': processed_items,
            'photo_urls': []
        })

        return jsonify({
            "status": "success",
            "visit_id": report_id,
            "cloudinary_cloud_name": CLOUDINARY_CLOUD_NAME,
            "cloudinary_upload_preset": CLOUDINARY_UPLOAD_PRESET,
        })
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"ERROR (Metadata): {error_details}")
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
        print(f"ERROR (Update Photos): {error_details}")
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

        # Normalize visit_info to dict if it's a JSON string or other unexpected type
        if isinstance(visit_info, str):
            try:
                visit_info = json.loads(visit_info)
            except Exception:
                # keep safe fallback
                visit_info = {"raw_visit_info": visit_info}

        if visit_info is None:
            visit_info = {}

        email_recipient = visit_info.get('email')

        # Build URL map (keys are tuples)
        url_map = {}
        for url_data in final_photo_urls:
            try:
                key = (int(url_data.get('item_index', 0)), int(url_data.get('photo_index', 0)))
                url_map[key] = url_data.get('photo_url')
            except Exception:
                # skip malformed entry
                continue

        for item_index, item in enumerate(final_items):
            image_urls = []
            for photo_index in range(int(item.get('photo_count', 0))):
                key = (item_index, photo_index)
                photo_url = url_map.get(key)
                if photo_url:
                    image_urls.append(photo_url)
                else:
                    print(f"WARNING: Missing photo URL for item {item_index}, photo {photo_index}. Key: {key}")

            item['image_urls'] = image_urls
            item.pop('photo_count', None)

        os.makedirs(GENERATED_DIR, exist_ok=True)

        # Create Excel synchronously (small/lightweight)
        # note: create_report_workbook signature expects (output_dir, visit_info, processed_items)
        excel_path, excel_filename = create_report_workbook(GENERATED_DIR, visit_info, final_items)

        # Enqueue background job to generate PDF (and upload/send email)
        if q is None:
            # If Redis/RQ not configured, fall back to synchronous generation (not recommended in production)
            print("WARNING: Redis/RQ not available. Generating PDF synchronously (may time out).")
            pdf_path, pdf_filename = generate_visit_pdf(visit_info, final_items, GENERATED_DIR)

            # Try sending email synchronously as before
            subject = f"INJAAZ Site Visit Report for {visit_info.get('building_name', 'Unknown')} - {datetime.now().strftime('%Y-%m-%d')}"
            body = f"The site visit report for {visit_info.get('building_name', 'Unknown')} on {datetime.now().strftime('%Y-%m-%d')} has been generated and is attached."

            attachments = [p for p in [excel_path, pdf_path] if p and os.path.exists(p)]
            try:
                email_status, msg = send_outlook_email(subject, body, attachments, email_recipient)
                print("EMAIL_STATUS:", msg)
            except Exception as e:
                print(f"WARNING: Email sending failed in synchronous fallback: {e}")

            return jsonify({
                "status": "success",
                "excel_url": url_for('site_visit_bp.download_generated', filename=excel_filename, _external=True),
                "pdf_url": url_for('site_visit_bp.download_generated', filename=pdf_filename, _external=True)
            })

        # Import the background task function (must exist at module_site_visit.utils.tasks.generate_and_send_report)
        try:
            from .utils.tasks import generate_and_send_report
        except Exception as e:
            print(f"CRITICAL ERROR: Could not import background task generate_and_send_report: {e}")
            raise

        # Enqueue the job. job_timeout should be tuned for your expected workload.
        job = q.enqueue(
            generate_and_send_report,
            report_id,
            visit_info,
            final_items,
            GENERATED_DIR,
            job_timeout=1800  # 30 minutes
        )

        # Initialize report status in Redis so client can poll
        try:
            if redis_conn is not None:
                redis_conn.set(f"report:{report_id}", json.dumps({"status": "pending", "job_id": job.get_id()}))
        except Exception as e:
            print(f"WARNING: Could not set initial report status in Redis: {e}")

        return jsonify({
            "status": "accepted",
            "visit_id": report_id,
            "job_id": job.get_id(),
            "status_url": url_for('site_visit_bp.report_status', visit_id=report_id, _external=True)
        }), 202

    except Exception as e:
        error_details = traceback.format_exc()
        print(f"ERROR (Finalize): {error_details}")
        return jsonify({
            "status": "error",
            "error": f"Internal server error: Failed to process report. Reason: {type(e).__name__}: {str(e)}"
        }), 500

# 6. Report status endpoint to poll background job progress/result
@site_visit_bp.route('/api/report-status', methods=['GET'])
def report_status():
    """
    Query Redis for the report status and return it. Expects ?visit_id=<visit_id>
    """
    visit_id = request.args.get('visit_id')
    if not visit_id:
        return jsonify({"error": "Missing visit_id"}), 400

    if redis_conn is None:
        return jsonify({"status": "error", "message": "Redis not configured on server."}), 500

    key = f"report:{visit_id}"
    result = redis_conn.get(key)
    if not result:
        return jsonify({"status": "unknown", "message": "No record found. The job may not have been started."}), 404

    try:
        data = json.loads(result)
        return jsonify({"status": "ok", "report": data})
    except Exception:
        # If stored value is already a JSON string but parsing failed, return raw
        return jsonify({"status": "ok", "report_raw": result})

# 7. Serve generated files
@site_visit_bp.route('/generated/<path:filename>')
def download_generated(filename):
    return send_from_directory(GENERATED_DIR, filename, as_attachment=True)