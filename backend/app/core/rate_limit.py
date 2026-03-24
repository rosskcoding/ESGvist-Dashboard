"""General-purpose API rate limiter.

Enforces a per-user (or per-IP for unauthenticated requests) request limit
across all endpoints.  This is separate from the AI-specific rate limiter
in ``ai_gate.py`` which has per-role granularity.

Default: 100 requests per minute per identity.
"""

from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings

# Paths exempt from rate limiting
_EXEMPT_PREFIXES = ("/api/health", "/docs", "/redoc", "/openapi.json")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter (in-memory, per-process).

    Keyed by ``user_id`` (from request state, set by auth middleware) or
    by client IP for unauthenticated requests.

    Limits are configured via ``settings.rate_limit_per_minute``.
    """

    _buckets: dict[str, deque[datetime]] = defaultdict(deque)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip health and docs endpoints
        if any(request.url.path.startswith(p) for p in _EXEMPT_PREFIXES):
            return await call_next(request)

        limit = getattr(settings, "rate_limit_per_minute", 100)

        # Build identity key: prefer user_id, fallback to IP
        identity = f"ip:{request.client.host}" if request.client else "ip:unknown"
        if hasattr(request.state, "user_id") and request.state.user_id:
            identity = f"user:{request.state.user_id}"

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=1)

        bucket = self._buckets[identity]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

        if len(bucket) >= limit:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": f"Rate limit exceeded ({limit} requests/minute). Try again shortly.",
                    }
                },
                headers={"Retry-After": "60"},
            )

        bucket.append(now)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - len(bucket)))
        return response
