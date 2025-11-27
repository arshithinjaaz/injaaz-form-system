# module_site_assessment/routes.py

import json
from flask import Blueprint, request, render_template, send_file, jsonify, abort
from io import BytesIO
from datetime import datetime

# Import the core logic functions from your individual files
from .site_assessment_pdf import generate_assessment_pdf
from .site_assessment_excel import generate_assessment_excel

# Create the Blueprint for the Site Assessment Form (Form 2)
site_assessment_bp = Blueprint('site_assessment', __name__, 
                               template_folder='templates')


@site_assessment_bp.route('/form', methods=['GET'])
def index():
    """Renders the main Site Assessment Form page."""
    # Looks for 'site_assessment_form.html' inside 'module_site_assessment/templates'
    return render_template('site_assessment_form.html')


@site_assessment_bp.route('/download-pdf', methods=['POST'])
def download_pdf():
    """
    Receives JSON data and returns the generated PDF file.
    """
    try:
        data = request.get_json()

        if not data:
            return "Error: No data received for PDF.", 400

        # Extract photos (base64 strings) and the rest of the assessment data
        photos_data = data.pop('photos', []) 
        assessment_info = data
        
        # Pass data to the logic function
        pdf_stream, pdf_filename = generate_assessment_pdf(assessment_info, photos_data)
        
        # Return the file stream
        response = send_file(
            pdf_stream,
            mimetype='application/pdf', 
            as_attachment=True,
            download_name=pdf_filename, 
            max_age=0 
        )
        return response

    except RuntimeError as e:
        # Handle errors raised specifically by ReportLab/PDF generation logic
        print(f"Error during PDF generation: {e}")
        return f"Internal Server Error: Could not generate PDF. Details: {e}", 500
    except Exception as e:
        print(f"Unexpected error during PDF generation: {e}")
        return f"Internal Server Error: Unexpected error: {e}", 500


@site_assessment_bp.route('/download-excel', methods=['POST'])
def download_excel():
    """
    Receives JSON data and returns the generated Excel file.
    """
    try:
        data = request.get_json()

        if not data:
            return "Error: No data received for Excel.", 400

        # Note: photos_data is not used but must be popped if present
        data.pop('photos', []) 
        assessment_info = data
        
        excel_stream, excel_filename = generate_assessment_excel(assessment_info) 
        
        response = send_file(
            excel_stream,
            # Standard MIME type for XLSX files
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
            as_attachment=True,
            download_name=excel_filename, 
            max_age=0 
        )
        
        return response

    except Exception as e:
        print(f"Error during Excel generation: {e}")
        return f"Internal Server Error: Could not generate Excel. Details: {e}", 500