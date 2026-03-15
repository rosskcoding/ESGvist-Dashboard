# ESG Report Creator - Export Worker Dockerfile
# Heavy worker image with Playwright + Chromium for PDF export
#
# Spec reference: Export v2 spec - PDF Exporter

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including fonts and Playwright requirements
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Playwright/Chromium dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    # Font configuration
    fontconfig \
    # Additional tools
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Noto fonts (comprehensive Unicode coverage including Cyrillic)
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-core \
    fonts-noto-extra \
    fonts-noto-mono \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -f -v

# Create non-root user (after font installation)
RUN useradd --create-home --shell /bin/bash appuser

# Copy dependency files and install Python packages
COPY apps/api/ ./apps/api/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ./apps/api \
    && pip install --no-cache-dir celery[redis]

# NOTE: Do NOT bake Playwright browsers into the image layer.
# They are large and can cause Docker Desktop disk pressure.
# Browsers are installed on container start into a mounted volume (see entrypoint).

# Copy application code
COPY apps/api/app ./app
COPY apps/worker/src ./worker

# Set ownership
RUN chown -R appuser:appuser /app

# Create directories for artifacts
RUN mkdir -p /app/app/static/builds && chown -R appuser:appuser /app/app/static

# Create Playwright browsers directory with correct ownership
# This ensures the mounted volume path has correct permissions
RUN mkdir -p /ms-playwright && chown -R appuser:appuser /ms-playwright

# Install Playwright browsers if missing, then run the worker.
# Copy entrypoint script and make it executable (before USER switch)
COPY infra/docker/export-worker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    # Playwright settings (mounted volume)
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD celery -A worker.celery_app inspect ping -d celery@$HOSTNAME || exit 1

ENTRYPOINT ["/entrypoint.sh"]

# Default command: Run Celery worker with limited concurrency for heavy PDF jobs.
# Uses dedicated `exports` queue for PDF/DOCX generation.
CMD ["celery", "-A", "worker.celery_app", "worker", "--loglevel=info", "--concurrency=2", "-Q", "exports"]
