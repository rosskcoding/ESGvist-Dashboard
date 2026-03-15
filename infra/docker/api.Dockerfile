# ESG Report Creator - API Dockerfile
# Multi-stage build for production

# ===== Builder Stage =====
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy API source (pyproject + app code) so pip can build the package
COPY apps/api/ ./apps/api/

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ./apps/api

# ===== Runtime Base Stage =====
FROM python:3.11-slim AS runtime

WORKDIR /app

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY apps/api/app ./app
COPY apps/api/alembic ./alembic
COPY apps/api/alembic.ini .

# Set ownership
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ===== Dev Stage (pytest included) =====
# Used by docker compose (infra/compose.yml) for local development/testing.
FROM runtime AS dev

USER root
RUN pip install --no-cache-dir pytest pytest-asyncio pytest-cov

# Include tests in the image so pytest works even without bind mounts.
COPY apps/api/tests ./tests
RUN chown -R appuser:appuser /app/tests

USER appuser

# ===== Production Stage =====
# Keep production as the default/last stage.
FROM runtime AS production

