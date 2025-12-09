"""
Cloudinary helpers used by the app.
Provides a safe version lookup and upload helper.
"""
import cloudinary
import cloudinary.uploader
from importlib import metadata

def get_version():
    try:
        return metadata.version("cloudinary")
    except Exception:
        return getattr(cloudinary, "VERSION", None)

def upload_file(file_obj, folder=None, public_id=None, **kwargs):
    options = {}
    if folder:
        options["folder"] = folder
    if public_id:
        options["public_id"] = public_id
    options.update(kwargs)
    return cloudinary.uploader.upload(file_obj, **options)