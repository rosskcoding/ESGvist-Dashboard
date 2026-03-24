"""Service for platform-admin operations."""

from app.core.config import settings
from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.repositories.audit_repo import AuditRepository
from app.repositories.platform_repo import PlatformRepository


class PlatformService:
    def __init__(self, repo: PlatformRepository, audit_repo: AuditRepository):
        self.repo = repo
        self.audit = audit_repo

    def _require_platform(self, ctx: RequestContext) -> None:
        if not ctx.is_platform_admin:
            raise AppError(
                "PLATFORM_ADMIN_REQUIRED", 403, "Platform admin access required"
            )

    async def _audit(
        self, ctx: RequestContext, *, entity_type: str, action: str,
        entity_id: int | None = None, organization_id: int | None = None,
        changes: dict | None = None,
    ) -> None:
        await self.audit.log(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            user_id=ctx.user_id,
            organization_id=organization_id,
            changes=changes,
            performed_by_platform_admin=True,
        )

    # -- Tenants ---------------------------------------------------------------

    async def list_tenants(self, ctx: RequestContext, *, page: int, page_size: int):
        self._require_platform(ctx)
        total = await self.repo.count_tenants()
        tenants = await self.repo.list_tenants(
            offset=(page - 1) * page_size, limit=page_size
        )
        items = []
        for org in tenants:
            user_count = await self.repo.count_users_in_tenant(org.id)
            items.append({
                "id": org.id,
                "name": org.name,
                "country": org.country,
                "industry": org.industry,
                "status": org.status,
                "setup_completed": org.setup_completed,
                "user_count": user_count,
            })
        return {"items": items, "total": total}

    async def create_tenant(self, ctx: RequestContext, *, name: str, country: str | None, industry: str | None):
        self._require_platform(ctx)
        org = await self.repo.create_tenant(name=name, country=country, industry=industry)
        await self._audit(
            ctx, entity_type="Organization", entity_id=org.id,
            organization_id=org.id, action="platform_tenant_created",
            changes={"name": name, "country": country, "industry": industry},
        )
        return org

    async def get_tenant(self, ctx: RequestContext, tenant_id: int):
        self._require_platform(ctx)
        org = await self.repo.get_tenant(tenant_id)
        if not org:
            raise AppError("NOT_FOUND", 404, f"Tenant {tenant_id} not found")
        return org

    async def update_tenant(self, ctx: RequestContext, tenant_id: int, changes: dict):
        self._require_platform(ctx)
        org = await self.repo.get_tenant(tenant_id)
        if not org:
            raise AppError("NOT_FOUND", 404, f"Tenant {tenant_id} not found")
        for key, value in changes.items():
            setattr(org, key, value)
        await self._audit(
            ctx, entity_type="Organization", entity_id=org.id,
            organization_id=org.id, action="platform_tenant_updated", changes=changes,
        )
        return org

    async def set_tenant_status(self, ctx: RequestContext, tenant_id: int, new_status: str):
        self._require_platform(ctx)
        org = await self.repo.get_tenant(tenant_id)
        if not org:
            raise AppError("NOT_FOUND", 404, f"Tenant {tenant_id} not found")
        org.status = new_status
        await self._audit(
            ctx, entity_type="Organization", entity_id=org.id,
            organization_id=org.id, action=f"platform_tenant_{new_status}",
        )
        return org

    # -- Users -----------------------------------------------------------------

    async def list_users(self, ctx: RequestContext):
        self._require_platform(ctx)
        users = await self.repo.list_all_users()
        return [
            {"id": u.id, "email": u.email, "full_name": u.full_name, "is_active": u.is_active}
            for u in users
        ]

    # -- Admin assignment ------------------------------------------------------

    async def assign_tenant_admin(self, ctx: RequestContext, tenant_id: int, user_id: int):
        self._require_platform(ctx)
        org = await self.repo.get_tenant(tenant_id)
        if not org:
            raise AppError("NOT_FOUND", 404, f"Tenant {tenant_id} not found")
        user = await self.repo.get_user(user_id)
        if not user:
            raise AppError("NOT_FOUND", 404, f"User {user_id} not found")
        existing = await self.repo.get_role_binding(user_id, "organization", tenant_id)
        if existing:
            raise AppError("ROLE_BINDING_EXISTS", 409, "User already has a role in this organization")
        binding = await self.repo.create_role_binding(
            user_id=user_id, role="admin", scope_type="organization",
            scope_id=tenant_id, created_by=ctx.user_id,
        )
        await self._audit(
            ctx, entity_type="RoleBinding", entity_id=binding.id,
            organization_id=tenant_id, action="platform_tenant_admin_assigned",
            changes={"user_id": user_id, "role": "admin"},
        )
        return binding

    # -- Config ----------------------------------------------------------------

    async def get_self_registration(self, ctx: RequestContext):
        self._require_platform(ctx)
        return settings.self_registration_enabled

    async def set_self_registration(self, ctx: RequestContext, enabled: bool):
        self._require_platform(ctx)
        settings.allow_self_registration = enabled
        await self._audit(
            ctx, entity_type="PlatformSettings", action="platform_self_registration_updated",
            changes={"allow_self_registration": enabled},
        )
        return settings.self_registration_enabled

    # -- Support sessions ------------------------------------------------------

    async def start_support_session(self, ctx: RequestContext, tenant_id: int, reason: str):
        self._require_platform(ctx)
        org = await self.repo.get_tenant(tenant_id)
        if not org:
            raise AppError("NOT_FOUND", 404, f"Tenant {tenant_id} not found")
        existing = await self.repo.get_active_support_session(ctx.user_id)
        if existing:
            raise AppError("SUPPORT_SESSION_ACTIVE", 409, "You already have an active support session")
        ss = await self.repo.create_support_session(
            platform_admin_id=ctx.user_id, tenant_id=tenant_id, reason=reason,
        )
        await self._audit(
            ctx, entity_type="SupportSession", entity_id=ss.id,
            organization_id=tenant_id, action="support_session_started",
            changes={"reason": reason, "tenant_id": tenant_id},
        )
        return ss

    async def end_support_session(self, ctx: RequestContext, session_id: int):
        self._require_platform(ctx)
        ss = await self.repo.get_support_session(session_id, ctx.user_id)
        if not ss:
            raise AppError("NOT_FOUND", 404, "Support session not found")
        if not ss.is_active:
            raise AppError("ALREADY_ENDED", 409, "Support session already ended")
        await self.repo.end_support_session(ss)
        await self._audit(
            ctx, entity_type="SupportSession", entity_id=ss.id,
            organization_id=ss.tenant_id, action="support_session_ended",
        )
        return ss

    # -- Metrics ---------------------------------------------------------------

    async def get_platform_metrics(self, ctx: RequestContext) -> dict:
        self._require_platform(ctx)
        total_tenants = await self.repo.count_tenants()
        active_tenants = await self.repo.count_active_tenants()
        suspended_tenants = await self.repo.count_suspended_tenants()
        total_users = await self.repo.count_all_users()
        active_users = await self.repo.count_active_users()
        return {
            "tenants": {
                "total": total_tenants,
                "active": active_tenants,
                "suspended": suspended_tenants,
                "archived": total_tenants - active_tenants - suspended_tenants,
            },
            "users": {
                "total": total_users,
                "active": active_users,
                "inactive": total_users - active_users,
            },
        }

    # -- Cross-tenant user management ------------------------------------------

    async def list_tenant_users(self, ctx: RequestContext, tenant_id: int):
        self._require_platform(ctx)
        org = await self.repo.get_tenant(tenant_id)
        if not org:
            raise AppError("NOT_FOUND", 404, f"Tenant {tenant_id} not found")
        return await self.repo.list_users_in_tenant(tenant_id)
