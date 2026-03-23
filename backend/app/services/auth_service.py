from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.core.config import settings
from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.models.organization import Organization
from app.db.models.sso import SSOProvider
from app.repositories.audit_repo import AuditRepository
from app.repositories.refresh_token_repo import RefreshTokenRepository
from app.repositories.role_binding_repo import RoleBindingRepository
from app.repositories.user_repo import UserRepository
from app.schemas.auth import (
    OrganizationAuthSettingsOut,
    OrganizationAuthSettingsUpdate,
    RoleBindingOut,
    TokenResponse,
    UserResponse,
)


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

    async def _get_organization_or_raise(self, organization_id: int) -> Organization:
        result = await self.user_repo.session.execute(
            select(Organization).where(Organization.id == organization_id)
        )
        organization = result.scalar_one_or_none()
        if not organization:
            raise AppError("NOT_FOUND", 404, f"Organization {organization_id} not found")
        return organization

    async def _count_active_sso_providers(self, organization_id: int) -> int:
        result = await self.user_repo.session.execute(
            select(func.count())
            .select_from(SSOProvider)
            .where(
                SSOProvider.organization_id == organization_id,
                SSOProvider.is_active.is_(True),
            )
        )
        return int(result.scalar_one())

    async def _serialize_org_auth_settings(self, organization: Organization) -> OrganizationAuthSettingsOut:
        active_sso_provider_count = await self._count_active_sso_providers(organization.id)
        return OrganizationAuthSettingsOut(
            organization_id=organization.id,
            allow_password_login=organization.allow_password_login,
            allow_sso_login=organization.allow_sso_login,
            enforce_sso=organization.enforce_sso,
            active_sso_provider_count=active_sso_provider_count,
            sso_available=organization.allow_sso_login and active_sso_provider_count > 0,
        )

    async def get_login_options(self, organization_id: int) -> OrganizationAuthSettingsOut:
        organization = await self._get_organization_or_raise(organization_id)
        return await self._serialize_org_auth_settings(organization)

    async def get_organization_auth_settings(self, ctx: RequestContext) -> OrganizationAuthSettingsOut:
        if not ctx.organization_id:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required")
        organization = await self._get_organization_or_raise(ctx.organization_id)
        return await self._serialize_org_auth_settings(organization)

    async def update_organization_auth_settings(
        self,
        payload: OrganizationAuthSettingsUpdate,
        ctx: RequestContext,
    ) -> OrganizationAuthSettingsOut:
        if not ctx.organization_id:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required")

        organization = await self._get_organization_or_raise(ctx.organization_id)
        active_sso_provider_count = await self._count_active_sso_providers(organization.id)

        allow_password_login = (
            payload.allow_password_login
            if payload.allow_password_login is not None
            else organization.allow_password_login
        )
        allow_sso_login = (
            payload.allow_sso_login if payload.allow_sso_login is not None else organization.allow_sso_login
        )
        enforce_sso = payload.enforce_sso if payload.enforce_sso is not None else organization.enforce_sso

        if not allow_password_login and not allow_sso_login:
            raise AppError("INVALID_AUTH_SETTINGS", 422, "Organization must allow at least one login method")
        if enforce_sso and allow_password_login:
            raise AppError("INVALID_AUTH_SETTINGS", 422, "Password login must be disabled when SSO is enforced")
        if enforce_sso and not allow_sso_login:
            raise AppError("INVALID_AUTH_SETTINGS", 422, "SSO must stay enabled when SSO is enforced")
        if (enforce_sso or not allow_password_login) and active_sso_provider_count == 0:
            raise AppError("SSO_PROVIDER_REQUIRED", 422, "At least one active SSO provider is required")

        changes: dict[str, bool] = {}
        for field, value in (
            ("allow_password_login", allow_password_login),
            ("allow_sso_login", allow_sso_login),
            ("enforce_sso", enforce_sso),
        ):
            if getattr(organization, field) != value:
                setattr(organization, field, value)
                changes[field] = value

        await self.user_repo.session.flush()
        if changes:
            await self.audit_repo.log(
                entity_type="Organization",
                entity_id=organization.id,
                action="organization_auth_settings_updated",
                user_id=ctx.user_id,
                organization_id=organization.id,
                changes=changes,
                performed_by_platform_admin=ctx.is_platform_admin,
            )

        return await self._serialize_org_auth_settings(organization)

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

        bindings = await self.role_binding_repo.get_bindings(user.id)
        if not any(binding.scope_type == "platform" and binding.role == "platform_admin" for binding in bindings):
            org_scope_ids = [
                binding.scope_id
                for binding in bindings
                if binding.scope_type == "organization" and binding.scope_id is not None
            ]
            if org_scope_ids:
                result = await self.user_repo.session.execute(
                    select(Organization).where(Organization.id.in_(org_scope_ids))
                )
                organizations = result.scalars().all()
                statuses = {organization.status for organization in organizations}
                if organizations and statuses.issubset({"suspended", "archived"}):
                    raise AppError(
                        code="TENANT_SUSPENDED",
                        status_code=403,
                        message="All tenant access for this account is suspended",
                    )
                active_organizations = [
                    organization for organization in organizations if organization.status == "active"
                ]
                if active_organizations and any(
                    organization.enforce_sso or not organization.allow_password_login
                    for organization in active_organizations
                ):
                    raise AppError(
                        code="SSO_REQUIRED",
                        status_code=403,
                        message="Password login is disabled for this organization. Use SSO instead",
                    )

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
