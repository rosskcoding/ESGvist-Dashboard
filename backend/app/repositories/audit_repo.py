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
