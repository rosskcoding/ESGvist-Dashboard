"""
Authentication API endpoints.

Security features:
- httpOnly cookies for refresh tokens (XSS protection)
- Server-side token storage with revocation
- Token rotation (one-time use)
- Secure cookie settings (SameSite, Secure in production)
- Double-submit cookie CSRF protection
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.domain.models import Company, CompanyMembership, RoleAssignment, User
from app.domain.models.enums import AssignableRole, ScopeType
from app.domain.schemas import (
    LoginRequest,
    PaginatedResponse,
    RefreshTokenRequest,
    TokenResponse,
    UserCompanyDTO,
    UserCreate,
    UserDTO,
    UserUpdate,
)
from app.infra.database import get_session
from app.middleware.csrf import delete_csrf_cookie, generate_csrf_token, set_csrf_cookie
from app.services.auth import AuthService, get_current_user, hash_password


# Cookie settings
REFRESH_TOKEN_COOKIE_NAME = "refresh_token"
REFRESH_TOKEN_MAX_AGE = settings.refresh_token_expire_days * 24 * 60 * 60  # seconds


def _get_cookie_settings() -> dict:
    """Get secure cookie settings based on environment."""
    # In production, use secure cookies
    is_production = settings.environment == "production"

    return {
        "key": REFRESH_TOKEN_COOKIE_NAME,
        "httponly": True,  # Prevent XSS access
        "samesite": "lax",  # CSRF protection
        "secure": is_production,  # HTTPS only in production
        "max_age": REFRESH_TOKEN_MAX_AGE,
        "path": "/api/v1/auth",  # Only sent to auth endpoints
    }


async def _load_user_companies(
    session: AsyncSession,
    user_id: UUID,
) -> list[UserCompanyDTO]:
    """
    Load a user's company memberships with company names.

    Used to populate UserDTO.companies for frontend navigation (/company).
    Checks RoleAssignment for corporate_lead role.
    """
    result = await session.execute(
        select(CompanyMembership, Company)
        .join(Company, CompanyMembership.company_id == Company.company_id)
        .where(CompanyMembership.user_id == user_id)
        .order_by(CompanyMembership.created_at_utc.asc())
    )

    companies: list[UserCompanyDTO] = []
    for membership, company in result.all():
        # Load all role assignments for this user in this company.
        # NOTE: role can be scoped (company/report/section). For UI navigation we expose
        # a flattened list of role names present in the company.
        roles_result = await session.execute(
            select(RoleAssignment.role).where(
                RoleAssignment.user_id == user_id,
                RoleAssignment.company_id == membership.company_id,
            )
        )
        role_values = sorted({r[0].value for r in roles_result.fetchall() if r and r[0] is not None})

        # Corporate Lead flag (used by frontend to unlock company admin screens)
        is_corporate_lead = AssignableRole.CORPORATE_LEAD.value in role_values

        companies.append(
            UserCompanyDTO(
                company_id=membership.company_id,
                company_name=company.name,
                is_corporate_lead=is_corporate_lead,
                is_active=membership.is_active,
                roles=role_values,
            )
        )
    return companies

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Security scheme
security = HTTPBearer(auto_error=False)


async def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthService:
    """Dependency to get AuthService."""
    return AuthService(session)


async def get_current_user_required(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """
    Dependency to get current authenticated user.

    Raises 401 if not authenticated.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await get_current_user(credentials.credentials, session)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_user_optional(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User | None:
    """
    Dependency to get current user (optional).

    Returns None if not authenticated.
    """
    if not credentials:
        return None

    return await get_current_user(credentials.credentials, session)


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    response: Response,
    http_request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TokenResponse:
    """
    Authenticate user and return JWT tokens.

    - **email**: User email
    - **password**: User password

    Returns access token in response body.
    Refresh token is set as httpOnly cookie for security.
    """
    ip_address = http_request.client.host if http_request.client else None
    user_agent = http_request.headers.get("user-agent")

    result = await auth_service.authenticate(request, ip_address, user_agent)
    if not result:
        # AuthService may have written audit events (e.g. login_failed).
        # Persist them even though we return 401 (avoid rollback-on-exception).
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_response, refresh_jwt = result

    # Enrich user with company memberships for frontend navigation
    token_response.user.companies = await _load_user_companies(
        session, token_response.user.user_id
    )

    # Set refresh token as httpOnly cookie
    cookie_settings = _get_cookie_settings()
    response.set_cookie(value=refresh_jwt, **cookie_settings)

    # Set CSRF token cookie (double-submit cookie pattern)
    csrf_token = generate_csrf_token()
    set_csrf_cookie(response, csrf_token)

    return token_response


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    response: Response,
    http_request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    session: Annotated[AsyncSession, Depends(get_session)],
    refresh_token_cookie: str | None = Cookie(default=None, alias=REFRESH_TOKEN_COOKIE_NAME),
    request_body: RefreshTokenRequest | None = None,
) -> TokenResponse:
    """
    Refresh access token using refresh token.

    Accepts refresh token from:
    1. httpOnly cookie (preferred, secure)
    2. Request body (backward compatibility)

    Returns new access token and rotates refresh token.
    """
    # Prefer cookie, fall back to body for backward compatibility
    refresh_token_value = refresh_token_cookie
    if not refresh_token_value and request_body:
        refresh_token_value = request_body.refresh_token

    if not refresh_token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    ip_address = http_request.client.host if http_request.client else None
    user_agent = http_request.headers.get("user-agent")

    result = await auth_service.refresh_tokens(
        refresh_token_value,
        ip_address,
        user_agent,
    )

    if not result:
        # Clear invalid cookie
        response.delete_cookie(
            REFRESH_TOKEN_COOKIE_NAME,
            path="/api/v1/auth",
        )
        # AuthService may have revoked token families / written audit events.
        # Persist them even though we return 401 (avoid rollback-on-exception).
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_response, new_refresh_jwt = result

    # Enrich user with company memberships
    token_response.user.companies = await _load_user_companies(
        session, token_response.user.user_id
    )

    # Set new refresh token cookie (rotation)
    cookie_settings = _get_cookie_settings()
    response.set_cookie(value=new_refresh_jwt, **cookie_settings)

    # Refresh CSRF token on token rotation (security best practice)
    csrf_token = generate_csrf_token()
    set_csrf_cookie(response, csrf_token)

    return token_response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    current_user: Annotated[User, Depends(get_current_user_required)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    refresh_token_cookie: str | None = Cookie(default=None, alias=REFRESH_TOKEN_COOKIE_NAME),
    all_devices: bool = Query(default=False, description="Logout from all devices"),
) -> None:
    """
    Logout current user.

    - Revokes refresh token(s) on server
    - Clears refresh token cookie

    Use `all_devices=true` to logout from all devices (revokes all tokens).
    """
    from app.services.auth import decode_token

    if all_devices:
        # Revoke all user's refresh tokens
        await auth_service.revoke_all_user_tokens(current_user.user_id)
    elif refresh_token_cookie:
        # Revoke only current refresh token
        payload = decode_token(refresh_token_cookie)
        if payload and payload.get("jti"):
            await auth_service.revoke_refresh_token(payload["jti"])

    # Clear cookies
    response.delete_cookie(
        REFRESH_TOKEN_COOKIE_NAME,
        path="/api/v1/auth",
    )
    delete_csrf_cookie(response)


@router.get("/me", response_model=UserDTO)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user_required)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserDTO:
    """
    Get current authenticated user info.
    """
    user_dto = UserDTO.model_validate(current_user)
    user_dto.companies = await _load_user_companies(session, current_user.user_id)
    return user_dto


@router.get("/users", response_model=PaginatedResponse[UserDTO])
async def list_users(
    current_user: Annotated[User, Depends(get_current_user_required)],
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
) -> PaginatedResponse[UserDTO]:
    """
    List all users with pagination. Requires superuser.

    Used for admin panel to add members and assign roles.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only platform admins can list users",
        )

    # Count total
    count_query = select(func.count()).select_from(User)
    total = (await session.execute(count_query)).scalar() or 0

    # Fetch page
    offset = (page - 1) * page_size
    query = select(User).order_by(User.created_at_utc.desc()).offset(offset).limit(page_size)
    result = await session.execute(query)
    users = list(result.scalars().all())

    # Convert to DTOs
    items = [UserDTO.model_validate(u) for u in users]

    return PaginatedResponse.create(items=items, total=total, page=page, page_size=page_size)


@router.post("/users", response_model=UserDTO, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    current_user: Annotated[User, Depends(get_current_user_required)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """
    Create a new user. Requires superuser.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only platform admins can create users",
        )

    # Check email uniqueness
    existing = await session.execute(
        select(User).where(User.email == data.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email '{data.email}' already exists",
        )

    user = User(
        email=data.email,
        full_name=data.full_name,
        password_hash=hash_password(data.password),
        locale_scopes=data.locale_scopes,
        is_superuser=data.is_superuser,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    return user


@router.get("/users/{user_id}", response_model=UserDTO)
async def get_user(
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_user_required)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """
    Get user by ID. Requires superuser.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only platform admins can view user details",
        )

    result = await session.execute(
        select(User).where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user


@router.patch("/users/{user_id}", response_model=UserDTO)
async def update_user(
    user_id: UUID,
    data: UserUpdate,
    current_user: Annotated[User, Depends(get_current_user_required)],
    session: Annotated[AsyncSession, Depends(get_session)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> User:
    """
    Update user. Requires superuser.

    If password is changed, all user's refresh tokens are revoked.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only platform admins can update users",
        )

    result = await session.execute(
        select(User).where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Prevent removing last superuser
    if data.is_superuser is False and user.is_superuser:
        superuser_count = await session.execute(
            select(User).where(User.is_superuser == True)  # noqa: E712
        )
        if len(list(superuser_count.scalars().all())) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove last superuser",
            )

    # Update fields
    if data.email is not None:
        # Check email uniqueness
        existing = await session.execute(
            select(User).where(User.email == data.email, User.user_id != user_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with email '{data.email}' already exists",
            )
        user.email = data.email

    if data.full_name is not None:
        user.full_name = data.full_name

    if data.locale_scopes is not None:
        user.locale_scopes = data.locale_scopes

    if data.is_active is not None:
        user.is_active = data.is_active
        # If deactivating, revoke all tokens
        if not data.is_active:
            await auth_service.revoke_all_user_tokens(user_id)

    if data.is_superuser is not None:
        user.is_superuser = data.is_superuser

    if data.password is not None:
        user.password_hash = hash_password(data.password)
        # Revoke all tokens on password change (security)
        await auth_service.revoke_all_user_tokens(user_id)

    await session.commit()
    await session.refresh(user)

    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_user_required)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """
    Delete user. Requires superuser.
    Cannot delete yourself or the last superuser.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only platform admins can delete users",
        )

    if user_id == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself",
        )

    result = await session.execute(
        select(User).where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Prevent deleting last superuser
    if user.is_superuser:
        superuser_count = await session.execute(
            select(User).where(User.is_superuser == True)  # noqa: E712
        )
        if len(list(superuser_count.scalars().all())) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete last superuser",
            )

    # Delete related records first (to avoid FK constraint issues)
    from app.domain.models import CompanyMembership, RoleAssignment

    await session.execute(
        select(CompanyMembership).where(CompanyMembership.user_id == user_id)
    )
    await session.execute(
        CompanyMembership.__table__.delete().where(CompanyMembership.user_id == user_id)
    )
    await session.execute(
        RoleAssignment.__table__.delete().where(RoleAssignment.user_id == user_id)
    )

    await session.delete(user)
    await session.commit()
