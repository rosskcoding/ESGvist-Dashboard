from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log import AuditLog


class AuditRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def log(
        self,
        entity_type: str,
        action: str,
        user_id: int | None = None,
        organization_id: int | None = None,
        entity_id: int | None = None,
        changes: dict | None = None,
        request_id: str | None = None,
        performed_by_platform_admin: bool = False,
    ) -> AuditLog:
        entry = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            changes=changes,
            request_id=request_id,
            performed_by_platform_admin=performed_by_platform_admin,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    @staticmethod
    def _apply_filters(
        query,
        *,
        organization_id: int | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        action: str | None = None,
        user_id: int | None = None,
        request_id: str | None = None,
        performed_by_platform_admin: bool | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ):
        if organization_id is not None:
            query = query.where(AuditLog.organization_id == organization_id)
        if entity_type:
            query = query.where(AuditLog.entity_type == entity_type)
        if entity_id is not None:
            query = query.where(AuditLog.entity_id == entity_id)
        if action:
            query = query.where(AuditLog.action == action)
        if user_id is not None:
            query = query.where(AuditLog.user_id == user_id)
        if request_id:
            query = query.where(AuditLog.request_id == request_id)
        if performed_by_platform_admin is not None:
            query = query.where(AuditLog.performed_by_platform_admin == performed_by_platform_admin)
        if date_from is not None:
            query = query.where(AuditLog.created_at >= date_from)
        if date_to is not None:
            query = query.where(AuditLog.created_at <= date_to)
        return query

    async def list_logs(
        self,
        *,
        organization_id: int | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        action: str | None = None,
        user_id: int | None = None,
        request_id: str | None = None,
        performed_by_platform_admin: bool | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[AuditLog], int]:
        base = self._apply_filters(
            select(AuditLog),
            organization_id=organization_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            user_id=user_id,
            request_id=request_id,
            performed_by_platform_admin=performed_by_platform_admin,
            date_from=date_from,
            date_to=date_to,
        )
        count_query = self._apply_filters(
            select(func.count()).select_from(AuditLog),
            organization_id=organization_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            user_id=user_id,
            request_id=request_id,
            performed_by_platform_admin=performed_by_platform_admin,
            date_from=date_from,
            date_to=date_to,
        )
        total = int((await self.session.execute(count_query)).scalar_one())
        result = await self.session.execute(
            base.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def export_logs(
        self,
        *,
        organization_id: int | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        action: str | None = None,
        user_id: int | None = None,
        request_id: str | None = None,
        performed_by_platform_admin: bool | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[AuditLog]:
        query = self._apply_filters(
            select(AuditLog),
            organization_id=organization_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            user_id=user_id,
            request_id=request_id,
            performed_by_platform_admin=performed_by_platform_admin,
            date_from=date_from,
            date_to=date_to,
        ).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())
