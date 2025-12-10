from redis import from_url
from rq import Queue
import config
from cloudinary_utils import safe_upload

redis_conn = from_url(config.REDIS_URL, socket_connect_timeout=5, socket_timeout=60)
q = Queue(name=config.RQ_QUEUE, connection=redis_conn)

def generate_and_upload_placeholder(data):
    # Replace this with your actual PDF/XLS generator call.
    # Example: local_path = my_pdf_module.make_pdf(data)
    local_path = "/tmp/example.pdf"
    result = safe_upload(local_path, options={"resource_type": "raw"})
    return result