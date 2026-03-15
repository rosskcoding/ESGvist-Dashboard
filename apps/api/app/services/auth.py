"""
Authentication Service.

Handles password hashing, JWT tokens, and user authentication.

Security features:
- httpOnly cookies for token storage (XSS protection)
- Server-side refresh token storage (revocation support)
- Token rotation (one-time use refresh tokens)
- Token family tracking (theft detection)
"""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.domain.models import (
    AuditEvent,
    CompanyMembership,
    RefreshToken,
    RoleAssignment,
    User,
)
from app.domain.models.enums import AssignableRole, ScopeType
from app.domain.schemas import (
    LoginRequest,
    TokenResponse,
    UserCompanyDTO,
    UserCreate,
    UserDTO,
)

# Password hashing (per docs/product/spec/12_IAM.md):
# Prefer argon2; keep it as the primary scheme.
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def generate_jti() -> str:
    """Generate unique JWT ID for token identification."""
    return secrets.token_urlsafe(32)


def create_access_token(
    data: dict[str, Any],
    jti: str | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({
        "exp": expire,
        "type": "access",
        "jti": jti or generate_jti(),
    })
    return jwt.encode(
        to_encode,
        settings.secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token_jwt(
    data: dict[str, Any],
    jti: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT refresh token with specific jti."""
    to_encode = data.copy()
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(days=settings.refresh_token_expire_days)
    )
    to_encode.update({
        "exp": expire,
        "type": "refresh",
        "jti": jti,
    })
    return jwt.encode(
        to_encode,
        settings.secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError:
        return None


class AuthService:
    """Authentication service with secure token management."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_by_email(self, email: str) -> User | None:
        """Get user by email with memberships and role_assignments."""
        result = await self.session.execute(
            select(User)
            .options(
                selectinload(User.memberships).selectinload(CompanyMembership.company),
                selectinload(User.role_assignments),
            )
            .where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        """Get user by ID with memberships and role_assignments."""
        result = await self.session.execute(
            select(User)
            .options(
                selectinload(User.memberships).selectinload(CompanyMembership.company),
                selectinload(User.role_assignments),
            )
            .where(User.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def _create_user_dto(self, user: User) -> UserDTO:
        """Create UserDTO with company memberships and roles."""
        user_dto = UserDTO.model_validate(user)
        companies: list[UserCompanyDTO] = []

        for m in user.memberships:
            # Fetch all role assignments for this user in this company
            roles_result = await self.session.execute(
                select(RoleAssignment.role)
                .where(
                    RoleAssignment.user_id == user.user_id,
                    RoleAssignment.company_id == m.company_id,
                )
            )
            role_values = [r[0].value for r in roles_result.fetchall()]

            # Check if user has corporate_lead role
            is_corporate_lead = AssignableRole.CORPORATE_LEAD.value in role_values

            companies.append(
                UserCompanyDTO(
                    company_id=m.company_id,
                    company_name=m.company.name if m.company else "",
                    is_corporate_lead=is_corporate_lead,
                    is_active=m.is_active,
                    roles=role_values,
                )
            )
        user_dto.companies = companies
        return user_dto

    async def _create_refresh_token_record(
        self,
        user_id: UUID,
        family_id: UUID | None = None,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[RefreshToken, str]:
        """
        Create a new refresh token record in DB and return JWT.

        Args:
            user_id: User ID
            family_id: Token family ID (for rotation). None = new family.
            user_agent: Client user agent
            ip_address: Client IP address

        Returns:
            Tuple of (RefreshToken record, JWT string)
        """
        jti = generate_jti()
        expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)

        token_record = RefreshToken(
            jti=jti,
            user_id=user_id,
            family_id=family_id or uuid4(),
            expires_at_utc=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        self.session.add(token_record)
        await self.session.flush()

        # Create JWT with jti
        jwt_token = create_refresh_token_jwt(
            {"sub": str(user_id)},
            jti=jti,
        )

        return token_record, jwt_token

    async def authenticate(
        self,
        request: LoginRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[TokenResponse, str] | None:
        """
        Authenticate user and return tokens.

        Returns:
            Tuple of (TokenResponse for body, refresh_token_jwt for cookie)
            or None if authentication fails.
        """
        user = await self.get_user_by_email(request.email)

        if not user:
            return None

        if not user.is_active:
            return None

        if not verify_password(request.password, user.password_hash):
            # Log failed attempt
            await self._log_audit(
                actor_id=str(user.user_id),
                action="login_failed",
                entity_type="user",
                entity_id=str(user.user_id),
                metadata={"reason": "invalid_password"},
                ip_address=ip_address,
            )
            return None

        # Create access token
        access_jti = generate_jti()
        token_data = {"sub": str(user.user_id), "email": user.email}
        access_token = create_access_token(token_data, jti=access_jti)

        # Create refresh token (stored in DB)
        _, refresh_jwt = await self._create_refresh_token_record(
            user_id=user.user_id,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        # Log successful login
        await self._log_audit(
            actor_id=str(user.user_id),
            action="login",
            entity_type="user",
            entity_id=str(user.user_id),
            ip_address=ip_address,
        )

        user_dto = await self._create_user_dto(user)

        token_response = TokenResponse(
            access_token=access_token,
            refresh_token="",  # Will be set in cookie, not body
            expires_in=settings.access_token_expire_minutes * 60,
            user=user_dto,
        )

        return token_response, refresh_jwt

    async def refresh_tokens(
        self,
        refresh_token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[TokenResponse, str] | None:
        """
        Refresh access token using refresh token.

        Implements token rotation:
        - Old refresh token is marked as used
        - New refresh token is created in same family
        - If old token is already used → theft detected, revoke family

        Returns:
            Tuple of (TokenResponse, new_refresh_jwt) or None if invalid.
        """
        payload = decode_token(refresh_token)
        if not payload:
            return None

        if payload.get("type") != "refresh":
            return None

        jti = payload.get("jti")
        if not jti:
            return None

        user_id_str = payload.get("sub")
        if not user_id_str:
            return None

        # Find token record
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.jti == jti)
        )
        token_record = result.scalar_one_or_none()

        if not token_record:
            # Token not found - could be old token before migration
            # Fall back to stateless refresh for backward compatibility
            return await self._fallback_refresh(refresh_token)

        # Check if token was already used (potential theft!)
        if token_record.is_used:
            # Revoke entire token family - this is a security breach
            await self._revoke_token_family(token_record.family_id)
            await self._log_audit(
                actor_id=user_id_str,
                action="refresh_token_reuse_detected",
                entity_type="refresh_token",
                entity_id=str(token_record.token_id),
                metadata={"family_id": str(token_record.family_id)},
                ip_address=ip_address,
            )
            return None

        # Check if token is valid
        if not token_record.is_valid:
            return None

        # Mark old token as used (rotation)
        token_record.mark_used()

        # Get user
        user = await self.get_user_by_id(UUID(user_id_str))
        if not user or not user.is_active:
            return None

        # Create new tokens
        access_jti = generate_jti()
        token_data = {"sub": str(user.user_id), "email": user.email}
        new_access_token = create_access_token(token_data, jti=access_jti)

        # Create new refresh token in same family
        _, new_refresh_jwt = await self._create_refresh_token_record(
            user_id=user.user_id,
            family_id=token_record.family_id,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        user_dto = await self._create_user_dto(user)

        token_response = TokenResponse(
            access_token=new_access_token,
            refresh_token="",  # Will be set in cookie
            expires_in=settings.access_token_expire_minutes * 60,
            user=user_dto,
        )

        return token_response, new_refresh_jwt

    async def _fallback_refresh(
        self,
        refresh_token: str,
    ) -> tuple[TokenResponse, str] | None:
        """
        Fallback refresh for tokens created before migration.

        This maintains backward compatibility but creates new tracked tokens.
        """
        payload = decode_token(refresh_token)
        if not payload:
            return None

        if payload.get("type") != "refresh":
            return None

        user_id = payload.get("sub")
        if not user_id:
            return None

        user = await self.get_user_by_id(UUID(user_id))
        if not user or not user.is_active:
            return None

        # Create new tracked tokens
        access_jti = generate_jti()
        token_data = {"sub": str(user.user_id), "email": user.email}
        new_access_token = create_access_token(token_data, jti=access_jti)

        _, new_refresh_jwt = await self._create_refresh_token_record(
            user_id=user.user_id,
        )

        user_dto = await self._create_user_dto(user)

        token_response = TokenResponse(
            access_token=new_access_token,
            refresh_token="",
            expires_in=settings.access_token_expire_minutes * 60,
            user=user_dto,
        )

        return token_response, new_refresh_jwt

    async def _revoke_token_family(self, family_id: UUID) -> int:
        """
        Revoke all tokens in a family (theft detection response).

        Returns count of revoked tokens.
        """
        result = await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id)
            .values(is_revoked=True)
        )
        return result.rowcount

    async def revoke_refresh_token(self, jti: str) -> bool:
        """
        Revoke a specific refresh token by jti.

        Returns True if token was found and revoked.
        """
        result = await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.jti == jti)
            .values(is_revoked=True)
        )
        return result.rowcount > 0

    async def revoke_all_user_tokens(self, user_id: UUID) -> int:
        """
        Revoke all refresh tokens for a user (logout from all devices).

        Returns count of revoked tokens.
        """
        result = await self.session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked == False,  # noqa: E712
            )
            .values(is_revoked=True)
        )
        return result.rowcount

    async def cleanup_expired_tokens(self) -> int:
        """
        Delete expired refresh tokens (housekeeping).

        Returns count of deleted tokens.
        """
        result = await self.session.execute(
            delete(RefreshToken).where(
                RefreshToken.expires_at_utc < datetime.now(UTC)
            )
        )
        return result.rowcount

    async def create_user(self, data: UserCreate) -> User:
        """Create a new user."""
        user = User(
            email=data.email,
            password_hash=hash_password(data.password),
            full_name=data.full_name,
            is_superuser=data.is_superuser,
            locale_scopes=data.locale_scopes,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def _log_audit(
        self,
        actor_id: str,
        action: str,
        entity_type: str,
        entity_id: str,
        metadata: dict | None = None,
        ip_address: str | None = None,
    ) -> None:
        """Log an audit event."""
        event = AuditEvent.create(
            actor_type="user",
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=metadata,
            ip_address=ip_address,
        )
        self.session.add(event)


async def get_current_user(
    token: str,
    session: AsyncSession,
) -> User | None:
    """
    Get current user from JWT token.

    Used by FastAPI dependencies.
    Loads role_assignments AND memberships for RBAC + tenant isolation checks.
    """
    payload = decode_token(token)
    if not payload:
        return None

    if payload.get("type") != "access":
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    # Load user with role_assignments + memberships for RBAC + tenant checks
    result = await session.execute(
        select(User)
        .options(
            selectinload(User.role_assignments),
            selectinload(User.memberships).selectinload(CompanyMembership.company),
        )
        .where(User.user_id == UUID(user_id))
    )
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        return None

    return user
