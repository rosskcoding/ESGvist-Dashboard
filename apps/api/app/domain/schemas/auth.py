"""
Authentication schemas.

Security:
- Refresh tokens are stored in httpOnly cookies (XSS protection)
- refresh_token field in responses is kept empty for backward compatibility
- RefreshTokenRequest.refresh_token is optional (prefer cookie)
"""

from pydantic import EmailStr, Field

from .common import BaseSchema
from .user import UserDTO


class LoginRequest(BaseSchema):
    """Login request."""

    email: EmailStr
    password: str = Field(min_length=1)


class TokenResponse(BaseSchema):
    """
    Token response after successful login.

    Note: refresh_token is empty - actual token is set in httpOnly cookie.
    """

    access_token: str
    refresh_token: str = ""  # Empty - token is in httpOnly cookie
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token expiration in seconds")
    user: UserDTO


class RefreshTokenRequest(BaseSchema):
    """
    Refresh token request.

    refresh_token can be sent in body (backward compatibility) or
    omitted if using httpOnly cookie (preferred).
    """

    refresh_token: str | None = None





