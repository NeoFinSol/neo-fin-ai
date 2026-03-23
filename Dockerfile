# Pin to specific Python version for reproducibility and security
# See: https://hub.docker.com/_/python/tags?page=1&name=3.11-slim
FROM python:3.11.6-slim

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV VIRTUAL_ENV=/app/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install system dependencies (cache this layer)
# libgl1: required for opencv-python (PDF table extraction)
# tesseract-ocr: required for pytesseract (OCR)
# poppler-utils: required for pdf2image (PDF to image conversion)
# ca-certificates: required for HTTPS requests (GigaChat/Qwen APIs)
# Using --no-install-recommends to minimize attack surface
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        poppler-utils \
        libgl1 \
        curl \
        ca-certificates \
    && update-ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Copy only requirements first (better layer caching)
COPY requirements.txt .

# Create virtual environment and install dependencies
RUN python -m venv $VIRTUAL_ENV \
    && $VIRTUAL_ENV/bin/pip install --upgrade pip setuptools wheel \
    && $VIRTUAL_ENV/bin/pip install --no-cache-dir -r requirements.txt

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

# Copy application code (changes more frequently)
COPY src ./src
COPY alembic.ini .
COPY migrations ./migrations
COPY entrypoint.sh .

# Make entrypoint executable and set ownership
RUN chmod +x entrypoint.sh \
    && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check (runs as appuser, port 8000 is accessible)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/system/health || exit 1

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
