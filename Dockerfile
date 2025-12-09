# Start with a clean, stable version of Python
FROM python:3.11-slim

# Set the working directory inside the cloud package
WORKDIR /app

# Install the ingredients (Flask, gunicorn, Pillow)
COPY requirements.txt .
# Ensure we install Pillow now
RUN pip install --no-cache-dir -r requirements.txt

# Copy all your files (Injaaz.py, templates, static, etc.) into the package
COPY . . 

# Tell the cloud how to run your app, using gunicorn to start Injaaz.py
# CRITICAL FIX: Explicitly set --workers 1 to reserve maximum memory for the PDF generation process.
CMD exec gunicorn --timeout 60 --workers 1 --threads 4 Injaaz:app -b 0.0.0.0:$PORT