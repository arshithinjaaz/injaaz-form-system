# module_site_civil/routes.py

import os
from flask import Blueprint, render_template, request, url_for, redirect, jsonify

# Define the Blueprint for the Civil module
site_civil_bp = Blueprint('site_civil_bp', __name__)

# --- Route to Render the Form ---
@site_civil_bp.route('/', methods=['GET'])
def index():
    """Renders the Site Visit Civil Report Form."""
    # Renders the HTML template we will create next
    return render_template('civil_form.html')

# --- Route to Handle Form Submission ---
@site_civil_bp.route('/submit', methods=['POST'])
def submit_form():
    """Handles data submission and triggers report generation."""
    
    # 1. Get the form data
    form_data = request.form

    # 2. Trigger report generation
    # These functions will be defined in the excel/pdf scripts
    excel_filename = create_excel_report(form_data)
    pdf_filename = create_pdf_report(form_data)

    # 3. Return the success page with download links
    return render_template('civil_success.html',
                           excel_file=excel_filename,
                           pdf_file=pdf_filename)
    
# --- Placeholder Functions for Report Generation ---
# IMPORTANT: These functions must match the names used in submit_form()
def create_excel_report(data):
    # In a real app, this would call site_civil_excel.py functions
    # For now, return a placeholder file name
    return "Site_Civil_Report_TEMP.xlsx"

def create_pdf_report(data):
    # In a real app, this would call site_civil_pdf.py functions
    # For now, return a placeholder file name
    return "Site_Civil_Report_TEMP.pdf"
