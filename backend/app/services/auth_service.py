from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.core.config import settings
from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.core.security import (
    build_totp_uri,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_backup_codes,
    generate_totp_secret,
    hash_backup_code,
    hash_password,
    verify_backup_code,
    verify_password,
    verify_totp,
)
from app.db.models.boundary import BoundaryDefinition
from app.db.models.organization import Organization
from app.db.models.sso import SSOProvider
from app.repositories.audit_repo import AuditRepository
from app.repositories.refresh_token_repo import RefreshTokenRepository
from app.repositories.role_binding_repo import RoleBindingRepository
from app.repositories.user_repo import UserRepository
from app.schemas.auth import (
    AuthSessionListOut,
    AuthSessionOut,
    AuthSessionRevokeOut,
    LogoutAllOut,
    OrganizationAuthSettingsOut,
    OrganizationAuthSettingsUpdate,
    OrganizationSettingsOut,
    RoleBindingOut,
    TokenResponse,
    TwoFactorSetupOut,
    TwoFactorStatusOut,
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

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

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

    async def _get_default_boundary_id(self, organization_id: int) -> int | None:
        result = await self.user_repo.session.execute(
            select(BoundaryDefinition.id).where(
                BoundaryDefinition.organization_id == organization_id,
                BoundaryDefinition.is_default.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def _resolve_user_organization_name(self, bindings: list[RoleBindingOut]) -> str | None:
        org_binding = next(
            (
                binding
                for binding in bindings
                if binding.scope_type == "organization" and binding.scope_id is not None
            ),
            None,
        )
        if not org_binding or org_binding.scope_id is None:
            return None
        organization = await self._get_organization_or_raise(org_binding.scope_id)
        return organization.name

    async def _serialize_user_response(self, user) -> UserResponse:
        bindings = [
            RoleBindingOut.model_validate(binding)
            for binding in await self.role_binding_repo.get_bindings(user.id)
        ]
        return UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            organization_name=await self._resolve_user_organization_name(bindings),
            roles=bindings,
        )

    async def _serialize_organization_settings(
        self, organization: Organization
    ) -> OrganizationSettingsOut:
        return OrganizationSettingsOut(
            id=organization.id,
            name=organization.name,
            legal_name=organization.legal_name,
            registration_number=organization.registration_number,
            country=organization.country,
            jurisdiction=organization.jurisdiction,
            industry=organization.industry,
            currency=organization.default_currency,
            reporting_year=organization.default_reporting_year,
            default_standards=organization.default_standards or [],
            consolidation_approach=organization.default_consolidation_approach,
            ghg_scope_approach=organization.default_ghg_scope_approach,
            logo_url=None,
            default_boundary_id=await self._get_default_boundary_id(organization.id),
        )

    async def _create_refresh_session(
        self,
        user,
        *,
        refresh_token: str,
        client_ip: str | None = None,
        user_agent: str | None = None,
        rotated_from_id: int | None = None,
    ):
        payload = decode_token(refresh_token)
        if payload.token_type != "refresh" or not payload.jti:
            raise AppError("UNAUTHORIZED", 401, "Invalid token type")

        expires_at = self._now() + timedelta(days=settings.jwt_refresh_ttl_days)
        return await self.refresh_token_repo.create(
            user.id,
            refresh_token,
            expires_at,
            token_jti=payload.jti,
            ip_address=client_ip,
            user_agent=user_agent,
            rotated_from_id=rotated_from_id,
            last_used_at=self._now(),
        )

    @staticmethod
    def _current_refresh_jti(refresh_token: str | None) -> str | None:
        if not refresh_token:
            return None
        try:
            payload = decode_token(refresh_token)
        except AppError:
            return None
        return payload.jti if payload.token_type == "refresh" else None

    @staticmethod
    def _serialize_auth_session(
        refresh_session, *, current_session_jti: str | None
    ) -> AuthSessionOut:
        return AuthSessionOut(
            id=refresh_session.id,
            created_at=refresh_session.created_at,
            expires_at=refresh_session.expires_at,
            last_used_at=refresh_session.last_used_at,
            ip_address=refresh_session.ip_address,
            user_agent=refresh_session.user_agent,
            is_current=bool(
                current_session_jti
                and refresh_session.token_jti
                and refresh_session.token_jti == current_session_jti
            ),
        )

    async def _serialize_org_auth_settings(
        self, organization: Organization
    ) -> OrganizationAuthSettingsOut:
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

    async def get_organization_auth_settings(
        self, ctx: RequestContext
    ) -> OrganizationAuthSettingsOut:
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
            payload.allow_sso_login
            if payload.allow_sso_login is not None
            else organization.allow_sso_login
        )
        enforce_sso = (
            payload.enforce_sso if payload.enforce_sso is not None else organization.enforce_sso
        )

        if not allow_password_login and not allow_sso_login:
            raise AppError(
                "INVALID_AUTH_SETTINGS", 422, "Organization must allow at least one login method"
            )
        if enforce_sso and allow_password_login:
            raise AppError(
                "INVALID_AUTH_SETTINGS", 422, "Password login must be disabled when SSO is enforced"
            )
        if enforce_sso and not allow_sso_login:
            raise AppError(
                "INVALID_AUTH_SETTINGS", 422, "SSO must stay enabled when SSO is enforced"
            )
        if (enforce_sso or not allow_password_login) and active_sso_provider_count == 0:
            raise AppError(
                "SSO_PROVIDER_REQUIRED", 422, "At least one active SSO provider is required"
            )

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

        return await self._serialize_user_response(user)

    async def get_two_factor_status(self, user_id: int) -> TwoFactorStatusOut:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise AppError("NOT_FOUND", 404, "User not found")
        return TwoFactorStatusOut(
            enabled=user.totp_enabled,
            pending_setup=bool(user.totp_pending_secret),
            confirmed_at=user.totp_confirmed_at.isoformat() if user.totp_confirmed_at else None,
            backup_codes_remaining=len(user.totp_backup_codes or []),
        )

    async def setup_two_factor(self, user_id: int) -> TwoFactorSetupOut:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise AppError("NOT_FOUND", 404, "User not found")
        if user.totp_enabled:
            raise AppError(
                "TWO_FACTOR_ALREADY_ENABLED", 409, "Two-factor authentication is already enabled"
            )

        secret = generate_totp_secret()
        backup_codes = generate_backup_codes()
        user.totp_pending_secret = secret
        user.totp_backup_codes = [hash_backup_code(code) for code in backup_codes]
        await self.user_repo.session.flush()
        return TwoFactorSetupOut(
            secret=secret,
            otpauth_uri=build_totp_uri(secret, email=user.email),
            backup_codes=backup_codes,
        )

    async def enable_two_factor(self, user_id: int, code: str) -> TwoFactorStatusOut:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise AppError("NOT_FOUND", 404, "User not found")
        if user.totp_enabled:
            raise AppError(
                "TWO_FACTOR_ALREADY_ENABLED", 409, "Two-factor authentication is already enabled"
            )
        if not user.totp_pending_secret:
            raise AppError("TWO_FACTOR_NOT_SETUP", 409, "Two-factor setup has not been started")
        if not verify_totp(user.totp_pending_secret, code):
            raise AppError("TWO_FACTOR_INVALID_CODE", 401, "Invalid two-factor verification code")

        user.totp_secret = user.totp_pending_secret
        user.totp_pending_secret = None
        user.totp_enabled = True
        user.totp_confirmed_at = datetime.now(UTC)
        await self.user_repo.session.flush()
        await self.audit_repo.log(
            entity_type="User",
            entity_id=user.id,
            action="two_factor_enabled",
            user_id=user.id,
        )
        return await self.get_two_factor_status(user.id)

    async def disable_two_factor(
        self,
        user_id: int,
        *,
        code: str | None = None,
        backup_code: str | None = None,
    ) -> TwoFactorStatusOut:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise AppError("NOT_FOUND", 404, "User not found")
        if not user.totp_enabled or not user.totp_secret:
            raise AppError(
                "TWO_FACTOR_NOT_ENABLED", 409, "Two-factor authentication is not enabled"
            )

        verified = False
        if code and verify_totp(user.totp_secret, code):
            verified = True
        elif backup_code:
            verified, remaining = verify_backup_code(backup_code, user.totp_backup_codes)
            if verified:
                user.totp_backup_codes = remaining
        if not verified:
            raise AppError("TWO_FACTOR_INVALID_CODE", 401, "Invalid two-factor verification code")

        user.totp_enabled = False
        user.totp_secret = None
        user.totp_pending_secret = None
        user.totp_backup_codes = None
        user.totp_confirmed_at = None
        await self.user_repo.session.flush()
        await self.audit_repo.log(
            entity_type="User",
            entity_id=user.id,
            action="two_factor_disabled",
            user_id=user.id,
        )
        return await self.get_two_factor_status(user.id)

    async def _verify_login_two_factor(
        self,
        user,
        *,
        totp_code: str | None = None,
        backup_code: str | None = None,
    ) -> None:
        if not user.totp_enabled:
            return
        if user.totp_secret and totp_code and verify_totp(user.totp_secret, totp_code):
            return
        if backup_code:
            matched, remaining = verify_backup_code(backup_code, user.totp_backup_codes)
            if matched:
                user.totp_backup_codes = remaining
                await self.user_repo.session.flush()
                return
        raise AppError(
            code="TWO_FACTOR_REQUIRED",
            status_code=401,
            message="Two-factor verification is required for this account",
        )

    async def login(
        self,
        email: str,
        password: str,
        request_id: str | None = None,
        totp_code: str | None = None,
        backup_code: str | None = None,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> TokenResponse:
        user = await self.user_repo.get_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            raise AppError(
                code="UNAUTHORIZED", status_code=401, message="Invalid email or password"
            )

        if not user.is_active:
            raise AppError(code="FORBIDDEN", status_code=403, message="Account is deactivated")

        await self._verify_login_two_factor(
            user,
            totp_code=totp_code,
            backup_code=backup_code,
        )

        bindings = await self.role_binding_repo.get_bindings(user.id)
        if not any(
            binding.scope_type == "platform" and binding.role == "platform_admin"
            for binding in bindings
        ):
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
                    organization
                    for organization in organizations
                    if organization.status == "active"
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

        refresh = create_refresh_token(user.id, user.email)

        refresh_session = await self._create_refresh_session(
            user,
            refresh_token=refresh,
            client_ip=client_ip,
            user_agent=user_agent,
        )
        access = create_access_token(user.id, user.email, session_id=refresh_session.id)

        await self.audit_repo.log(
            entity_type="User",
            entity_id=user.id,
            action="login",
            user_id=user.id,
            request_id=request_id,
            changes={"session_id": refresh_session.id},
        )

        return TokenResponse(access_token=access, refresh_token=refresh)

    async def refresh(
        self,
        refresh_token: str,
        *,
        request_id: str | None = None,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> TokenResponse:
        payload = decode_token(refresh_token)
        if payload.token_type != "refresh":
            raise AppError(code="UNAUTHORIZED", status_code=401, message="Invalid token type")

        stored = await self.refresh_token_repo.get_active_by_token(refresh_token)
        if not stored:
            previous = await self.refresh_token_repo.get_any_by_token(refresh_token)
            if previous:
                await self.audit_repo.log(
                    entity_type="RefreshSession",
                    entity_id=previous.id,
                    action="refresh_session_rejected",
                    user_id=previous.user_id,
                    request_id=request_id,
                    changes={
                        "reason": "revoked_or_expired",
                        "token_jti": payload.jti,
                    },
                )
            raise AppError(
                code="UNAUTHORIZED", status_code=401, message="Invalid or expired refresh token"
            )

        user = await self.user_repo.get_by_id(stored.user_id)
        if not user or not user.is_active:
            raise AppError(code="UNAUTHORIZED", status_code=401, message="User not found")

        # Rotate refresh token
        await self.refresh_token_repo.revoke(
            stored,
            reason="rotated",
            used_at=self._now(),
        )

        new_refresh = create_refresh_token(user.id, user.email)
        new_refresh_session = await self._create_refresh_session(
            user,
            refresh_token=new_refresh,
            client_ip=client_ip,
            user_agent=user_agent,
            rotated_from_id=stored.id,
        )
        access = create_access_token(
            user.id,
            user.email,
            session_id=new_refresh_session.id,
        )

        await self.audit_repo.log(
            entity_type="RefreshSession",
            entity_id=new_refresh_session.id,
            action="refresh_session_rotated",
            user_id=user.id,
            request_id=request_id,
            changes={"rotated_from_id": stored.id},
        )

        return TokenResponse(access_token=access, refresh_token=new_refresh)

    async def logout(
        self,
        user_id: int,
        *,
        current_refresh_token: str | None = None,
        request_id: str | None = None,
    ) -> AuthSessionRevokeOut:
        refresh_session = None
        if current_refresh_token:
            refresh_session = await self.refresh_token_repo.revoke_by_token(
                current_refresh_token,
                reason="logout",
            )
        if refresh_session:
            revoked_sessions = 1
            session_id = refresh_session.id
        else:
            revoked_sessions = await self.refresh_token_repo.revoke_all_for_user(
                user_id,
                reason="logout_all_fallback",
            )
            session_id = None
        await self.audit_repo.log(
            entity_type="User",
            entity_id=user_id,
            action="logout",
            user_id=user_id,
            request_id=request_id,
            changes={
                "session_id": session_id,
                "revoked_sessions": revoked_sessions,
            },
        )
        return AuthSessionRevokeOut(
            session_id=session_id or 0,
            revoked=bool(revoked_sessions),
            is_current=bool(session_id),
        )

    async def logout_all(
        self,
        user_id: int,
        *,
        request_id: str | None = None,
    ) -> LogoutAllOut:
        revoked_sessions = await self.refresh_token_repo.revoke_all_for_user(
            user_id,
            reason="logout_all",
        )
        await self.audit_repo.log(
            entity_type="User",
            entity_id=user_id,
            action="logout_all",
            user_id=user_id,
            request_id=request_id,
            changes={"revoked_sessions": revoked_sessions},
        )
        return LogoutAllOut(revoked_sessions=revoked_sessions)

    async def list_sessions(
        self,
        user_id: int,
        *,
        current_refresh_token: str | None = None,
    ) -> AuthSessionListOut:
        current_session_jti = self._current_refresh_jti(current_refresh_token)
        sessions = await self.refresh_token_repo.list_active_for_user(user_id)
        items = [
            self._serialize_auth_session(
                refresh_session,
                current_session_jti=current_session_jti,
            )
            for refresh_session in sessions
        ]
        return AuthSessionListOut(items=items, total=len(items))

    async def revoke_session(
        self,
        user_id: int,
        session_id: int,
        *,
        current_refresh_token: str | None = None,
        request_id: str | None = None,
    ) -> AuthSessionRevokeOut:
        refresh_session = await self.refresh_token_repo.get_by_id_for_user(session_id, user_id)
        if not refresh_session:
            raise AppError("NOT_FOUND", 404, f"Session {session_id} not found")

        revoked = await self.refresh_token_repo.revoke(
            refresh_session,
            reason="user_revoked",
            used_at=self._now(),
        )
        is_current = bool(
            refresh_session.token_jti
            and refresh_session.token_jti == self._current_refresh_jti(current_refresh_token)
        )
        await self.audit_repo.log(
            entity_type="RefreshSession",
            entity_id=refresh_session.id,
            action="refresh_session_revoked",
            user_id=user_id,
            request_id=request_id,
            changes={"is_current": is_current},
        )
        return AuthSessionRevokeOut(
            session_id=refresh_session.id,
            revoked=revoked,
            is_current=is_current,
        )

    async def get_me(self, user_id: int) -> UserResponse:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise AppError(code="NOT_FOUND", status_code=404, message="User not found")
        return await self._serialize_user_response(user)

    async def update_me(
        self, user_id: int, updates: dict, request_id: str | None = None
    ) -> UserResponse:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise AppError(code="NOT_FOUND", status_code=404, message="User not found")

        changes = {}
        full_name = updates.get("full_name")
        if full_name and full_name != user.full_name:
            user.full_name = full_name
            changes["full_name"] = full_name

        await self.user_repo.session.flush()
        if changes:
            await self.audit_repo.log(
                entity_type="User",
                entity_id=user.id,
                action="profile_updated",
                user_id=user.id,
                request_id=request_id,
                changes=changes,
            )

        return await self._serialize_user_response(user)

    async def change_password(
        self,
        user_id: int,
        *,
        current_password: str,
        new_password: str,
        current_refresh_token: str | None = None,
        request_id: str | None = None,
    ) -> dict:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise AppError(code="NOT_FOUND", status_code=404, message="User not found")
        if not verify_password(current_password, user.password_hash):
            raise AppError("INVALID_CREDENTIALS", 401, "Current password is incorrect")
        if current_password == new_password:
            raise AppError(
                "PASSWORD_UNCHANGED",
                422,
                "New password must be different from the current password",
            )

        user.password_hash = hash_password(new_password)
        await self.user_repo.session.flush()
        current_session = (
            await self.refresh_token_repo.get_active_by_token(current_refresh_token)
            if current_refresh_token
            else None
        )
        revoked_sessions = await self.refresh_token_repo.revoke_all_for_user(
            user.id,
            reason="password_changed",
            except_session_id=current_session.id if current_session else None,
        )
        await self.audit_repo.log(
            entity_type="User",
            entity_id=user.id,
            action="password_changed",
            user_id=user.id,
            request_id=request_id,
            changes={"revoked_sessions": revoked_sessions},
        )
        return {
            "changed": True,
            "revoked_sessions": revoked_sessions,
            "current_session_preserved": current_session is not None,
        }

    async def get_my_organization_settings(self, ctx: RequestContext) -> OrganizationSettingsOut:
        if not ctx.organization_id:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required")
        organization = await self._get_organization_or_raise(ctx.organization_id)
        return await self._serialize_organization_settings(organization)

    async def update_my_organization_settings(
        self,
        ctx: RequestContext,
        updates: dict,
    ) -> OrganizationSettingsOut:
        if not ctx.organization_id:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required")

        organization = await self._get_organization_or_raise(ctx.organization_id)
        changes = {}
        field_mapping = {
            "name": "name",
            "legal_name": "legal_name",
            "registration_number": "registration_number",
            "country": "country",
            "jurisdiction": "jurisdiction",
            "industry": "industry",
            "currency": "default_currency",
            "reporting_year": "default_reporting_year",
            "default_standards": "default_standards",
            "consolidation_approach": "default_consolidation_approach",
            "ghg_scope_approach": "default_ghg_scope_approach",
        }
        for public_field, model_field in field_mapping.items():
            if public_field not in updates:
                continue
            value = updates[public_field]
            if getattr(organization, model_field) != value:
                setattr(organization, model_field, value)
                changes[public_field] = value

        if "default_boundary_id" in updates:
            boundary_id = updates["default_boundary_id"]
            boundaries_result = await self.user_repo.session.execute(
                select(BoundaryDefinition).where(
                    BoundaryDefinition.organization_id == organization.id
                )
            )
            boundaries = boundaries_result.scalars().all()
            selected_boundary = None
            if boundary_id is not None:
                selected_boundary = next(
                    (boundary for boundary in boundaries if boundary.id == boundary_id), None
                )
                if not selected_boundary:
                    raise AppError("NOT_FOUND", 404, f"Boundary {boundary_id} not found")
            for boundary in boundaries:
                boundary.is_default = (
                    selected_boundary is not None and boundary.id == selected_boundary.id
                )
            changes["default_boundary_id"] = boundary_id

        await self.user_repo.session.flush()
        if changes:
            await self.audit_repo.log(
                entity_type="Organization",
                entity_id=organization.id,
                action="organization_settings_updated",
                user_id=ctx.user_id,
                organization_id=organization.id,
                changes=changes,
                performed_by_platform_admin=ctx.is_platform_admin,
            )

        return await self._serialize_organization_settings(organization)
