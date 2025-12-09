import os
import json
import tempfile
import redis

REDIS_URL = os.environ.get('REDIS_URL', '')
use_redis = bool(REDIS_URL)

if use_redis:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
else:
    redis_client = None

def save_report_state(report_id, data):
    """
    Save state either to Redis (preferred) or to temp file (fallback).
    """
    if use_redis and redis_client:
        key = f"report_state:{report_id}"
        redis_client.set(key, json.dumps(data))
    else:
        temp_record_path = os.path.join(tempfile.gettempdir(), f"{report_id}.json")
        with open(temp_record_path, 'w') as f:
            json.dump(data, f)

def get_report_state(report_id):
    """
    Retrieve and (optionally) delete state. Returns dict or None.
    """
    if use_redis and redis_client:
        key = f"report_state:{report_id}"
        raw = redis_client.get(key)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None
    else:
        temp_record_path = os.path.join(tempfile.gettempdir(), f"{report_id}.json")
        if not os.path.exists(temp_record_path):
            return None
        try:
            with open(temp_record_path, 'r') as f:
                record = json.load(f)
            # Keep file so other endpoints can still read; delete only when appropriate
            return record
        except Exception:
            return None