from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.worker_lease import WorkerLease


class WorkerLeaseRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, name: str) -> WorkerLease | None:
        return await self.session.get(WorkerLease, name)

    async def acquire_or_renew(
        self,
        *,
        name: str,
        owner_id: str,
        ttl_seconds: int,
    ) -> tuple[WorkerLease, bool]:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)
        lease = await self.get(name)
        if lease is None:
            lease = WorkerLease(
                name=name,
                owner_id=owner_id,
                heartbeat_at=now,
                expires_at=expires_at,
            )
            self.session.add(lease)
            await self.session.flush()
            return lease, True

        current_expiry = lease.expires_at
        if current_expiry.tzinfo is None:
            current_expiry = current_expiry.replace(tzinfo=timezone.utc)

        if lease.owner_id == owner_id or current_expiry <= now:
            lease.owner_id = owner_id
            lease.heartbeat_at = now
            lease.expires_at = expires_at
            await self.session.flush()
            return lease, True

        return lease, False

    async def mark_started(self, *, name: str, owner_id: str, ttl_seconds: int) -> WorkerLease | None:
        lease, acquired = await self.acquire_or_renew(name=name, owner_id=owner_id, ttl_seconds=ttl_seconds)
        if not acquired:
            return None
        now = datetime.now(timezone.utc)
        lease.last_started_at = now
        lease.last_status = "running"
        lease.heartbeat_at = now
        lease.expires_at = now + timedelta(seconds=ttl_seconds)
        await self.session.flush()
        return lease

    async def mark_finished(
        self,
        *,
        name: str,
        owner_id: str,
        status: str,
        result: dict,
        ttl_seconds: int,
    ) -> WorkerLease | None:
        lease = await self.get(name)
        if lease is None or lease.owner_id != owner_id:
            return None
        now = datetime.now(timezone.utc)
        lease.heartbeat_at = now
        lease.expires_at = now + timedelta(seconds=ttl_seconds)
        lease.last_completed_at = now
        lease.last_status = status
        lease.last_result = result
        await self.session.flush()
        return lease

    async def release(self, *, name: str, owner_id: str, status: str, result: dict) -> WorkerLease | None:
        lease = await self.get(name)
        if lease is None or lease.owner_id != owner_id:
            return None
        now = datetime.now(timezone.utc)
        lease.heartbeat_at = now
        lease.expires_at = now
        lease.last_completed_at = now
        lease.last_status = status
        lease.last_result = result
        await self.session.flush()
        return lease

    async def list_active(self) -> list[WorkerLease]:
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(WorkerLease)
            .where(WorkerLease.expires_at > now)
            .order_by(WorkerLease.name)
        )
        return list(result.scalars().all())
