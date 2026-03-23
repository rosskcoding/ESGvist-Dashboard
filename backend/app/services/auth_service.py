from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.repositories.audit_repo import AuditRepository
from app.repositories.refresh_token_repo import RefreshTokenRepository
from app.repositories.role_binding_repo import RoleBindingRepository
from app.repositories.user_repo import UserRepository
from app.schemas.auth import TokenResponse, UserResponse, RoleBindingOut


class AuthService:
    def __init__(
        self,
        user_repo: UserRepository,
        role_binding_repo: RoleBindingRepository,
        refresh_token_repo: RefreshTokenRepository,
        audit_repo: AuditRepository,
    ):
        self.user_repo = user_repo
        self.role_binding_repo = role_binding_repo
        self.refresh_token_repo = refresh_token_repo
        self.audit_repo = audit_repo

    async def register(
        self, email: str, password: str, full_name: str, request_id: str | None = None
    ) -> UserResponse:
        existing = await self.user_repo.get_by_email(email)
        if existing:
            raise AppError(code="CONFLICT", status_code=409, message="Email already registered")

        user = await self.user_repo.create(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
        )

        # First user becomes platform_admin
        user_count = await self.user_repo.count()
        if user_count == 1:
            await self.role_binding_repo.create(
                user_id=user.id,
                role="platform_admin",
                scope_type="platform",
                scope_id=None,
                created_by=user.id,
            )

        await self.audit_repo.log(
            entity_type="User",
            entity_id=user.id,
            action="register",
            user_id=user.id,
            request_id=request_id,
        )

        bindings = await self.role_binding_repo.get_bindings(user.id)
        return UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            roles=[RoleBindingOut.model_validate(b) for b in bindings],
        )

    async def login(
        self, email: str, password: str, request_id: str | None = None
    ) -> TokenResponse:
        user = await self.user_repo.get_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            raise AppError(
                code="UNAUTHORIZED", status_code=401, message="Invalid email or password"
            )

        if not user.is_active:
            raise AppError(code="FORBIDDEN", status_code=403, message="Account is deactivated")

        access = create_access_token(user.id, user.email)
        refresh = create_refresh_token(user.id, user.email)

        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_ttl_days)
        await self.refresh_token_repo.create(user.id, refresh, expires_at)

        await self.audit_repo.log(
            entity_type="User",
            entity_id=user.id,
            action="login",
            user_id=user.id,
            request_id=request_id,
        )

        return TokenResponse(access_token=access, refresh_token=refresh)

    async def refresh(self, refresh_token: str) -> TokenResponse:
        stored = await self.refresh_token_repo.get_by_token(refresh_token)
        if not stored:
            raise AppError(
                code="UNAUTHORIZED", status_code=401, message="Invalid or expired refresh token"
            )

        payload = decode_token(refresh_token)
        if payload.token_type != "refresh":
            raise AppError(code="UNAUTHORIZED", status_code=401, message="Invalid token type")

        user = await self.user_repo.get_by_id(stored.user_id)
        if not user or not user.is_active:
            raise AppError(code="UNAUTHORIZED", status_code=401, message="User not found")

        # Rotate refresh token
        await self.refresh_token_repo.delete_by_token(refresh_token)

        access = create_access_token(user.id, user.email)
        new_refresh = create_refresh_token(user.id, user.email)

        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_ttl_days)
        await self.refresh_token_repo.create(user.id, new_refresh, expires_at)

        return TokenResponse(access_token=access, refresh_token=new_refresh)

    async def logout(self, user_id: int, request_id: str | None = None) -> None:
        await self.refresh_token_repo.delete_all_for_user(user_id)
        await self.audit_repo.log(
            entity_type="User",
            entity_id=user_id,
            action="logout",
            user_id=user_id,
            request_id=request_id,
        )

    async def get_me(self, user_id: int) -> UserResponse:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise AppError(code="NOT_FOUND", status_code=404, message="User not found")

        bindings = await self.role_binding_repo.get_bindings(user.id)
        return UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            roles=[RoleBindingOut.model_validate(b) for b in bindings],
        )
