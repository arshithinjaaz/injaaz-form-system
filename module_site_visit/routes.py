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

# --- Define Absolute Path for Logo ---
LOGO_ABSOLUTE_PATH = os.path.join(BASE_DIR, 'static', 'INJAAZ.png') 

# Define the Blueprint
site_visit_bp = Blueprint(
    'site_visit_bp', 
    __name__,
    template_folder=TEMPLATE_ABSOLUTE_PATH,
    static_folder='static'
)


# --- HELPER FUNCTION: Decode and Save Base64 Images/Signatures ---
# NOTE: This function is still used for signatures, as they are sent as Base64 strings.
def save_base64_image(base64_data, filename_prefix):
    """Decodes a base64 image string and saves it to the IMAGE_UPLOAD_DIR."""
    os.makedirs(IMAGE_UPLOAD_DIR, exist_ok=True)
    
    if not base64_data or not isinstance(base64_data, str) or len(base64_data) < 100:
        print(f"DEBUG_SAVE: Invalid or empty base64 data for {filename_prefix}")
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
            
        print(f"DEBUG_SAVE: Successfully saved {filename} to {file_path}")
        
        return filename
        
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
    temp_image_paths = []
    final_items = []
    excel_path = None
    pdf_path = None
    
    # --- CRITICAL FIX: Extract Data from multipart/form-data ---
    # The JSON payload is sent as a string under the key 'data' in the form data.
    data_json_string = request.form.get('data') 
    
    if not data_json_string:
        return jsonify({"error": "Missing main data payload ('data') in request form. Ensure 'Content-Type' is NOT set to application/json on the client."}), 400

    try:
        # Deserialize the JSON string payload
        data = json.loads(data_json_string) 
        
        # Access all uploaded files (photos)
        uploaded_files = request.files 
        
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON format in 'data' payload."}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to parse request data: {str(e)}"}), 400
    # --- END CRITICAL FIX ---


    # 2. Extract Data (uses the now-loaded 'data' dictionary)
    visit_info = data.get('visit_info', {})
    processed_items = data.get('report_items', []) 
    signatures = data.get('signatures', {}) 

    email_recipient = visit_info.get('email')
    
    try:
        # --- 3. Process Signatures (STILL base64) ---
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
        # --- 4. Process Report Item Photos (NEW FILE HANDLING LOGIC) ---
        # -----------------------------------------------------------------
        item_photo_count = 0
        
        # Iterate through the submitted items from the JSON payload (processed_items)
        for item_index, item in enumerate(processed_items):
            item_image_paths = []
            
            # The files were uploaded with the key pattern: 'photo-item-{itemIndex}-{photoIndex}'
            # We iterate through all uploaded_files to find the matching photos for this item
            for file_key, file_storage in uploaded_files.items():
                if file_key.startswith(f"photo-item-{item_index}-"):
                    
                    # Generate a unique filename and path
                    timestamp = int(time.time() * 1000)
                    filename = f"report_item_{item_index}_{item_photo_count}_{timestamp}.png"
                    path = os.path.join(IMAGE_UPLOAD_DIR, filename)
                    
                    # Ensure directory exists before saving
                    os.makedirs(IMAGE_UPLOAD_DIR, exist_ok=True)
                    
                    # Save the uploaded file (FileStorage object)
                    file_storage.save(path)
                    
                    item_image_paths.append(path)
                    temp_image_paths.append(path) # Add to cleanup list
                    item_photo_count += 1
            
            # Pass file paths, not Base64 data, to utility functions.
            item['image_paths'] = item_image_paths
            final_items.append(item)
            
        print(f"DEBUG_SUBMIT: Total photos received and processed: {item_photo_count}")
        # Note: You should have a separate route for downloading files, which is assumed here.
            
        # -----------------------------------------------------------------
        # --- 5. Generate Excel Report ---
        # -----------------------------------------------------------------
        excel_path, excel_filename = create_report_workbook(GENERATED_DIR, visit_info, final_items)
        
        # -----------------------------------------------------------------
        # --- 6. Generate PDF Report ---
        # -----------------------------------------------------------------
        pdf_path, pdf_filename = generate_visit_pdf(visit_info, final_items, GENERATED_DIR, logo_path=LOGO_ABSOLUTE_PATH)
        
        # --- 7. Send Email ---
        subject = f"INJAAZ Site Visit Report for {visit_info.get('building_name', 'Unknown')}"
        body = f"""The site visit report for {visit_info.get('building_name', 'Unknown')} on {visit_info.get('visit_date', 'N/A')} has been generated and is attached."""
        attachments = [excel_path, pdf_path]
        
        email_status, msg = send_outlook_email(subject, body, attachments, email_recipient)
        print("EMAIL_STATUS:", msg)

        # ----------------------
        # 8. Cleanup (UNCOMMENT THIS SECTION AFTER SUCCESSFUL TESTING)
        # ----------------------
        # for path in temp_image_paths:
        #     try:
        #         if os.path.isfile(path): 
        #             os.remove(path)
        #     except OSError as e:
        #         print(f"Error deleting temp image file {path}: {e}")

        # ----------------------
        # 9. RESPONSE TO FRONTEND
        # ----------------------
        # Assuming you have a route like: @site_visit_bp.route('/generated/<path:filename>')
        return jsonify({
            "status": "success",
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
                if os.path.isfile(path):
                    os.remove(path)
            except:
                pass
        
        # 11. ERROR RESPONSE TO FRONTEND
        return jsonify({
            "status": "error",
            "error": f"Internal server error: Failed to process report. Reason: {type(e).__name__}: {str(e)}"
        }), 500

# =================================================================
# 4. Route: Download Generated Files (Example)
# =================================================================
@site_visit_bp.route('/generated/<path:filename>')
def download_generated(filename):
    """Serves the generated files (PDF/Excel) from the GENERATED_DIR."""
    # Ensure the path is correct and secure
    return send_from_directory(GENERATED_DIR, filename, as_attachment=True)