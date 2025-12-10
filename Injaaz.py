from flask import Flask, jsonify, send_from_directory
from pathlib import Path
import config
from cloudinary_utils import init_cloudinary

def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.SECRET_KEY

    init_cloudinary(config)

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.route("/download/<path:filename>")
    def download(filename):
        from werkzeug.utils import secure_filename
        fn = secure_filename(filename)
        generated_dir = Path(config.GENERATED_DIR)
        file_path = (generated_dir / fn).resolve()
        try:
            file_path.relative_to(generated_dir.resolve())
        except Exception:
            return "Invalid filename", 400
        if not file_path.exists():
            return "Not found", 404
        return send_from_directory(str(generated_dir), fn, as_attachment=True)

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)