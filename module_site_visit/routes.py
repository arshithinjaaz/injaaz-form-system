import os
import json
import base64
import time
import traceback
from flask import Blueprint, render_template, jsonify, request, url_for, send_from_directory

# 1. Import utility functions
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
IMAGE_UPLOAD_DIR = os.path.join(GENERATED_DIR, "images")


# Define the Blueprint
site_visit_bp = Blueprint(
    'site_visit_bp', 
    __name__,
    template_folder=TEMPLATE_ABSOLUTE_PATH,
    static_folder='static'
)


# --- HELPER FUNCTION: Decode and Save Base64 Images/Signatures ---
def save_base64_image(base64_data, filename_prefix):
    """Decodes a base64 image string and saves it to the IMAGE_UPLOAD_DIR."""
    os.makedirs(IMAGE_UPLOAD_DIR, exist_ok=True)
    
    if not base64_data or not isinstance(base64_data, str) or len(base64_data) < 100:
        return None
        
    try:
        if ',' in base64_data:
            base64_data = base64_data.split(',')[1]
        
        img_data = base64.b64decode(base64_data)
        
        timestamp = int(time.time() * 1000)
        filename = f"{filename_prefix}_{timestamp}.png"
        file_path = os.path.join(IMAGE_UPLOAD_DIR, filename)

        with open(file_path, 'wb') as f:
            f.write(img_data)
            
        return filename
        
    except Exception as e:
        print(f"Error decoding/saving base64 image: {e}")
        return None


# =================================================================
# 1. Route: Main Form Page (Called by url_for('site_visit_bp.index') from dashboard.html)
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
# 3. Route: File Download Endpoint
#    ***REMOVED REDUNDANT ROUTE*** (The file serving is handled by download_generated 
#    in Injaaz.py which serves from the /generated/ path.)
# =================================================================
# @site_visit_bp.route('/downloads/<filename>')
# def download_file(filename):
#    return send_from_directory(GENERATED_DIR, filename, as_attachment=True)


# =================================================================
# 4. Route: Form Submission (Called by POST to /submit)
# =================================================================
@site_visit_bp.route('/submit', methods=['POST'])
def submit():
    # 1. Setup
    data = request.get_json()
    # temp_image_paths only tracks images, NOT the final Excel/PDF reports
    temp_image_paths = [] 
    final_items = [] 
    
    excel_path = None
    pdf_path = None
    
    if not data:
        return jsonify({"error": "No data received."}), 400

    # 2. Extract Data
    visit_info = data.get('visit_info', {})
    processed_items = data.get('report_items', []) 
    signatures = data.get('signatures', {}) 

    email_recipient = visit_info.get('email')
    
    try:
        # --- 3. Process Signatures ---
        tech_sig_data = signatures.get('tech_signature')
        opMan_sig_data = signatures.get('opMan_signature')
        
        tech_sig_filename = save_base64_image(tech_sig_data, 'tech_sig')
        opMan_sig_filename = save_base64_image(opMan_sig_data, 'opman_sig')

        tech_sig_path = os.path.join(IMAGE_UPLOAD_DIR, tech_sig_filename) if tech_sig_filename else None
        opMan_sig_path = os.path.join(IMAGE_UPLOAD_DIR, opMan_sig_filename) if opMan_sig_filename else None

        if tech_sig_path: temp_image_paths.append(tech_sig_path)
        if opMan_sig_path: temp_image_paths.append(opMan_sig_path)

        visit_info['tech_signature_path'] = tech_sig_path
        visit_info['opMan_signature_path'] = opMan_sig_path

        # -----------------------------------------------------------------
        # --- 4. Process Report Item Photos ---
        # -----------------------------------------------------------------
        for item in processed_items:
            item_image_paths = []
            
            for i, base64_photo_data in enumerate(item.get('photos', [])):
                prefix = f"{visit_info.get('building_name', 'item')}_{item.get('asset', 'asset')}_{i}"
                prefix = prefix.replace(' ', '_')[:30] 
                
                filename = save_base64_image(base64_photo_data, prefix) 
                
                if filename:
                    path = os.path.join(IMAGE_UPLOAD_DIR, filename)
                    item_image_paths.append(path)
                    temp_image_paths.append(path) # Add to cleanup list for images only

            # CRITICAL: Pass file paths, not Base64 data, to utility functions.
            item['image_paths'] = item_image_paths
            item.pop('photos', None) # Remove large base64 data
            
            final_items.append(item)
            
        # -----------------------------------------------------------------
        # --- 5. Generate Excel Report ---
        # -----------------------------------------------------------------
        excel_path, excel_filename = create_report_workbook(GENERATED_DIR, visit_info, final_items)
        
        # -----------------------------------------------------------------
        # --- 6. Generate PDF Report ---
        # -----------------------------------------------------------------
        pdf_path, pdf_filename = generate_visit_pdf(visit_info, final_items, GENERATED_DIR)
        
        # --- 7. Send Email ---
        subject = f"INJAAZ Site Visit Report for {visit_info.get('building_name', 'Unknown')}"
        body = f"""
Dear Internal Team,

A new Site Visit Report has been completed and attached:
- Building: {visit_info.get('building_name', 'N/A')}
- Address: {visit_info.get('site_address', 'N/A')}
- Technician: {visit_info.get('technician_name', 'N/A')}

The final reports (Excel and PDF) are attached.

Regards,
INJAAZ System
"""
        attachments = [excel_path, pdf_path]
        
        email_status, msg = send_outlook_email(subject, body, attachments, email_recipient)
        print("EMAIL_STATUS:", msg)

        # ----------------------
        # 8. Cleanup (ONLY delete temporary IMAGE files, keep the reports for download)
        # ----------------------
        for path in temp_image_paths:
            try:
                if os.path.isfile(path): 
                    os.remove(path)
            except OSError as e:
                # This error won't stop the frontend response, but helps debug
                print(f"Error deleting temp image file {path}: {e}")

        # ----------------------
        # 9. RESPONSE TO FRONTEND (CRITICAL: Using the root app's 'download_generated' route)
        # ----------------------
        return jsonify({
            "status": "success",
            # FIX: Point to the main app's download route, not a blueprint route
            "excel_url": url_for('download_generated', filename=excel_filename, _external=True), 
            "pdf_url": url_for('download_generated', filename=pdf_filename, _external=True)
        })

    except Exception as e:
        error_details = traceback.format_exc()
        
        print("\n--- SERVER ERROR TRACEBACK START (ROOT CAUSE) ---")
        print(error_details)
        print("--- SERVER ERROR TRACEBACK END ---\n")
        
        # 10. ERROR CLEANUP (Only delete images on failure)
        for path in temp_image_paths:
            try:
                # Ensure we only delete image files that were successfully created
                if os.path.isfile(path):
                    os.remove(path)
            except:
                pass
        
        # 11. ERROR RESPONSE TO FRONTEND
        return jsonify({
            "status": "error",
            "error": f"Internal server error: Failed to process report. Reason: {type(e).__name__}: {str(e)}"
        }), 500