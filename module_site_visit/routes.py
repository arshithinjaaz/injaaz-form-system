import os
import json
import time
import traceback
import tempfile
from datetime import datetime
from flask import Blueprint, render_template, jsonify, request, url_for, send_from_directory

# =================================================================
# --- 1. CORE IMPORTS ---
# =================================================================

# IMPORTANT: The following functions MUST be defined in a sibling file named 's3_utils.py'
from .utils import (
    generate_presigned_put_url,
    decode_base64_to_s3
)

# IMPORTANT: The following utility functions MUST be defined in 'utils/'
from .utils.email_sender import send_outlook_email 
from .utils.excel_writer import create_report_workbook 
from .utils.pdf_generator import generate_visit_pdf 

# =================================================================
# --- 🔴 STABILITY FIX: REDIS/DB PLACEHOLDER ---
# This simulates using a key/value store (like Redis) for temporary 
# state between API calls (e.g., while photos are uploaded to S3).
# It uses the temporary file system (os.path.join(tempfile.gettempdir())) 
# which is NOT production safe, but works for the current placeholder logic.
# =================================================================

def save_report_state(report_id, data):
    """Saves report state (Placeholder for Redis/DB)."""
    # NOTE: DANGEROUS! Replace with redis_client.setex(report_id, 3600, json.dumps(data))
    temp_record_path = os.path.join(tempfile.gettempdir(), f"{report_id}.json")
    with open(temp_record_path, 'w') as f:
        json.dump(data, f)

def get_report_state(report_id):
    """Retrieves and deletes report state (Placeholder for Redis/DB)."""
    # NOTE: DANGEROUS! Replace with data = redis_client.get(report_id); redis_client.delete(report_id)
    temp_record_path = os.path.join(tempfile.gettempdir(), f"{report_id}.json")
    
    if not os.path.exists(temp_record_path):
        return None
        
    try:
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
# 1. Route: Main Form Page
# =================================================================
@site_visit_bp.route('/form') 
def index():
    """Renders the main site visit form template (site_visit_form.html)."""
    return render_template('site_visit_form.html') 


# =================================================================
# 2. Route: Dropdown Data Endpoint
# =================================================================
@site_visit_bp.route('/dropdowns')
def get_dropdown_data():
    """Reads the dropdown_data.json file and returns its content as JSON."""
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


# =================================================================
# 3. ROUTE: PHASE 1 - SUBMIT METADATA & GET S3 LINKS
# Receives form metadata, processes signatures, saves state, and returns S3 links.
# =================================================================
@site_visit_bp.route('/api/submit/metadata', methods=['POST'])
def submit_metadata():
    """Receives metadata, uploads signatures, and generates S3 upload links for photos."""
    
    try:
        data = request.json
        visit_info = data.get('visit_info', {})
        processed_items = data.get('report_items', []) 
        signatures = data.get('signatures', {})
        
        # --- 3A. Process Signatures (Using s3_utils.decode_base64_to_s3) ---
        # This function should convert the base64 string to a file and upload it to S3, returning the key.
        tech_sig_key = decode_base64_to_s3(signatures.get('tech_signature'), 'tech_sig')
        opMan_sig_key = decode_base64_to_s3(signatures.get('opMan_signature'), 'opman_sig')
        
        # Store S3 keys instead of local paths
        visit_info['tech_signature_key'] = tech_sig_key
        visit_info['opMan_signature_key'] = opMan_sig_key
        
        # --- 3B. Generate S3 Pre-Signed URLs for Photos (Using s3_utils.generate_presigned_put_url) ---
        signed_urls = []
        report_id = f"report-{int(time.time())}" 
        
        for item_index, item in enumerate(processed_items):
            for photo_index in range(item.get('photo_count', 0)):
                file_extension = '.jpg' 
                # This function returns the URL for the client to upload to, and the S3 key.
                url, s3_key = generate_presigned_put_url(file_extension)
                
                if url and s3_key:
                    signed_urls.append({
                        'item_index': item_index,
                        'photo_index': photo_index,
                        'url': url,
                        's3_key': s3_key,
                        'asset': item.get('asset'),
                        'description': item.get('description'),
                        'visit_info': visit_info 
                    })
                    
        # --- 3C. Temporary/Shared Storage (SAVES STATE via PLACEHOLDER) ---
        save_report_state(report_id, {
            'visit_info': visit_info,
            'report_items': processed_items,
            'signed_urls_data': signed_urls
        })


        return jsonify({
            "status": "success",
            "visit_id": report_id, 
            "signed_urls": signed_urls
        })

    except Exception as e:
        error_details = traceback.format_exc()
        print(f"ERROR (Metadata): {error_details}")
        return jsonify({"error": f"Failed to process metadata: {str(e)}"}), 500


# =================================================================
# 4. ROUTE: PHASE 3 - FINALIZE REPORT & GENERATE PDF
# Finalizes report generation once client confirms all files are uploaded.
# =================================================================
@site_visit_bp.route('/api/submit/finalize', methods=['GET'])
def finalize_report():
    """Triggers PDF and Excel generation after client confirms S3 uploads are complete."""
    
    report_id = request.args.get('visit_id')
    if not report_id:
        return jsonify({"error": "Missing visit_id parameter for finalization."}), 400

    # --- 1. Retrieve Stored Record (GETS STATE via PLACEHOLDER) ---
    record = get_report_state(report_id)
    
    if not record:
        return jsonify({"error": "Report record not found (Server restarted or session expired)."}), 500
    
    try:
        visit_info = record['visit_info']
        final_items = record['report_items']
        signed_urls_data = record['signed_urls_data']
        email_recipient = visit_info.get('email')
        
        # --- 2. Map S3 Keys back to Items (Reconstruct data structure) ---
        s3_key_map = {}
        for url_data in signed_urls_data:
            key = (url_data['item_index'], url_data['photo_index'])
            s3_key_map[key] = url_data['s3_key']

        for item_index, item in enumerate(final_items):
            image_keys = []
            for photo_index in range(item.get('photo_count', 0)):
                key = (item_index, photo_index)
                s3_key = s3_key_map.get(key)
                if s3_key:
                    image_keys.append(s3_key)
                else:
                    print(f"WARNING: Missing S3 key for item {item_index}, photo {photo_index}")
            
            item['image_keys'] = image_keys 
        
        # -----------------------------------------------------------------
        # --- 3. Generate Reports (Calls utility functions) ---
        # These utilities must handle fetching files from S3 using the image_keys.
        # -----------------------------------------------------------------
        excel_path, excel_filename = create_report_workbook(GENERATED_DIR, visit_info, final_items)
        pdf_path, pdf_filename = generate_visit_pdf(visit_info, final_items, GENERATED_DIR)
        
        # --- 4. Send Email (Calls utility function) ---
        subject = f"INJAAZ Site Visit Report for {visit_info.get('building_name', 'Unknown')} - {datetime.now().strftime('%Y-%m-%d')}"
        body = f"""The site visit report for {visit_info.get('building_name', 'Unknown')} on {datetime.now().strftime('%Y-%m-%d')} has been generated and is attached."""
        
        attachments = [p for p in [excel_path, pdf_path] if p and os.path.exists(p)]
        email_status, msg = send_outlook_email(subject, body, attachments, email_recipient)
        print("EMAIL_STATUS:", msg)
        
        # 5. SUCCESS RESPONSE TO FRONTEND
        return jsonify({
            "status": "success",
            # Use url_for to generate the full download link
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
# 5. Route: Download Generated Files
# =================================================================
@site_visit_bp.route('/generated/<path:filename>')
def download_generated(filename):
    """Serves the generated files (PDF/Excel) from the GENERATED_DIR."""
    # This serves the file to the user's browser as a download attachment
    return send_from_directory(GENERATED_DIR, filename, as_attachment=True)
