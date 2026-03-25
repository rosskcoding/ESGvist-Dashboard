"""Gunicorn configuration for production deployment.

Usage:
    gunicorn app.main:app -c gunicorn.conf.py

For development, continue using:
    uvicorn app.main:app --reload --port 8001
"""

import multiprocessing
import os

# Workers: 2-4x CPU cores is the sweet spot for async workers.
# Default to 4 or (2 * cores + 1), whichever is smaller.
_cpu_count = multiprocessing.cpu_count()
workers = int(os.getenv("WEB_CONCURRENCY", min(4, 2 * _cpu_count + 1)))

# Use uvicorn's async worker class (required for FastAPI/async)
worker_class = "uvicorn.workers.UvicornWorker"

# Bind
bind = os.getenv("BIND", "0.0.0.0:8001")

# Timeouts
timeout = 120          # Kill worker if request takes >120s
graceful_timeout = 30  # Wait 30s for in-flight requests on shutdown
keepalive = 5          # Keep TCP connections alive between requests

# Logging
accesslog = "-"        # stdout
errorlog = "-"         # stderr
loglevel = os.getenv("LOG_LEVEL", "info")

# Limits
max_requests = 1000          # Restart worker after 1000 requests (prevent memory leaks)
max_requests_jitter = 100    # Add jitter so workers don't restart simultaneously

# Preload app for faster worker startup and shared memory
preload_app = True
