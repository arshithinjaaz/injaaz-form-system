import os
import time
import base64
import uuid
import tempfile
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from typing import Optional, Tuple

# =================================================================
# --- AWS S3 CLIENT SETUP ---
# =================================================================

# IMPORTANT: These environment variables must be set in your Render dashboard
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', 'injaaz-files')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')

# Initialize Boto3 Client - Reads credentials from environment variables automatically
s3_client = boto3.client(
    's3', 
    region_name=AWS_REGION, 
    # Critical for direct PUT uploads from the client
    config=Config(signature_version='s3v4') 
)

# =================================================================
# --- 1. UPLOAD HELPERS (Used by routes.py) ---
# =================================================================

def generate_presigned_put_url(file_extension: str) -> Tuple[Optional[str], Optional[str]]:
    """Generates a secure PUT presigned URL for direct client upload to S3."""
    
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    object_key = f"site-visit-photos/{unique_filename}"
    
    try:
        url = s3_client.generate_presigned_url(
            ClientMethod='put_object',
            Params={'Bucket': S3_BUCKET_NAME, 'Key': object_key},
            # URL is valid for 1 hour
            ExpiresIn=3600 
        )
        return url, object_key
    except ClientError as e:
        print(f"Error generating presigned URL: {e}")
        return None, None


def decode_base64_to_s3(base64_data: str, filename_prefix: str) -> Optional[str]:
    """Decodes base64 data (like signature) and uploads the binary data directly to S3."""
    if not base64_data or not isinstance(base64_data, str) or len(base64_data) < 100:
        return None
        
    try:
        if ',' in base64_data:
            # Strip the data:image/png;base64, header
            base64_data = base64_data.split(',', 1)[1]
        
        img_data = base64.b64decode(base64_data)
        
        # Define the S3 Key/Path
        object_key = f"signatures/{filename_prefix}_{int(time.time() * 1000)}.png"

        # Upload binary data directly to S3
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=object_key,
            Body=img_data,
            ContentType='image/png'
        )
        
        del img_data # Explicitly release the decoded image data from memory
        
        print(f"DEBUG_S3_SIG: Successfully uploaded {filename_prefix} to S3 key: {object_key}")
        return object_key # Return the S3 key
        
    except Exception as e:
        print(f"Error decoding/saving base64 image to S3: {e}")
        return None

# =================================================================
# --- 2. DOWNLOAD HELPER (Used by pdf_generator.py) ---
# =================================================================

def download_s3_file_to_temp(s3_key: str) -> Optional[str]:
    """
    Downloads an S3 object to a uniquely named temporary local file.
    Returns the local path or None on failure.
    """
    if not s3_key:
        return None
        
    # Create a unique temporary file path and close the file descriptor
    temp_file_descriptor, temp_file_path = tempfile.mkstemp()
    os.close(temp_file_descriptor) 
    
    try:
        # Download the file from S3 to the temporary path
        s3_client.download_file(
            Bucket=S3_BUCKET_NAME, 
            Key=s3_key, 
            Filename=temp_file_path
        )
        return temp_file_path
    except Exception as e:
        print(f"S3 Download Error for key {s3_key}: {e}")
        # Clean up the empty temporary file if the download failed
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        return None
