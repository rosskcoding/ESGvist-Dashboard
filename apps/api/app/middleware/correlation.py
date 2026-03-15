"""
Correlation ID middleware for request tracing.

Provides:
- X-Request-ID header propagation (client → server → celery)
- Context variable for access within request lifecycle
- Automatic generation if not provided

Usage in logs:
    logger.info("Processing build", extra={"request_id": get_request_id()})
"""

import contextvars
import logging
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Context variable for request ID (thread-safe, async-safe)
_request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id",
    default="unknown"
)

__all__ = ["CorrelationMiddleware", "get_request_id", "set_request_id"]


class CorrelationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle correlation IDs for distributed tracing.

    Extracts X-Request-ID from incoming requests or generates new one.
    Stores in context variable for access during request processing.
    Returns X-Request-ID in response headers.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and add correlation ID."""
        # Extract or generate request ID
        request_id = request.headers.get("X-Request-ID") or request.headers.get("x-request-id")
        if not request_id:
            request_id = str(uuid4())

        # Store in context variable
        _request_id_var.set(request_id)

        # Log request with correlation ID
        logger.debug(
            f"{request.method} {request.url.path}",
            extra={"request_id": request_id}
        )

        # Process request
        response = await call_next(request)

        # Add correlation ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response


def get_request_id() -> str:
    """
    Get current request ID from context.

    Returns:
        Request ID string, or "unknown" if not set

    Example:
        >>> logger.info("Processing", extra={"request_id": get_request_id()})
    """
    return _request_id_var.get()


def set_request_id(request_id: str) -> None:
    """
    Set request ID in context (for testing/celery tasks).

    Args:
        request_id: Request ID to set

    Example (Celery task):
        >>> request_id = self.request.headers.get("x_request_id", str(uuid4()))
        >>> set_request_id(request_id)
    """
    _request_id_var.set(request_id)


