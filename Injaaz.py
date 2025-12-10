# Injaaz.py (snippet showing the top of the file)
import os
from flask import Flask, send_from_directory, abort, render_template

# Create the Flask app immediately so the module exposes `app` even if later imports fail.
app = Flask(__name__)

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GENERATED_DIR_NAME = "generated"
GENERATED_DIR = os.path.join(BASE_DIR, GENERATED_DIR_NAME)

# 1. Import the Blueprint object for Form 1 (Site Visit Report)
# Ensure 'module_site_visit/routes.py' is robust to import-time failures (see below).
from module_site_visit.routes import site_visit_bp

# 2. Import the Blueprint object for Form 2 (The new Site Assessment Report)
from module_site_assessment.routes import site_assessment_bp

# 3. Import the Blueprint object for Form 3 (New Site Civil Report)
from module_site_civil.routes import site_civil_bp

# Ensure required directories exist at startup
os.makedirs(GENERATED_DIR, exist_ok=True)
os.makedirs(os.path.join(GENERATED_DIR, "images"), exist_ok=True)

# --- Blueprint Registration ---
app.register_blueprint(site_visit_bp, url_prefix='/site-visit')
app.register_blueprint(site_assessment_bp, url_prefix='/site-assessment')
app.register_blueprint(site_civil_bp, url_prefix='/site-civil')

# --- Root Route Renders Dashboard ---
@app.route('/')
def index():
    """Renders the dashboard page with links to available forms."""
    return render_template('dashboard.html')

# --- Shared Route: File Download ---
@app.route(f'/{GENERATED_DIR_NAME}/<path:filename>')
def download_generated(filename):
    full_path = os.path.join(GENERATED_DIR, filename)
    if not os.path.exists(full_path):
        print(f"File not found at: {full_path}")
        abort(404)
    return send_from_directory(GENERATED_DIR, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')