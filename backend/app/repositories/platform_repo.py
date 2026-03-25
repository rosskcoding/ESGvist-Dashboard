"""Repository for platform-admin operations (cross-tenant)."""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.organization import Organization
from app.db.models.platform_settings import PlatformSettings
from app.db.models.role_binding import RoleBinding
from app.db.models.support_session import SupportSession
from app.db.models.user import User


class PlatformRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # -- Tenants ---------------------------------------------------------------

    async def count_tenants(self) -> int:
        return (
            await self.session.execute(select(func.count()).select_from(Organization))
        ).scalar_one()

    async def list_tenants(self, *, offset: int, limit: int) -> list[Organization]:
        result = await self.session.execute(
            select(Organization).order_by(Organization.id).offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    async def get_tenant(self, tenant_id: int) -> Organization | None:
        result = await self.session.execute(
            select(Organization).where(Organization.id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def create_tenant(self, **kwargs) -> Organization:
        org = Organization(**kwargs, setup_completed=False, status="active")
        self.session.add(org)
        await self.session.flush()
        return org

    async def count_users_in_tenant(self, tenant_id: int) -> int:
        return (
            await self.session.execute(
                select(func.count())
                .select_from(RoleBinding)
                .where(
                    RoleBinding.scope_type == "organization",
                    RoleBinding.scope_id == tenant_id,
                )
            )
        ).scalar_one()

    # -- Users -----------------------------------------------------------------

    async def list_all_users(self) -> list[User]:
        result = await self.session.execute(select(User).order_by(User.id))
        return list(result.scalars().all())

    async def get_user(self, user_id: int) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    # -- Role bindings ---------------------------------------------------------

    async def get_role_binding(
        self, user_id: int, scope_type: str, scope_id: int
    ) -> RoleBinding | None:
        result = await self.session.execute(
            select(RoleBinding).where(
                RoleBinding.user_id == user_id,
                RoleBinding.scope_type == scope_type,
                RoleBinding.scope_id == scope_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_role_binding(self, **kwargs) -> RoleBinding:
        binding = RoleBinding(**kwargs)
        self.session.add(binding)
        await self.session.flush()
        return binding

    # -- Support sessions ------------------------------------------------------

    async def get_active_support_session(self, admin_id: int) -> SupportSession | None:
        result = await self.session.execute(
            select(SupportSession).where(
                SupportSession.platform_admin_id == admin_id,
                SupportSession.is_active == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_support_session(
        self, session_id: int, admin_id: int
    ) -> SupportSession | None:
        result = await self.session.execute(
            select(SupportSession).where(
                SupportSession.id == session_id,
                SupportSession.platform_admin_id == admin_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_support_session(self, **kwargs) -> SupportSession:
        ss = SupportSession(**kwargs)
        self.session.add(ss)
        await self.session.flush()
        return ss

    async def end_support_session(self, ss: SupportSession) -> None:
        ss.is_active = False
        ss.ended_at = datetime.now(UTC)
        await self.session.flush()

    # -- Metrics ---------------------------------------------------------------

    async def count_all_users(self) -> int:
        return (
            await self.session.execute(select(func.count()).select_from(User))
        ).scalar_one()

    async def count_active_users(self) -> int:
        return (
            await self.session.execute(
                select(func.count()).select_from(User).where(User.is_active == True)  # noqa: E712
            )
        ).scalar_one()

    async def count_active_tenants(self) -> int:
        return (
            await self.session.execute(
                select(func.count())
                .select_from(Organization)
                .where(Organization.status == "active")
            )
        ).scalar_one()

    async def count_suspended_tenants(self) -> int:
        return (
            await self.session.execute(
                select(func.count())
                .select_from(Organization)
                .where(Organization.status == "suspended")
            )
        ).scalar_one()

    # -- Cross-tenant user management ------------------------------------------

    # -- Platform settings -----------------------------------------------------

    async def get_platform_settings(self) -> PlatformSettings:
        result = await self.session.execute(
            select(PlatformSettings).where(PlatformSettings.id == 1)
        )
        settings_row = result.scalar_one_or_none()
        if not settings_row:
            settings_row = PlatformSettings(id=1, allow_self_registration=False)
            self.session.add(settings_row)
            await self.session.flush()
        return settings_row

    async def update_platform_settings(self, **kwargs) -> PlatformSettings:
        settings_row = await self.get_platform_settings()
        for key, value in kwargs.items():
            if hasattr(settings_row, key):
                setattr(settings_row, key, value)
        await self.session.flush()
        return settings_row

    async def list_users_in_tenant(self, tenant_id: int) -> list[dict]:
        result = await self.session.execute(
            select(User.id, User.email, User.full_name, User.is_active, RoleBinding.role)
            .join(RoleBinding, RoleBinding.user_id == User.id)
            .where(
                RoleBinding.scope_type == "organization",
                RoleBinding.scope_id == tenant_id,
            )
            .order_by(User.id)
        )
        return [
            {"id": uid, "email": email, "full_name": name, "is_active": active, "role": role}
            for uid, email, name, active, role in result.all()
        ]
