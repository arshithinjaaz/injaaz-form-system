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

# --- CORE IMPORTS ---
# Assuming these are relative imports from the module's sub-directories
from .utils.email_sender import send_outlook_email 
from .utils.excel_writer import create_report_workbook 
from .utils.pdf_generator import generate_visit_pdf 

# --- CONFIGURATION (Loaded from environment variables with provided defaults) ---
# NOTE: Replace the default values with environment variables in production!
CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME', 'dv7kljagk') 
CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY', '863137649681362') 
CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET', '2T8gWf0H--OH2T55rcYS9qXm9Bg') 
CLOUDINARY_UPLOAD_PRESET = os.environ.get('CLOUDINARY_UPLOAD_PRESET','render_site_upload') # No default set here

# Initialize Cloudinary (required for server-side upload of signatures)
try:
    # ⚠️ FIXED: All indentation here must use standard spaces/tabs.
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY, 
        api_secret=CLOUDINARY_API_SECRET
    )
    print("Cloudinary configuration successful.")
except Exception as e:
    print(f"CRITICAL ERROR: Cloudinary initialization failed: {e}")
    pass


# =================================================================
# --- CLOUDINARY SIGNATURE UPLOAD UTILITY ---
# =================================================================

def upload_base64_to_cloudinary(base64_string, public_id_prefix):
    """
    Uploads a base64 string (signature) directly to Cloudinary and returns the secure URL.
    """
    if not base64_string:
        return None
        
    try:
        # ⚠️ FIXED: Indentation here must use standard spaces/tabs.
        # Cloudinary Uploader can accept the full 'data:image/png;base64,...' string
        upload_result = cloudinary.uploader.upload(
            file=base64_string,
            folder="signatures",
            public_id=f"{public_id_prefix}_{int(time.time())}"
        )
        # Return the secure permanent URL
        return upload_result.get('secure_url')
        
    except Exception as e:
        print(f"ERROR: Cloudinary signature upload failed for {public_id_prefix}: {e}")
        return None

# =================================================================
# --- TEMPORARY STATE MANAGEMENT (Placeholder) ---
# =================================================================

def save_report_state(report_id, data):
    """Saves report state (Placeholder for Redis/DB)."""
    temp_record_path = os.path.join(tempfile.gettempdir(), f"{report_id}.json")
    # ⚠️ FIXED: Indentation here must use standard spaces/tabs.
    with open(temp_record_path, 'w') as f:
        json.dump(data, f)

def get_report_state(report_id):
    """Retrieves and deletes report state (Placeholder for Redis/DB)."""
    temp_record_path = os.path.join(tempfile.gettempdir(), f"{report_id}.json")
    
    if not os.path.exists(temp_record_path):
        return None
        
    try:
        # ⚠️ FIXED: Indentation here must use standard spaces/tabs.
        with open(temp_record_path, 'r') as f:
            record = json.load(f)
        return record
    finally:
        # Simulate cleanup after reading (like Redis delete)
        if os.path.exists(temp_record_path):
            os.remove(temp_record_path)

# =================================================================
# --- PATH AND BLUEPRINT CONFIGURATION ---
# =================================================================

BLUEPRINT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(BLUEPRINT_DIR) 

TEMPLATE_ABSOLUTE_PATH = os.path.join(BLUEPRINT_DIR, 'templates')
DROPDOWN_DATA_PATH = os.path.join(BLUEPRINT_DIR, 'dropdown_data.json') 

# Define the directory where generated files will be stored
GENERATED_DIR_NAME = "generated"
GENERATED_DIR = os.path.join(BASE_DIR, GENERATED_DIR_NAME)

# Define the Blueprint
site_visit_bp = Blueprint(
    'site_visit_bp', 
    __name__,
    template_folder=TEMPLATE_ABSOLUTE_PATH,
    static_folder='static'
)


# =================================================================
# 1 & 2. Main Form Page & Dropdown Data
# =================================================================

@site_visit_bp.route('/form') 
def index():
    """Renders the main site visit form template (site_visit_form.html)."""
    return render_template('site_visit_form.html') 


@site_visit_bp.route('/dropdowns')
def get_dropdown_data():
    """Reads the dropdown_data.json file and returns its content as JSON."""
    try:
        # ⚠️ FIXED: Indentation here must use standard spaces/tabs.
        with open(DROPDOWN_DATA_PATH, 'r') as f:
            data = json.load(f)
        return jsonify(data)
    except FileNotFoundError:
        print(f"ERROR: Dropdown data file not found at: {DROPDOWN_DATA_PATH}")
        return jsonify({"error": "Dropdown data file not found"}), 404
    except json.JSONDecodeError:
        print(f"ERROR: Could not decode JSON data in: {DROPDOWN_DATA_PATH}")
        return jsonify({"error": "Invalid JSON data"}), 500


# =================================================================
# 3. ROUTE: PHASE 1 - SUBMIT METADATA (Uploads signatures to Cloudinary)
# =================================================================
@site_visit_bp.route('/api/submit/metadata', methods=['POST'])
def submit_metadata():
    """Receives metadata, uploads signatures to Cloudinary, and returns Cloudinary config for client photo upload."""
    
    try:
        # ⚠️ FIXED: Indentation here must use standard spaces/tabs.
        data = request.json
        visit_info = data.get('visit_info', {})
        processed_items = data.get('report_items', []) 
        signatures = data.get('signatures', {})
        
        # --- 3A. Process Signatures (Using Cloudinary upload) ---
        tech_sig_url = upload_base64_to_cloudinary(signatures.get('tech_signature'), 'tech_sig')
        opMan_sig_url = upload_base64_to_cloudinary(signatures.get('opMan_signature'), 'opman_sig')
        
        # Store signature URLs
        visit_info['tech_signature_url'] = tech_sig_url
        visit_info['opMan_signature_url'] = opMan_sig_url
        
        # --- 3B. Setup Report ID ---
        report_id = f"report-{int(time.time())}" 
        
        # --- 3C. Temporary/Shared Storage (SAVES INITIAL STATE) ---
        save_report_state(report_id, {
            'visit_info': visit_info,
            'report_items': processed_items,
            'photo_urls': [] 
        })

        # --- 3D. Return Cloudinary Configuration for the FRONT-END (client-side upload) ---
        return jsonify({
            "status": "success",
            "visit_id": report_id, 
            # These are used by main.js for direct client-side photo upload
            "cloudinary_cloud_name": CLOUDINARY_CLOUD_NAME,
            "cloudinary_upload_preset": CLOUDINARY_UPLOAD_PRESET,
        })

    except Exception as e:
        error_details = traceback.format_exc()
        print(f"ERROR (Metadata): {error_details}")
        return jsonify({"error": f"Failed to process metadata: {str(e)}"}), 500


# =================================================================
# 4. ROUTE: PHASE 2 - RECEIVE FINAL PHOTO URLS (From client direct upload)
# =================================================================
@site_visit_bp.route('/api/submit/update-photos', methods=['POST'])
def update_photos():
    """Receives the final Cloudinary URLs and updates the server state."""
    report_id = request.args.get('visit_id')
    if not report_id:
        return jsonify({"error": "Missing visit_id"}), 400

    record = get_report_state(report_id)
    if not record:
        return jsonify({"error": "Report record not found (Server restarted or session expired)."}), 500
        
    try:
        # ⚠️ FIXED: Indentation here must use standard spaces/tabs.
        data = request.json
        photo_urls = data.get('photo_urls', [])
        
        record['photo_urls'] = photo_urls
        save_report_state(report_id, record) 
        
        return jsonify({"status": "success"})
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"ERROR (Update Photos): {error_details}")
        return jsonify({"error": f"Failed to update photo URLs: {str(e)}"}), 500


# =================================================================
# 5. ROUTE: PHASE 3 - FINALIZE REPORT (Generates PDF/Excel)
# =================================================================
@site_visit_bp.route('/api/submit/finalize', methods=['GET'])
def finalize_report():
    """Triggers report generation after client confirms uploads are complete."""
    
    report_id = request.args.get('visit_id')
    if not report_id:
        return jsonify({"error": "Missing visit_id parameter for finalization."}), 400

    record = get_report_state(report_id)
    
    if not record:
        return jsonify({"error": "Report record not found (Server restarted or session expired)."}), 500
    
    try:
        # ⚠️ FIXED: Indentation here must use standard spaces/tabs.
        visit_info = record['visit_info']
        final_items = record['report_items']
        final_photo_urls = record.get('photo_urls', []) 
        email_recipient = visit_info.get('email')
        
        # --- 2. Map Cloudinary URLs back to Items ---
        url_map = {}
        for url_data in final_photo_urls:
            key = (url_data['item_index'], url_data['photo_index'])
            url_map[key] = url_data['photo_url'] 

        for item_index, item in enumerate(final_items):
            image_urls = []
            for photo_index in range(item.get('photo_count', 0)):
                key = (item_index, photo_index)
                photo_url = url_map.get(key)
                if photo_url:
                    image_urls.append(photo_url)
                else:
                    print(f"WARNING: Missing photo URL for item {item_index}, photo {photo_index}. URL map key: {key}")
            
            item['image_urls'] = image_urls 
            item.pop('photo_count', None)
        
        # -----------------------------------------------------------------
        # --- 3. Generate Reports ---
        # -----------------------------------------------------------------
        os.makedirs(GENERATED_DIR, exist_ok=True) 

        # This requires xlsxwriter and openpyxl
        excel_path, excel_filename = create_report_workbook(GENERATED_DIR, visit_info, final_items)
        # This requires reportlab and Pillow
        pdf_path, pdf_filename = generate_visit_pdf(visit_info, final_items, GENERATED_DIR)
        
        # --- 4. Send Email ---
        subject = f"INJAAZ Site Visit Report for {visit_info.get('building_name', 'Unknown')} - {datetime.now().strftime('%Y-%m-%d')}"
        body = f"""The site visit report for {visit_info.get('building_name', 'Unknown')} on {datetime.now().strftime('%Y-%m-%d')} has been generated and is attached."""
        
        attachments = [p for p in [excel_path, pdf_path] if p and os.path.exists(p)]
        email_status, msg = send_outlook_email(subject, body, attachments, email_recipient)
        print("EMAIL_STATUS:", msg)

        # 5. SUCCESS RESPONSE TO FRONTEND
        return jsonify({
            "status": "success",
            "excel_url": url_for('site_visit_bp.download_generated', filename=excel_filename, _external=True), 
            "pdf_url": url_for('site_visit_bp.download_generated', filename=pdf_filename, _external=True)
        })

    except Exception as e:
        error_details = traceback.format_exc()
        print(f"ERROR (Finalize): {error_details}")
        return jsonify({
            "status": "error",
            "error": f"Internal server error: Failed to process report. Reason: {type(e).__name__}: {str(e)}"
        }), 500


# =================================================================
# 6. Route: Download Generated Files
# =================================================================
@site_visit_bp.route('/generated/<path:filename>')
def download_generated(filename):
    """Serves the generated files (PDF/Excel) from the GENERATED_DIR."""
    return send_from_directory(GENERATED_DIR, filename, as_attachment=True)