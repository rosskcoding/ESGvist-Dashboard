import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings

logger = structlog.get_logger("app.requests")


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        start_time = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start_time) * 1000, 2)

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Request-Duration"] = str(duration_ms)

        # Extract user context if available
        user_id = None
        organization_id = None
        if hasattr(request.state, "user_id"):
            user_id = request.state.user_id
        if hasattr(request.state, "organization_id"):
            organization_id = request.state.organization_id

        # Also try to extract from headers for cases where state isn't set yet
        if organization_id is None:
            org_header = request.headers.get("X-Organization-Id")
            if org_header:
                try:
                    organization_id = int(org_header)
                except (ValueError, TypeError):
                    pass

        log_data = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "user_id": user_id,
            "organization_id": organization_id,
        }

        if response.status_code >= 500:
            logger.error("http_request", **log_data)
        elif response.status_code >= 400:
            logger.warning("http_request", **log_data)
        elif duration_ms >= settings.slow_request_warning_ms:
            logger.warning("http_request_slow", **log_data)
        else:
            logger.info("http_request", **log_data)

        return response
