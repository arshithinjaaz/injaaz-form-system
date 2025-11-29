# module_site_civil/routes.py

import os
from flask import Blueprint, render_template, request, url_for, redirect, jsonify

# 1. IMPORT the report generation functions from the placeholder files.
# We explicitly reference the files within the package to ensure the app finds them.
# The dot (.) prefix means "from the current package", which is module_site_civil
from .site_civil_excel import create_excel_report 
from .site_civil_pdf import create_pdf_report 

# Define the Blueprint for the Civil module
site_civil_bp = Blueprint('site_civil_bp', __name__, 
                           # Tweak: Set the template folder explicitly for robustness
                           template_folder='templates') 

# --- Route to Render the Form (e.g., /site-civil/) ---
@site_civil_bp.route('/', methods=['GET'])
def index():
    """Renders the Site Visit Civil Report Form."""
    return render_template('civil_form.html')

# --- Route to Handle Form Submission (e.g., /site-civil/submit) ---
@site_civil_bp.route('/submit', methods=['POST'])
def submit_form():
    """Handles data submission and triggers report generation."""
    
    # 1. Get the form data
    form_data = request.form

    # 2. Trigger report generation using the IMPORTED functions
    excel_filename = create_excel_report(form_data)
    pdf_filename = create_pdf_report(form_data)

    # 3. Return the success page with download links
    return render_template('civil_success.html',
                           excel_file=excel_filename,
                           pdf_file=pdf_filename)

