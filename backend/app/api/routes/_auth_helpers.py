from fastapi import Request

from app.schemas.auth import TokenResponse


def is_browser_auth_request(request: Request) -> bool:
    if request.headers.get("Origin") or request.headers.get("Referer"):
        return True
    return bool(request.headers.get("Sec-Fetch-Mode") or request.headers.get("Sec-Fetch-Site"))


def serialize_auth_response(request: Request, tokens: TokenResponse) -> TokenResponse:
    if is_browser_auth_request(request):
        return TokenResponse(token_type=tokens.token_type, session_mode="cookie")
    return TokenResponse(
        access_token=tokens.access_token,
        token_type=tokens.token_type,
        session_mode="token",
    )


def resolve_client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or None
    if request.client:
        return request.client.host
    return None


def resolve_user_agent(request: Request) -> str | None:
    user_agent = request.headers.get("User-Agent")
    if not user_agent:
        return None
    normalized = user_agent.strip()
    return normalized[:512] if normalized else None
