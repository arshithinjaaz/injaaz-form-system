import os
import json
import base64
import time
import traceback
from flask import Blueprint, render_template, jsonify, request, url_for, send_from_directory
from werkzeug.datastructures import FileStorage # Import FileStorage for type hinting

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

# --- CRITICAL FIX 1: Define Absolute Path for Logo ---
LOGO_ABSOLUTE_PATH = os.path.join(BASE_DIR, 'static', 'INJAAZ.png') 
# --- END LOGO PATH ---


# Define the Blueprint
site_visit_bp = Blueprint(
    'site_visit_bp', 
    __name__,
    template_folder=TEMPLATE_ABSOLUTE_PATH,
    static_folder='static'
)


# --- NEW HELPER FUNCTION: Save Uploaded Files (for Item Photos) ---
def save_uploaded_file(file: FileStorage, filename_prefix):
    """Saves an uploaded FileStorage object to the IMAGE_UPLOAD_DIR."""
    os.makedirs(IMAGE_UPLOAD_DIR, exist_ok=True)
    
    if not file:
        print(f"DEBUG_SAVE: Invalid or empty file received for {filename_prefix}")
        return None
        
    try:
        # Preserve the original file extension if possible, or default to .png
        extension = os.path.splitext(file.filename)[1] if file.filename else '.png'
        
        timestamp = int(time.time() * 1000)
        filename = f"{filename_prefix}_{timestamp}{extension}"
        file_path = os.path.join(IMAGE_UPLOAD_DIR, filename)

        file.save(file_path) # Save the uploaded file directly
            
        print(f"DEBUG_SAVE: Successfully saved {filename} to {file_path}")
        
        return filename
        
    except Exception as e:
        print(f"Error saving uploaded file: {e}")
        return None

# --- EXISTING HELPER FUNCTION: Decode and Save Base64 Images/Signatures (Used ONLY for Signatures) ---
# Keep this function as is, since signatures are small and still sent as Base64 strings.
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
# 4. Route: Form Submission (Called by POST to /submit) - UPDATED FOR FormData
# =================================================================
@site_visit_bp.route('/submit', methods=['POST'])
def submit():
    # 1. Setup
    # CRITICAL CHANGE: Read the main data structure from request.form as a JSON string
    try:
        data_json_string = request.form.get('data')
        if not data_json_string:
            return jsonify({"error": "No main JSON data string received in 'data' field."}), 400
            
        data = json.loads(data_json_string)
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON format for the main form data."}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to process form data: {str(e)}"}), 400
        
    temp_image_paths = [] 
    final_items = [] 
    
    excel_path = None
    pdf_path = None
    
    # 2. Extract Data
    visit_info = data.get('visit_info', {})
    processed_items = data.get('report_items', []) 
    signatures = data.get('signatures', {}) 
    
    email_recipient = visit_info.get('email')
    
    try:
        # --- 3. Process Signatures (STILL using Base64 helper) ---
        tech_sig_data = signatures.get('tech_signature')
        opMan_sig_data = signatures.get('opMan_signature')
        
        # Save signature Base64 data (it's small, so this is fine)
        tech_sig_filename = save_base64_image(tech_sig_data, 'tech_sig')
        opMan_sig_filename = save_base64_image(opMan_sig_data, 'opman_sig')

        tech_sig_path = os.path.join(IMAGE_UPLOAD_DIR, tech_sig_filename) if tech_sig_filename else None
        opMan_sig_path = os.path.join(IMAGE_UPLOAD_DIR, opMan_sig_filename) if opMan_sig_filename else None

        if tech_sig_path: temp_image_paths.append(tech_sig_path)
        if opMan_sig_path: temp_image_paths.append(opMan_sig_path)

        visit_info['tech_signature_path'] = tech_sig_path
        visit_info['opMan_signature_path'] = opMan_sig_path

        # -----------------------------------------------------------------
        # --- 4. Process Report Item Photos (NEW LOGIC) ---
        # -----------------------------------------------------------------
        item_photo_count = 0
        
        # request.files is a dictionary-like object mapping field names to FileStorage objects
        # The frontend will send files with names like 'photo-item-0-0', 'photo-item-0-1', 'photo-item-1-0', etc.
        
        # Create a mapping of item_index to a list of file paths
        item_paths_map = {}
        for file_key, file_storage in request.files.items():
            # Check if the file_key matches our naming convention, e.g., 'photo-item-0-0'
            if file_key.startswith('photo-item-'):
                try:
                    # Extract item index (e.g., '0' from 'photo-item-0-0')
                    item_index = int(file_key.split('-')[2]) 
                    
                    # Create a safe prefix using item details from the data structure
                    # Use index to match file to item
                    if item_index < len(processed_items):
                        item = processed_items[item_index]
                        prefix = f"{visit_info.get('building_name', 'item')}_{item.get('asset', 'asset')}_{item_index}"
                        prefix = prefix.replace(' ', '_')[:30] 
                        
                        # Save the actual uploaded file using the new helper function
                        filename = save_uploaded_file(file_storage, prefix) 
                        
                        if filename:
                            path = os.path.join(IMAGE_UPLOAD_DIR, filename)
                            
                            if item_index not in item_paths_map:
                                item_paths_map[item_index] = []
                                
                            item_paths_map[item_index].append(path)
                            temp_image_paths.append(path) # Add to cleanup list
                            item_photo_count += 1
                        
                except (ValueError, IndexError):
                    # Should not happen if frontend logic is correct
                    print(f"ERROR: Could not parse item index from file key: {file_key}")
                    continue

        # Now, integrate the saved file paths back into the processed_items structure
        for index, item in enumerate(processed_items):
            # Assign the list of saved paths for this item, default to empty list
            item['image_paths'] = item_paths_map.get(index, []) 
            
            # The 'photos' field now contains the list of image keys (indices)
            # We don't need the Base64 data anymore, but we must make sure the image_paths are correct.
            # We can still pop 'photos' as it was just a temporary holder of the Base64 data in the old flow.
            item.pop('photos', None) 
            final_items.append(item)
            
        # --- DEBUGGING LINE ---
        print(f"DEBUG_SUBMIT: Total photos received and processed: {item_photo_count}")
        print(f"DEBUG_SUBMIT: Checking {len(temp_image_paths)} saved paths before PDF generation...")
        for path in temp_image_paths:
            print(f"DEBUG_SUBMIT: Path check: {path}, Exists: {os.path.exists(path)}")
        # --- END DEBUGGING LINE ---
            
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
        body = f"""...""" # Shortened body text
        attachments = [excel_path, pdf_path]
        
        email_status, msg = send_outlook_email(subject, body, attachments, email_recipient)
        print("EMAIL_STATUS:", msg)

        # ----------------------
        # 8. Cleanup (TEMPORARILY COMMENTED OUT FOR DEBUGGING)
        # ----------------------
        # for path in temp_image_paths:
        #    try:
        #        if os.path.isfile(path): 
        #            os.remove(path)
        #    except OSError as e:
        #        print(f"Error deleting temp image file {path}: {e}")

        # ----------------------
        # 9. RESPONSE TO FRONTEND
        # ----------------------
        return jsonify({
            "status": "success",
            "excel_url": url_for('download_generated', filename=excel_filename, _external=True), 
            "pdf_url": url_for('download_generated', filename=pdf_filename, _external=True)
        })

    except Exception as e:
        # ... (Error handling remains the same) ...
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

# Other routes (index, get_dropdown_data) remain unchanged