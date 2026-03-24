import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from sqlalchemy import select

from app.core.config import settings
from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password
from app.db.models.organization import Organization
from app.db.models.sso import SSOProvider
from app.repositories.audit_repo import AuditRepository
from app.repositories.refresh_token_repo import RefreshTokenRepository
from app.repositories.role_binding_repo import RoleBindingRepository
from app.repositories.sso_repo import SSORepository
from app.repositories.user_repo import UserRepository
from app.schemas.auth import TokenResponse
from app.schemas.sso import (
    SSOCallbackRequest,
    SSOProviderCreate,
    SSOProviderListOut,
    SSOProviderOut,
    SSOProviderPublicListOut,
    SSOProviderPublicOut,
    SSOProviderUpdate,
    SSOStartOut,
)


class SSOService:
    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    async def _get_organization_or_raise(self, organization_id: int) -> Organization:
        result = await self.sso_repo.session.execute(
            select(Organization).where(Organization.id == organization_id)
        )
        organization = result.scalar_one_or_none()
        if not organization:
            raise AppError("NOT_FOUND", 404, f"Organization {organization_id} not found")
        return organization

    @staticmethod
    def _require_sso_enabled(organization: Organization) -> None:
        if organization.status in {"suspended", "archived"}:
            raise AppError("TENANT_SUSPENDED", 403, "Tenant access is suspended")
        if not organization.allow_sso_login:
            raise AppError("SSO_DISABLED", 403, "SSO login is disabled for this organization")

    def __init__(
        self,
        sso_repo: SSORepository,
        user_repo: UserRepository,
        role_binding_repo: RoleBindingRepository,
        refresh_token_repo: RefreshTokenRepository,
        audit_repo: AuditRepository,
    ):
        self.sso_repo = sso_repo
        self.user_repo = user_repo
        self.role_binding_repo = role_binding_repo
        self.refresh_token_repo = refresh_token_repo
        self.audit_repo = audit_repo

    @staticmethod
    def _serialize_provider(provider: SSOProvider) -> SSOProviderOut:
        return SSOProviderOut(
            id=provider.id,
            name=provider.name,
            provider_type=provider.provider_type,
            auth_url=provider.auth_url,
            issuer=provider.issuer,
            client_id=provider.client_id,
            redirect_uri=provider.redirect_uri,
            entity_id=provider.entity_id,
            is_active=provider.is_active,
            auto_provision=provider.auto_provision,
            default_role=provider.default_role,
            secret_configured=bool(provider.client_secret),
            created_at=provider.created_at,
            updated_at=provider.updated_at,
        )

    @staticmethod
    def _require_admin(ctx: RequestContext) -> int:
        if ctx.role not in ("admin", "platform_admin"):
            raise AppError("FORBIDDEN", 403, "Only admin can manage SSO providers")
        if ctx.organization_id is None:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required")
        return ctx.organization_id

    async def list_active_providers(self, organization_id: int) -> SSOProviderPublicListOut:
        providers = await self.sso_repo.list_active_providers(organization_id)
        return SSOProviderPublicListOut(
            items=[
                SSOProviderPublicOut(
                    id=provider.id,
                    name=provider.name,
                    provider_type=provider.provider_type,
                )
                for provider in providers
            ],
            total=len(providers),
        )

    async def list_providers(self, ctx: RequestContext) -> SSOProviderListOut:
        org_id = self._require_admin(ctx)
        providers = await self.sso_repo.list_providers(org_id)
        return SSOProviderListOut(
            items=[self._serialize_provider(provider) for provider in providers],
            total=len(providers),
        )

    async def create_provider(
        self, payload: SSOProviderCreate, ctx: RequestContext
    ) -> SSOProviderOut:
        org_id = self._require_admin(ctx)
        provider = await self.sso_repo.create_provider(
            organization_id=org_id,
            **payload.model_dump(mode="json"),
        )
        await self.audit_repo.log(
            entity_type="SSOProvider",
            entity_id=provider.id,
            action="sso_provider_created",
            user_id=ctx.user_id,
            organization_id=org_id,
            changes=payload.model_dump(mode="json", exclude={"client_secret"}),
            performed_by_platform_admin=ctx.is_platform_admin,
        )
        return self._serialize_provider(provider)

    async def update_provider(
        self,
        provider_id: int,
        payload: SSOProviderUpdate,
        ctx: RequestContext,
    ) -> SSOProviderOut:
        org_id = self._require_admin(ctx)
        provider = await self.sso_repo.get_provider_or_raise(provider_id)
        if provider.organization_id != org_id and not ctx.is_platform_admin:
            raise AppError("FORBIDDEN", 403, "Provider belongs to another organization")

        changes = payload.model_dump(mode="json", exclude_unset=True)
        for key, value in changes.items():
            setattr(provider, key, value)
        await self.sso_repo.session.flush()
        await self.audit_repo.log(
            entity_type="SSOProvider",
            entity_id=provider.id,
            action="sso_provider_updated",
            user_id=ctx.user_id,
            organization_id=provider.organization_id,
            changes={k: v for k, v in changes.items() if k != "client_secret"},
            performed_by_platform_admin=ctx.is_platform_admin,
        )
        return self._serialize_provider(provider)

    async def start_login(self, provider_id: int, organization_id: int) -> SSOStartOut:
        provider = await self.sso_repo.get_provider_or_raise(provider_id)
        if provider.organization_id != organization_id:
            raise AppError("FORBIDDEN", 403, "Provider does not belong to this organization")
        if not provider.is_active:
            raise AppError("SSO_PROVIDER_INACTIVE", 403, "SSO provider is inactive")
        organization = await self._get_organization_or_raise(provider.organization_id)
        self._require_sso_enabled(organization)

        state = secrets.token_urlsafe(24)
        expires_at = datetime.now(UTC) + timedelta(minutes=10)
        await self.sso_repo.create_login_state(
            sso_provider_id=provider.id,
            organization_id=organization_id,
            state=state,
            expires_at=expires_at,
        )

        query = urlencode(
            {
                "client_id": provider.client_id,
                "state": state,
                "redirect_uri": provider.redirect_uri or "",
                "response_type": "code" if provider.provider_type == "oauth2" else "saml_response",
            }
        )
        auth_url = f"{provider.auth_url}?{query}"
        return SSOStartOut(
            provider_id=provider.id,
            organization_id=organization_id,
            provider_type=provider.provider_type,
            state=state,
            auth_url=auth_url,
            expires_at=expires_at,
        )

    async def handle_callback(self, provider_id: int, payload: SSOCallbackRequest) -> TokenResponse:
        return await self.handle_callback_with_session_metadata(
            provider_id,
            payload,
            client_ip=None,
            user_agent=None,
        )

    async def handle_callback_with_session_metadata(
        self,
        provider_id: int,
        payload: SSOCallbackRequest,
        *,
        client_ip: str | None,
        user_agent: str | None,
    ) -> TokenResponse:
        provider = await self.sso_repo.get_provider_or_raise(provider_id)
        if not provider.is_active:
            raise AppError("SSO_PROVIDER_INACTIVE", 403, "SSO provider is inactive")
        organization = await self._get_organization_or_raise(provider.organization_id)
        self._require_sso_enabled(organization)

        login_state = await self.sso_repo.get_login_state(payload.state)
        if not login_state or login_state.sso_provider_id != provider_id:
            raise AppError("SSO_STATE_INVALID", 422, "SSO login state is invalid")
        if login_state.used_at is not None:
            raise AppError("SSO_STATE_USED", 409, "SSO login state has already been used")
        if self._as_utc(login_state.expires_at) < datetime.now(UTC):
            raise AppError("SSO_STATE_EXPIRED", 422, "SSO login state has expired")

        identity = await self.sso_repo.get_identity(provider_id, payload.external_subject)
        user = await self.user_repo.get_by_email(payload.email)

        if identity:
            user = await self.user_repo.get_by_id(identity.user_id)
        elif not user and not provider.auto_provision:
            raise AppError("SSO_USER_NOT_ALLOWED", 403, "SSO auto-provisioning is disabled")

        if not user:
            user = await self.user_repo.create(
                email=payload.email,
                password_hash=hash_password(secrets.token_urlsafe(32)),
                full_name=payload.full_name,
            )

        binding = await self.role_binding_repo.get_binding(
            user.id,
            "organization",
            provider.organization_id,
        )
        if not binding:
            if not provider.auto_provision:
                raise AppError("SSO_USER_NOT_ALLOWED", 403, "User has no role in this organization")
            await self.role_binding_repo.create(
                user_id=user.id,
                role=provider.default_role,
                scope_type="organization",
                scope_id=provider.organization_id,
                created_by=user.id,
            )

        if not identity:
            identity = await self.sso_repo.create_identity(
                sso_provider_id=provider.id,
                user_id=user.id,
                external_subject=payload.external_subject,
                email=payload.email,
                last_login_at=datetime.now(UTC),
            )
        else:
            identity.email = payload.email
            identity.last_login_at = datetime.now(UTC)
            await self.sso_repo.session.flush()

        if not user.is_active:
            raise AppError("FORBIDDEN", 403, "Account is deactivated")

        login_state.used_at = datetime.now(UTC)
        refresh = create_refresh_token(user.id, user.email)
        refresh_payload = decode_token(refresh)
        expires_at = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_ttl_days)
        refresh_session = await self.refresh_token_repo.create(
            user.id,
            refresh,
            expires_at,
            token_jti=refresh_payload.jti,
            ip_address=client_ip,
            user_agent=user_agent,
            last_used_at=datetime.now(UTC),
        )
        access = create_access_token(user.id, user.email, session_id=refresh_session.id)

        await self.audit_repo.log(
            entity_type="User",
            entity_id=user.id,
            action="sso_login",
            user_id=user.id,
            organization_id=provider.organization_id,
            changes={
                "provider_id": provider.id,
                "provider_type": provider.provider_type,
                "external_subject": payload.external_subject,
                "session_id": refresh_session.id,
            },
        )
        return TokenResponse(access_token=access, refresh_token=refresh)
