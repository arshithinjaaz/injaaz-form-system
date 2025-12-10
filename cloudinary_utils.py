import time
import logging
import cloudinary
from cloudinary.uploader import upload as cloudinary_upload

logger = logging.getLogger(__name__)

def init_cloudinary(config):
    cloudinary.config(
        cloud_name=config.CLOUDINARY_CLOUD_NAME,
        api_key=config.CLOUDINARY_API_KEY,
        api_secret=config.CLOUDINARY_API_SECRET,
        secure=True
    )

def safe_upload(filepath: str, options: dict = None, max_retries: int = 3, timeout: int = 30):
    options = options or {}
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            return cloudinary_upload(filepath, timeout=timeout, **options)
        except Exception as e:
            last_exc = e
            logger.exception("Cloudinary upload attempt %s failed for %s", attempt, filepath)
            if attempt < max_retries:
                time.sleep(2 ** attempt)
    raise last_exc