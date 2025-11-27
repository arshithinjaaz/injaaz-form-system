# module_site_visit/utils.py

import os
import time
import base64
# Import the global generated directory path
from config import GENERATED_DIR 

# --- HELPER FUNCTION: Decode and Save Base64 Images ---
# (Copy your save_base64_image function here and ensure it uses GENERATED_DIR)
def save_base64_image(base64_data, filename_prefix):
    """Decodes a Base64 string and saves it as a PNG file."""
    # Define image folder relative to the global GENERATED_DIR
    IMAGE_UPLOAD_DIR = os.path.join(GENERATED_DIR, "images")
    os.makedirs(IMAGE_UPLOAD_DIR, exist_ok=True)
    
    if not base64_data:
        return None
        
    try:
        if ',' not in base64_data:
            print(f"Error: Invalid Base64 format for {filename_prefix}")
            return None
            
        header, encoded = base64_data.split(',', 1)
        data = base64.b64decode(encoded)
        
        timestamp = int(time.time() * 1000)
        filename = f"{filename_prefix}_{timestamp}.png"
        path = os.path.join(IMAGE_UPLOAD_DIR, filename)

        with open(path, 'wb') as f:
            f.write(data)
            
        return path
    except Exception as e:
        print(f"Error decoding or saving image {filename_prefix}: {e}")
        return None