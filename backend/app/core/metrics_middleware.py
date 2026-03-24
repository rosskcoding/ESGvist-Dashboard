import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.metrics import ACTIVE_REQUESTS, REQUEST_COUNT, REQUEST_LATENCY, normalize_path


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        method = request.method
        ACTIVE_REQUESTS.labels(method=method).inc()
        start = time.perf_counter()
        try:
            response = await call_next(request)
            return response
        finally:
            duration = time.perf_counter() - start
            status = str(getattr(response, "status_code", 500)) if "response" in dir() else "500"
            path = normalize_path(request.url.path)
            REQUEST_LATENCY.labels(method=method, path=path, status=status).observe(duration)
            REQUEST_COUNT.labels(method=method, path=path, status=status).inc()
            ACTIVE_REQUESTS.labels(method=method).dec()
