from injaaz import create_app
import os

if __name__ == "__main__":
    app = create_app()
    host = os.environ.get("FLASK_RUN_HOST", "0.0.0.0")
    port = int(os.environ.get("FLASK_RUN_PORT", 8000))
    app.run(host=host, port=port, debug=True)