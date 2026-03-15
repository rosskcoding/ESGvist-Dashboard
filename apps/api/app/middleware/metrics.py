"""
Prometheus metrics middleware for observability.

Provides:
- HTTP request metrics (duration, count, errors)
- Build pipeline metrics (duration, errors)
- Artifact generation metrics (duration by format)
- Storage usage gauge

Metrics endpoint: GET /metrics (for Prometheus scraper)
"""

import time
from typing import Callable

from prometheus_client import Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

__all__ = [
    "MetricsMiddleware",
    "http_requests_total",
    "http_request_duration_seconds",
    "build_duration_seconds",
    "artifact_generation_seconds",
    "build_errors_total",
    "storage_usage_bytes",
]

# HTTP Metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"]
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0)
)

# Build Pipeline Metrics
build_duration_seconds = Histogram(
    "build_duration_seconds",
    "Build pipeline duration in seconds",
    ["build_type", "status"],
    buckets=(10, 30, 60, 120, 300, 600, 1200, 1800)
)

build_errors_total = Counter(
    "build_errors_total",
    "Total build errors",
    ["error_code"]
)

# Artifact Generation Metrics
artifact_generation_seconds = Histogram(
    "artifact_generation_seconds",
    "Artifact generation duration in seconds",
    ["format", "status"],
    buckets=(5, 15, 30, 60, 120, 300, 600)
)

# Storage Metrics
storage_usage_bytes = Gauge(
    "storage_usage_bytes",
    "Total storage used by builds in bytes",
    ["storage_type"]  # local, s3
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to collect HTTP request metrics.

    Tracks request count, duration, and status codes.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and record metrics."""
        # Skip metrics endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)

        # Record start time
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration = time.time() - start_time

        # Normalize path (remove UUIDs, IDs for cardinality)
        path = self._normalize_path(request.url.path)

        # Record metrics
        http_requests_total.labels(
            method=request.method,
            path=path,
            status_code=response.status_code
        ).inc()

        http_request_duration_seconds.labels(
            method=request.method,
            path=path
        ).observe(duration)

        return response

    def _normalize_path(self, path: str) -> str:
        """
        Normalize path to reduce cardinality.

        Replaces UUIDs and numeric IDs with placeholders.

        Examples:
            /api/v1/reports/123e4567-... → /api/v1/reports/{id}
            /api/v1/blocks/42 → /api/v1/blocks/{id}
        """
        import re

        # Replace UUIDs
        path = re.sub(
            r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            '/{id}',
            path,
            flags=re.IGNORECASE
        )

        # Replace numeric IDs
        path = re.sub(r'/\d+', '/{id}', path)

        return path


def metrics_endpoint() -> Response:
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus exposition format.

    Usage:
        app.add_route("/metrics", metrics_endpoint, methods=["GET"])
    """
    return Response(
        content=generate_latest(),
        media_type="text/plain; version=0.0.4"
    )


