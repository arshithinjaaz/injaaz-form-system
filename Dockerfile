# Start with a clean, stable version of Python
FROM python:3.11-slim

# Set the working directory inside the cloud package
WORKDIR /app

# Install the ingredients (Flask, gunicorn)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all your files (Injaaz.py, templates, static, etc.) into the package
COPY . . 

# Tell the cloud how to run your app, using gunicorn to start Injaaz.py
# The command is: gunicorn [file_name_without_.py]:[flask_app_variable]
# *** CORRECTION: Added --timeout 60 to prevent 502 Bad Gateway due to worker timeout ***
CMD exec gunicorn --timeout 60 Injaaz:app -b 0.0.0.0:$PORT