# ESG Report Creator - Worker Dockerfile
# For background tasks (translation, export)

FROM python:3.11-slim

WORKDIR /app

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files and install
COPY apps/api/ ./apps/api/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ./apps/api \
    && pip install --no-cache-dir celery[redis]

# Copy application code
COPY apps/api/app ./app
COPY apps/worker/src ./worker

# Set ownership
RUN chown -R appuser:appuser /app

# Copy entrypoint script and make it executable
COPY infra/docker/worker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

ENTRYPOINT ["/entrypoint.sh"]

# Default command (can be overridden)
CMD ["celery", "-A", "worker.celery_app", "worker", "--loglevel=info"]
