"""Security headers middleware.

Adds OWASP-recommended HTTP response headers to every response:
- Content-Security-Policy (CSP)
- Strict-Transport-Security (HSTS)
- X-Content-Type-Options
- X-Frame-Options
- Referrer-Policy
- Permissions-Policy

These complement CORS (which only controls cross-origin access) by hardening
the browser's security posture for same-origin and navigation contexts.
"""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject security headers into every HTTP response."""

    # CSP policy: self-only by default, allow inline styles (many UI frameworks
    # need them), block everything else.  connect-src allows API calls to self
    # and configured origins.
    CSP_POLICY = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)

        # CSP — prevent XSS, data injection
        response.headers["Content-Security-Policy"] = self.CSP_POLICY

        # HSTS — force HTTPS for 1 year, include subdomains
        # Only set when not in debug mode (local dev usually runs HTTP)
        if not getattr(settings, "debug", False):
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # Prevent MIME-type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking (redundant with CSP frame-ancestors but
        # needed for older browsers)
        response.headers["X-Frame-Options"] = "DENY"

        # Control referrer information leakage
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Restrict browser features the app doesn't need
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )

        return response
