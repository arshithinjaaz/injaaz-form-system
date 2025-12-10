# Example wsgi.py — make sure gunicorn loads `app`
# Adjust the import path if your app object is defined elsewhere.

from Injaaz import app  # if your Flask app instance is created in Injaaz.py
from flask import redirect, url_for, jsonify

# Provide / (root) -> redirect to /health (avoids a 404)
@app.route("/")
def index():
    return redirect(url_for("health"))

# Ensure /health exists and returns JSON 200
@app.route("/health")
def health():
    return jsonify({"status": "ok"})