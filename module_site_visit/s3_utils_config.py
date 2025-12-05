# File: /app/module_site_visit/s3_utils_config.py (or utils.py)

import os
import uuid
import base64
import logging
import boto3
from botocore.exceptions import ClientError

# --- Configuration & Initialization ---
# CRITICAL: These must be set as environment variables on your Render instance.
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1') # Use your actual region if different

# Initialize the S3 Client
try:
    s3_client = boto3.client('s3', region_name=AWS_REGION)
except ClientError as e:
    logging.error(f"S3 Client initialization failed: {e}")
    s3_client = None

# --- Constants ---
SIGNATURE_FOLDER = 'signatures/'
PHOTO_FOLDER = 'site-visit-photos/'
PRESIGNED_URL_EXPIRATION = 600 # 10 minutes

# =================================================================
# 1. Image Upload Helper: Generate Pre-Signed PUT URL (For Client)
#    Called by: /api/submit/metadata
# =================================================================

def generate_presigned_put_url(file_extension='.jpg', bucket_name=S3_BUCKET_NAME):
    """
    Generates a pre-signed URL for the client to directly upload a file to S3.
    """
    if not s3_client or not bucket_name:
        logging.error("S3 client not initialized or bucket name missing.")
        return None, None
        
    # Generate a unique key for the file
    file_key = f"{PHOTO_FOLDER}{uuid.uuid4()}{file_extension}"
    
    try:
        url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': bucket_name,
                'Key': file_key,
                # ContentType must match what the main.js client sends ('image/jpeg')
                'ContentType': 'image/jpeg' 
            },
            ExpiresIn=PRESIGNED_URL_EXPIRATION
        )
        return url, file_key
    except ClientError as e:
        logging.error(f"Error generating presigned URL for {file_key}: {e}")
        return None, None

# =================================================================
# 2. Signature Upload Helper: Decode Base64 and Upload to S3 (Server)
#    Called by: /api/submit/metadata
# =================================================================

def decode_base64_to_s3(base64_data_url, file_prefix, bucket_name=S3_BUCKET_NAME):
    """
    Decodes a base64 Data URL (like signature data) and uploads it directly to S3.
    Returns the S3 key on success.
    """
    if not base64_data_url or not s3_client or not bucket_name:
        return None
        
    try:
        # Check if the data is a proper Data URL (data:image/...)
        if ',' not in base64_data_url:
             # Assume it's just raw base64 data without the header
             encoded = base64_data_url
             mime_type = 'image/png' # Assume default signature format
        else:
             header, encoded = base64_data_url.split(',', 1)
             mime_type = header.split(';')[0].split(':')[1]
             
        data = base64.b64decode(encoded)
        file_extension = '.' + mime_type.split('/')[1]
        
        # Determine the S3 key
        s3_key = f"{SIGNATURE_FOLDER}{file_prefix}-{uuid.uuid4()}{file_extension}"
        
        # Upload the signature data (buffer/bytes) directly to S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=data,
            ContentType=mime_type,
            ACL='private' 
        )
        logging.info(f"Signature successfully uploaded to S3 key: {s3_key}")
        return s3_key
    except Exception as e:
        logging.error(f"Failed to upload base64 signature to S3 for {file_prefix}: {e}")
        return None