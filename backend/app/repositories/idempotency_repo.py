from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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

    async def try_reserve(
        self,
        *,
        organization_id: int,
        user_id: int | None,
        method: str,
        path: str,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> IdempotencyRecord | None:
        """Try to atomically reserve an idempotency key.

        Returns the existing record if the key was already taken (by a
        concurrent request), or None if reservation succeeded (the caller
        should proceed with the operation and then call finalize_record).

        Uses the unique constraint to detect conflicts — if two requests
        race, the loser gets an IntegrityError and falls back to reading
        the winner's record.
        """
        record = IdempotencyRecord(
            organization_id=organization_id,
            user_id=user_id,
            method=method,
            path=path,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            response_status_code=0,  # pending — will be updated by finalize
            response_body={},
        )
        try:
            self.session.add(record)
            await self.session.flush()
            return None  # Reserved successfully, caller proceeds
        except IntegrityError:
            await self.session.rollback()
            # Another request already claimed this key — return their record
            existing = await self.get_record(
                organization_id=organization_id,
                user_id=user_id,
                method=method,
                path=path,
                idempotency_key=idempotency_key,
            )
            return existing

    async def finalize_record(
        self,
        record: IdempotencyRecord,
        *,
        status_code: int,
        response_body: dict,
    ) -> None:
        """Update a reserved record with the final response."""
        record.response_status_code = status_code
        record.response_body = response_body
        await self.session.flush()

    async def create_record(self, **kwargs) -> IdempotencyRecord:
        record = IdempotencyRecord(**kwargs)
        self.session.add(record)
        await self.session.flush()
        return record
