# Injaaz.py

import os
from flask import Flask, send_from_directory, abort, render_template

# 1. Import the Blueprint object for Form 1 (Site Visit Report)
# Ensure you have 'module_site_visit/routes.py' defining 'site_visit_bp'
from module_site_visit.routes import site_visit_bp

# 2. Import the Blueprint object for Form 2 (The new Site Assessment Report)
# This module was created in the previous step ('module_site_assessment/routes.py')
from module_site_assessment.routes import site_assessment_bp

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GENERATED_DIR_NAME = "generated"
GENERATED_DIR = os.path.join(BASE_DIR, GENERATED_DIR_NAME)

# Initialize Flask App
app = Flask(__name__)

# Ensure required directories exist at startup
os.makedirs(GENERATED_DIR, exist_ok=True)
os.makedirs(os.path.join(GENERATED_DIR, "images"), exist_ok=True)

# --- Blueprint Registration ---
# Register Blueprint for Form 1
app.register_blueprint(site_visit_bp, url_prefix='/site-visit')

# Register Blueprint for Form 2 (New Site Assessment)
app.register_blueprint(site_assessment_bp, url_prefix='/site-assessment')

# --- Root Route Renders Dashboard ---
@app.route('/')
def index():
    """Renders the dashboard page with links to available forms."""
    # This renders the updated dashboard.html
    return render_template('dashboard.html')

# --- Shared Route: File Download ---
@app.route(f'/{GENERATED_DIR_NAME}/<path:filename>')
def download_generated(filename):
    """Allows direct download of files from the 'generated' directory."""

    global GENERATED_DIR

    full_path = os.path.join(GENERATED_DIR, filename)

    if not os.path.exists(full_path):
        print(f"File not found at: {full_path}")
        abort(404)

    return send_from_directory(GENERATED_DIR, filename, as_attachment=True)

# --- Run Application ---
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')