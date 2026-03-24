import secrets

from fastapi import Response

from app.core.config import settings

ACCESS_TOKEN_COOKIE_NAME = "access_token"
ACCESS_TOKEN_COOKIE_PATH = "/api"
CURRENT_ORGANIZATION_COOKIE_NAME = "current_organization_id"
CURRENT_ORGANIZATION_COOKIE_PATH = "/api"
CSRF_TOKEN_COOKIE_NAME = "csrf_token"
CSRF_TOKEN_COOKIE_PATH = "/"
REFRESH_TOKEN_COOKIE_NAME = "refresh_token"
REFRESH_TOKEN_COOKIE_PATH = "/api/auth"
SUPPORT_SESSION_COOKIE_NAME = "support_session_id"
SUPPORT_SESSION_COOKIE_PATH = "/api"


def set_access_token_cookie(response: Response, access_token: str) -> None:
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=not settings.is_local_env,
        samesite="lax",
        max_age=settings.jwt_access_ttl_minutes * 60,
        path=ACCESS_TOKEN_COOKIE_PATH,
    )


def clear_access_token_cookie(response: Response) -> None:
    response.delete_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        httponly=True,
        secure=not settings.is_local_env,
        samesite="lax",
        path=ACCESS_TOKEN_COOKIE_PATH,
    )


def set_current_organization_cookie(response: Response, organization_id: int) -> None:
    response.set_cookie(
        key=CURRENT_ORGANIZATION_COOKIE_NAME,
        value=str(organization_id),
        httponly=True,
        secure=not settings.is_local_env,
        samesite="lax",
        max_age=settings.jwt_refresh_ttl_days * 24 * 60 * 60,
        path=CURRENT_ORGANIZATION_COOKIE_PATH,
    )


def clear_current_organization_cookie(response: Response) -> None:
    response.delete_cookie(
        key=CURRENT_ORGANIZATION_COOKIE_NAME,
        httponly=True,
        secure=not settings.is_local_env,
        samesite="lax",
        path=CURRENT_ORGANIZATION_COOKIE_PATH,
    )


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_csrf_token_cookie(response: Response, csrf_token: str) -> None:
    response.set_cookie(
        key=CSRF_TOKEN_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        secure=not settings.is_local_env,
        samesite="lax",
        max_age=settings.jwt_refresh_ttl_days * 24 * 60 * 60,
        path=CSRF_TOKEN_COOKIE_PATH,
    )


def clear_csrf_token_cookie(response: Response) -> None:
    response.delete_cookie(
        key=CSRF_TOKEN_COOKIE_NAME,
        secure=not settings.is_local_env,
        samesite="lax",
        path=CSRF_TOKEN_COOKIE_PATH,
    )


def set_refresh_token_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=not settings.is_local_env,
        samesite="lax",
        max_age=settings.jwt_refresh_ttl_days * 24 * 60 * 60,
        path=REFRESH_TOKEN_COOKIE_PATH,
    )


def clear_refresh_token_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        httponly=True,
        secure=not settings.is_local_env,
        samesite="lax",
        path=REFRESH_TOKEN_COOKIE_PATH,
    )


def set_support_session_cookie(response: Response, session_id: int) -> None:
    response.set_cookie(
        key=SUPPORT_SESSION_COOKIE_NAME,
        value=str(session_id),
        httponly=True,
        secure=not settings.is_local_env,
        samesite="lax",
        max_age=settings.jwt_refresh_ttl_days * 24 * 60 * 60,
        path=SUPPORT_SESSION_COOKIE_PATH,
    )


def clear_support_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=SUPPORT_SESSION_COOKIE_NAME,
        httponly=True,
        secure=not settings.is_local_env,
        samesite="lax",
        path=SUPPORT_SESSION_COOKIE_PATH,
    )
