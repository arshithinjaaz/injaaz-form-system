# module_site_visit/__init__.py

from flask import Blueprint

site_visit_bp = Blueprint(
    'site_visit_bp', 
    __name__,
    template_folder='templates',
    static_folder='static',
    url_prefix='/site-visit-form' 
)

from . import routes