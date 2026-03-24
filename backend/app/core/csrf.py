import hmac
from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.auth_cookies import (
    ACCESS_TOKEN_COOKIE_NAME,
    CSRF_TOKEN_COOKIE_NAME,
    REFRESH_TOKEN_COOKIE_NAME,
)
from app.core.config import settings

CSRF_HEADER_NAME = "X-CSRF-Token"
ORIGIN_HEADER_NAME = "Origin"
REFERER_HEADER_NAME = "Referer"
SEC_FETCH_SITE_HEADER_NAME = "Sec-Fetch-Site"
ALLOWED_FETCH_SITES = {"same-origin", "same-site", "none"}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
EXEMPT_PATHS = {
    "/api/auth/login",
    "/api/auth/register",
}


def _is_exempt_path(path: str) -> bool:
    if path in EXEMPT_PATHS:
        return True
    return path.startswith("/api/auth/sso/providers/") and (
        path.endswith("/callback") or path.endswith("/start")
    )


def _normalize_origin(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def _allowed_origins(request: Request) -> set[str]:
    allowed = {origin.rstrip("/") for origin in settings.cors_origins}

    request_origin = _normalize_origin(str(request.base_url))
    if request_origin:
        allowed.add(request_origin)

    forwarded_proto = request.headers.get("X-Forwarded-Proto")
    forwarded_host = request.headers.get("X-Forwarded-Host")
    forwarded_origin = _normalize_origin(
        f"{forwarded_proto.split(',')[0].strip()}://{forwarded_host.split(',')[0].strip()}"
        if forwarded_proto and forwarded_host
        else None
    )
    if forwarded_origin:
        allowed.add(forwarded_origin)

    return allowed


def _has_trusted_origin_or_referer(request: Request) -> bool:
    trusted_origins = _allowed_origins(request)

    origin = _normalize_origin(request.headers.get(ORIGIN_HEADER_NAME))
    if origin:
        return origin in trusted_origins

    referer = _normalize_origin(request.headers.get(REFERER_HEADER_NAME))
    if referer:
        return referer in trusted_origins

    return False


def _has_trusted_fetch_site(request: Request) -> bool:
    fetch_site = request.headers.get(SEC_FETCH_SITE_HEADER_NAME)
    if not fetch_site:
        return True
    return fetch_site.strip().lower() in ALLOWED_FETCH_SITES


def _forbidden_response(request: Request, *, code: str, message: str) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(
        status_code=403,
        content={
            "error": {
                "code": code,
                "message": message,
                "requestId": request_id,
            }
        },
    )


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.method in SAFE_METHODS or _is_exempt_path(request.url.path):
            return await call_next(request)

        authorization = request.headers.get("Authorization", "")
        if authorization.startswith("Bearer "):
            return await call_next(request)

        has_auth_cookie = bool(
            request.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
            or request.cookies.get(REFRESH_TOKEN_COOKIE_NAME)
        )
        if not has_auth_cookie:
            return await call_next(request)

        csrf_cookie = request.cookies.get(CSRF_TOKEN_COOKIE_NAME)
        csrf_header = request.headers.get(CSRF_HEADER_NAME)
        if not (csrf_cookie and csrf_header and hmac.compare_digest(csrf_cookie, csrf_header)):
            return _forbidden_response(
                request,
                code="CSRF_VALIDATION_FAILED",
                message="CSRF token missing or invalid",
            )

        if not _has_trusted_fetch_site(request):
            return _forbidden_response(
                request,
                code="FETCH_METADATA_VALIDATION_FAILED",
                message="Sec-Fetch-Site header indicates an untrusted cross-site request",
            )

        if _has_trusted_origin_or_referer(request):
            return await call_next(request)

        return _forbidden_response(
            request,
            code="ORIGIN_VALIDATION_FAILED",
            message="Origin or Referer header missing or untrusted",
        )
