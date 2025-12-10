# Use official slim Python image
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install runtime system deps needed by Pillow/reportlab
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies from requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app code
COPY . .

# Create folder for generated files and non-root user
RUN mkdir -p /app/generated /app/generated/images && \
    useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 5000

# Default command for web service
CMD ["gunicorn", "--timeout", "120", "--workers", "1", "--threads", "4", "wsgi:app", "-b", "0.0.0.0:5000"]