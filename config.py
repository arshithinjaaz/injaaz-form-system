import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

GENERATED_DIR = Path(os.getenv("GENERATED_DIR", BASE_DIR / "generated"))

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
FLASK_ENV = os.getenv("FLASK_ENV", "production")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
RQ_QUEUE = os.getenv("RQ_QUEUE", "default")

CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "")

GUNICORN_WORKERS = int(os.getenv("GUNICORN_WORKERS", "1"))
GUNICORN_THREADS = int(os.getenv("GUNICORN_THREADS", "4"))
GUNICORN_TIMEOUT = int(os.getenv("GUNICORN_TIMEOUT", "120"))