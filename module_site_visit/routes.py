import os
import json
import base64
import time
import traceback
from datetime import datetime
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

# --- Define Absolute Path for Logo ---
# NOTE: This variable is now only used for reference/debugging, 
# as the pdf_generator calculates the path internally.
LOGO_ABSOLUTE_PATH = os.path.join(BASE_DIR, 'static', 'INJAAZ.png') 

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
        print(f"DEBUG_SAVE: Invalid or empty base64 data for {filename_prefix}")
        return None
        
    try:
        if ',' in base64_data:
            base64_data = base64_data.split(',')[1]
        
        # This is where memory consumption starts: decoding the base64 string
        img_data = base64.b64decode(base64_data)
        
        timestamp = int(time.time() * 1000)
        filename = f"{filename_prefix}_{timestamp}.png"
        file_path = os.path.join(IMAGE_UPLOAD_DIR, filename)

        with open(file_path, 'wb') as f:
            f.write(img_data)
            
        print(f"DEBUG_SAVE: Successfully saved {filename} to {file_path}")
        
        # Explicitly release the decoded image data from memory after writing to disk
        del img_data 
        
        return file_path # Return the full path for the PDF generator
        
    except Exception as e:
        print(f"Error decoding/saving base64 image: {e}")
        return None


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
# 3. Route: Form Submission (Called by POST to /submit)
# =================================================================
@site_visit_bp.route('/submit', methods=['POST'])
def submit():
    # 1. Setup
    temp_image_paths = [] # List to track all image/signature files for guaranteed deletion
    final_items = []
    excel_path = None
    pdf_path = None
    
    # --- Extract Data from multipart/form-data ---
    data_json_string = request.form.get('data') 
    
    if not data_json_string:
        return jsonify({"error": "Missing main data payload ('data') in request form."}), 400

    try:
        data = json.loads(data_json_string) 
        uploaded_files = request.files 
        visit_info = data.get('visit_info', {})
        processed_items = data.get('report_items', []) 
        signatures = data.get('signatures', {}) 
        email_recipient = visit_info.get('email')
    except Exception as e:
        return jsonify({"error": f"Failed to parse request data: {str(e)}"}), 400
    # --- END DATA EXTRACTION ---

    
    # -------------------------------------------------------------------------
    # --- START CRITICAL TRY...FINALLY BLOCK FOR MEMORY/CLEANUP GUARANTEE ---
    # -------------------------------------------------------------------------
    try:
        # --- 3. Process Signatures (STILL base64) ---
        tech_sig_data = signatures.get('tech_signature')
        opMan_sig_data = signatures.get('opMan_signature')
        
        # NOTE: save_base64_image now returns the full path
        tech_sig_path = save_base64_image(tech_sig_data, 'tech_sig')
        opMan_sig_path = save_base64_image(opMan_sig_data, 'opman_sig')

        if tech_sig_path: temp_image_paths.append(tech_sig_path)
        if opMan_sig_path: temp_image_paths.append(opMan_sig_path)

        visit_info['tech_signature_path'] = tech_sig_path
        visit_info['opMan_signature_path'] = opMan_sig_path

        # -----------------------------------------------------------------
        # --- 4. Process Report Item Photos (Uses FileStorage.save) ---
        # -----------------------------------------------------------------
        item_photo_count = 0
        os.makedirs(IMAGE_UPLOAD_DIR, exist_ok=True)

        for item_index, item in enumerate(processed_items):
            item_image_paths = []
            
            for file_key, file_storage in uploaded_files.items():
                if file_key.startswith(f"photo-item-{item_index}-"):
                    if not file_storage.filename:
                        continue

                    try:
                        timestamp = int(time.time() * 1000)
                        item_slug = item.get('category', 'item').replace(' ', '_').replace('/', '')
                        filename = f"{item_slug}_{item_index}_{item_photo_count}_{timestamp}.png"
                        path = os.path.join(IMAGE_UPLOAD_DIR, filename)
                        
                        # CRITICAL: This line streams the file to disk, preventing OOM errors
                        file_storage.save(path) 
                        
                        item_image_paths.append(path)
                        temp_image_paths.append(path) # Add to cleanup list
                        item_photo_count += 1
                    
                    except Exception as e:
                        print(f"Error saving file {file_key}: {e}")
                        # If a single file fails, we continue processing other files
                        continue
            
            item['image_paths'] = item_image_paths
            final_items.append(item)
            
        print(f"DEBUG_SUBMIT: Total photos received and processed: {item_photo_count}")
        
        # -----------------------------------------------------------------
        # --- 5. Generate Excel Report ---
        # -----------------------------------------------------------------
        excel_path, excel_filename = create_report_workbook(GENERATED_DIR, visit_info, final_items)
        
        # -----------------------------------------------------------------
        # --- 6. Generate PDF Report ---
        # -----------------------------------------------------------------
        # 👇 FIX APPLIED HERE: Remove the logo_path argument
        pdf_path, pdf_filename = generate_visit_pdf(visit_info, final_items, GENERATED_DIR)
        
        # --- 7. Send Email ---
        subject = f"INJAAZ Site Visit Report for {visit_info.get('building_name', 'Unknown')} - {datetime.now().strftime('%Y-%m-%d')}"
        body = f"""The site visit report for {visit_info.get('building_name', 'Unknown')} on {datetime.now().strftime('%Y-%m-%d')} has been generated and is attached."""
        
        attachments = [p for p in [excel_path, pdf_path] if p and os.path.exists(p)]
        email_status, msg = send_outlook_email(subject, body, attachments, email_recipient)
        print("EMAIL_STATUS:", msg)
        
        # ----------------------
        # 8. SUCCESS RESPONSE TO FRONTEND
        # ----------------------
        return jsonify({
            "status": "success",
            "excel_url": url_for('site_visit_bp.download_generated', filename=excel_filename, _external=True), 
            "pdf_url": url_for('site_visit_bp.download_generated', filename=pdf_filename, _external=True)
        })

    except Exception as e:
        error_details = traceback.format_exc()
        
        print("\n--- SERVER ERROR TRACEBACK START (ROOT CAUSE) ---")
        print(error_details)
        print("--- SERVER ERROR TRACEBACK END ---\n")
        
        # 9. ERROR RESPONSE TO FRONTEND
        return jsonify({
            "status": "error",
            "error": f"Internal server error: Failed to process report. Reason: {type(e).__name__}: {str(e)}"
        }), 500

    # --------------------------------------------------------------------
    # --- 10. CRITICAL: GUARANTEED CLEANUP (FINALLY BLOCK) ---
    # --------------------------------------------------------------------
    finally:
        print("DEBUG_FINALLY_CLEANUP: Starting guaranteed temporary file cleanup...")
        # This deletes all temporary image and signature files.
        for path in temp_image_paths:
            try:
                if os.path.isfile(path): 
                    os.remove(path)
                    print(f"DEBUG_FINALLY_CLEANUP: Removed temporary file {os.path.basename(path)}")
            except OSError as e:
                print(f"Error deleting temp file {os.path.basename(path)}: {e}")
        print("DEBUG_FINALLY_CLEANUP: Guaranteed cleanup complete.")


# =================================================================
# 4. Route: Download Generated Files
# =================================================================
@site_visit_bp.route('/generated/<path:filename>')
def download_generated(filename):
    """Serves the generated files (PDF/Excel) from the GENERATED_DIR."""
    return send_from_directory(GENERATED_DIR, filename, as_attachment=True)