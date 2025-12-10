from flask import Flask, jsonify
import sys, traceback

try:
    # Try to import the main Flask app (the app object must be named "app")
    from Injaaz import app  # repo: Injaaz.py defines "app"
except Exception:
    # If import fails, log the full traceback to stderr (Render logs will show it)
    tb = traceback.format_exc()
    print("ERROR importing Injaaz.app:\n", tb, file=sys.stderr)

    # Provide a minimal fallback app so Gunicorn can start and serve diagnostics
    _fallback = Flask(__name__)

    @_fallback.route("/health")
    def health():
        # Return a 500-ish status so health checks indicate an issue,
        # but keep a JSON body for quick verification in browser.
        return jsonify({
            "status": "error",
            "message": "Application import failed. Check logs for details."
        }), 500

    @_fallback.route("/")
    def index():
        return jsonify({
            "status": "error",
            "message": "Application import failed. Check logs."
        }), 500

    app = _fallback