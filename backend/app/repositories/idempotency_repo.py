from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.idempotency_record import IdempotencyRecord


class IdempotencyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_record(
        self,
        *,
        organization_id: int,
        user_id: int | None,
        method: str,
        path: str,
        idempotency_key: str,
    ) -> IdempotencyRecord | None:
        result = await self.session.execute(
            select(IdempotencyRecord).where(
                IdempotencyRecord.organization_id == organization_id,
                IdempotencyRecord.user_id == user_id,
                IdempotencyRecord.method == method,
                IdempotencyRecord.path == path,
                IdempotencyRecord.idempotency_key == idempotency_key,
            )
        )
        return result.scalar_one_or_none()

    async def create_record(self, **kwargs) -> IdempotencyRecord:
        record = IdempotencyRecord(**kwargs)
        self.session.add(record)
        await self.session.flush()
        return record
