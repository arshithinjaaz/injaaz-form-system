import os
import json
import base64
import time
import traceback
import uuid
import tempfile
from datetime import datetime
from flask import Blueprint, render_template, jsonify, request, url_for, send_from_directory

# --- BOTO3/AWS IMPORTS ---
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
# -------------------------

# 1. Import utility functions
# NOTE: Assume generate_visit_pdf and create_report_workbook now use S3 keys
from .utils.email_sender import send_outlook_email 
from .utils.excel_writer import create_report_workbook 
from .utils.pdf_generator import generate_visit_pdf 

# --- PATH CONFIGURATION ---
BLUEPRINT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(BLUEPRINT_DIR) 

TEMPLATE_ABSOLUTE_PATH = os.path.join(BLUEPRINT_DIR, 'templates')
DROPDOWN_DATA_PATH = os.path.join(BLUEPRINT_DIR, 'dropdown_data.json') 

GENERATED_DIR_NAME = "generated"
GENERATED_DIR = os.path.join(BASE_DIR, GENERATED_DIR_NAME)
# IMAGE_UPLOAD_DIR is no longer used for large photo uploads!

# Define the Blueprint
site_visit_bp = Blueprint(
    'site_visit_bp', 
    __name__,
    template_folder=TEMPLATE_ABSOLUTE_PATH,
    static_folder='static'
)

# =================================================================
# --- AWS S3 & HELPER CONFIGURATION ---
# =================================================================
S3_BUCKET = os.environ.get('S3_BUCKET_NAME', 'injaaz-files')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')

# Initialize Boto3 Client - Reads credentials from environment variables automatically
s3_client = boto3.client(
    's3', 
    region_name=AWS_REGION, 
    # Critical for direct PUT uploads from the client
    config=Config(signature_version='s3v4') 
)

def generate_presigned_put_url(file_extension):
    """Generates a secure PUT presigned URL for direct client upload to S3."""
    
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    object_key = f"site-visit-photos/{unique_filename}"
    
    try:
        url = s3_client.generate_presigned_url(
            ClientMethod='put_object',
            Params={'Bucket': S3_BUCKET, 'Key': object_key},
            # URL is valid for 1 hour
            ExpiresIn=3600 
        )
        return url, object_key
    except ClientError as e:
        print(f"Error generating presigned URL: {e}")
        return None, None

def decode_base64_to_s3(base64_data, filename_prefix):
    """Decodes base64 data (like signature) and uploads the binary data directly to S3."""
    if not base64_data or not isinstance(base64_data, str) or len(base64_data) < 100:
        return None
        
    try:
        if ',' in base64_data:
            base64_data = base64_data.split(',')[1]
        
        # Memory risk is ACCEPTED here because signatures are small (< 100 KB)
        img_data = base64.b64decode(base64_data)
        
        # Define the S3 Key/Path
        object_key = f"signatures/{filename_prefix}_{int(time.time() * 1000)}.png"

        # Upload binary data directly to S3
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=object_key,
            Body=img_data,
            ContentType='image/png'
        )
        
        # Explicitly release the decoded image data from memory
        del img_data 
        
        print(f"DEBUG_S3_SIG: Successfully uploaded {filename_prefix} to S3 key: {object_key}")
        return object_key # Return the S3 key
        
    except Exception as e:
        print(f"Error decoding/saving base64 image to S3: {e}")
        return None


# =================================================================
# 1. Route: Main Form Page (UNCHANGED)
# =================================================================
@site_visit_bp.route('/form') 
def index():
    """Renders the main site visit form template (site_visit_form.html)."""
    return render_template('site_visit_form.html') 


# =================================================================
# 2. Route: Dropdown Data Endpoint (UNCHANGED)
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
# This replaces the start of the old /submit route.
# =================================================================
@site_visit_bp.route('/api/submit/metadata', methods=['POST'])
def submit_metadata():
    """Receives metadata, uploads signatures, and generates S3 upload links for photos."""
    
    try:
        data = request.json
        visit_info = data.get('visit_info', {})
        processed_items = data.get('report_items', []) 
        signatures = data.get('signatures', {})
        
        # --- 3A. Process Signatures (Upload directly to S3) ---
        tech_sig_key = decode_base64_to_s3(signatures.get('tech_signature'), 'tech_sig')
        opMan_sig_key = decode_base64_to_s3(signatures.get('opMan_signature'), 'opman_sig')
        
        # Store S3 keys instead of local paths
        visit_info['tech_signature_key'] = tech_sig_key
        visit_info['opMan_signature_key'] = opMan_sig_key
        
        # --- 3B. Generate S3 Pre-Signed URLs for Photos ---
        signed_urls = []
        
        # We need a unique report ID to tie all data together later
        # We use a simple timestamp as a pseudo-ID here; replace with a proper DB ID if used.
        report_id = f"report-{int(time.time())}" 
        
        for item_index, item in enumerate(processed_items):
            for photo_index in range(item.get('photo_count', 0)):
                # Assume all photos are JPEGs or PNGs (use dynamic extension if possible)
                file_extension = '.jpg' 
                
                url, s3_key = generate_presigned_put_url(file_extension)
                
                if url and s3_key:
                    signed_urls.append({
                        'item_index': item_index,
                        'photo_index': photo_index,
                        'url': url,
                        's3_key': s3_key,
                        # Store initial metadata so we don't lose it if using a DB
                        'asset': item.get('asset'),
                        'description': item.get('description'),
                        'visit_info': visit_info 
                        # In a real app, save everything to a DB table here!
                    })
                    
        # --- 3C. Temporary Storage (Simulated DB) ---
        # Since we are not using a database, we must temporarily store the data structure.
        # CRITICAL RISK: This data will be lost if the server reloads between phases!
        # This is strictly a demonstration; use a DB (Redis, PostgreSQL) in production.
        
        # We'll use the temp directory to simulate a persistent record of this submission
        # In production, you MUST use a database here.
        temp_record_path = os.path.join(tempfile.gettempdir(), f"{report_id}.json")
        with open(temp_record_path, 'w') as f:
            json.dump({
                'visit_info': visit_info,
                'report_items': processed_items,
                'signed_urls_data': signed_urls # Stores the generated S3 keys and metadata
            }, f)


        return jsonify({
            "status": "success",
            "visit_id": report_id, # Return the pseudo-ID
            "signed_urls": signed_urls
        })

    except Exception as e:
        error_details = traceback.format_exc()
        print(f"ERROR (Metadata): {error_details}")
        return jsonify({"error": f"Failed to process metadata: {str(e)}"}), 500


# =================================================================
# 4. ROUTE: PHASE 3 - FINALIZE REPORT & GENERATE PDF
# This completes the process once files are uploaded to S3.
# =================================================================
@site_visit_bp.route('/api/submit/finalize', methods=['GET'])
def finalize_report():
    """Triggers PDF and Excel generation after client confirms S3 uploads are complete."""
    
    report_id = request.args.get('visit_id')
    if not report_id:
        return jsonify({"error": "Missing visit_id parameter for finalization."}), 400

    # --- 1. Retrieve Stored Record (Simulated DB Fetch) ---
    temp_record_path = os.path.join(tempfile.gettempdir(), f"{report_id}.json")
    if not os.path.exists(temp_record_path):
        return jsonify({"error": "Report record not found (Server restarted or session expired)."}), 500
    
    try:
        with open(temp_record_path, 'r') as f:
            record = json.load(f)
        
        visit_info = record['visit_info']
        final_items = record['report_items']
        signed_urls_data = record['signed_urls_data']
        email_recipient = visit_info.get('email')
        
        # --- 2. Map S3 Keys back to Items ---
        # Attach the final S3 keys to the correct report items
        s3_key_map = {}
        for url_data in signed_urls_data:
            key = (url_data['item_index'], url_data['photo_index'])
            s3_key_map[key] = url_data['s3_key']

        # Rebuild final_items list with S3 keys
        for item_index, item in enumerate(final_items):
            image_keys = []
            for photo_index in range(item.get('photo_count', 0)):
                key = (item_index, photo_index)
                s3_key = s3_key_map.get(key)
                if s3_key:
                    image_keys.append(s3_key)
                else:
                    print(f"WARNING: Missing S3 key for item {item_index}, photo {photo_index}")
            
            # NOTE: Updated to use 'image_keys' field name to match pdf_generator.py
            item['image_keys'] = image_keys 
        
        # -----------------------------------------------------------------
        # --- 3. Generate Reports (Using S3 download helpers) ---
        # -----------------------------------------------------------------
        excel_path, excel_filename = create_report_workbook(GENERATED_DIR, visit_info, final_items)
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

    finally:
        # 6. Clean up the temporary record
        if os.path.exists(temp_record_path):
            os.remove(temp_record_path)
            print(f"DEBUG_CLEANUP: Removed temporary record {report_id}.json")


# =================================================================
# 5. Route: Download Generated Files (UNCHANGED)
# =================================================================
@site_visit_bp.route('/generated/<path:filename>')
def download_generated(filename):
    """Serves the generated files (PDF/Excel) from the GENERATED_DIR."""
    return send_from_directory(GENERATED_DIR, filename, as_attachment=True)
