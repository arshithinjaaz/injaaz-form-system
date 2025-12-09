"""
injaaz package - app factory
"""
from flask import Flask

def create_app(config_object=None):
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_mapping(SECRET_KEY="dev-secret")
    if config_object:
        app.config.from_object(config_object)

    # try to load .env config
    try:
        from .config import load_config
        load_config(app)
    except Exception:
        pass

    # try to register your existing module_site_visit blueprint if present
    try:
        from module_site_visit.routes import site_visit_bp  # adjust name if different
        app.register_blueprint(site_visit_bp)
    except Exception:
        pass

    return app