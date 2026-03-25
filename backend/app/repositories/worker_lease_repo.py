"""Worker lease repository with atomic acquisition.

Uses INSERT ... ON CONFLICT for PostgreSQL to prevent race conditions
where two workers try to acquire the same lease simultaneously.
Falls back to SELECT + conditional UPDATE for SQLite (test environment).
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.worker_lease import WorkerLease


def _is_postgres(session: AsyncSession) -> bool:
    dialect = session.bind.dialect.name if session.bind else ""
    return "postgres" in dialect


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
        """Atomically acquire or renew a worker lease.

        Returns (lease, acquired). ``acquired`` is True if the caller
        now owns the lease, False if another live owner holds it.
        """
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)

        if _is_postgres(self.session):
            return await self._acquire_postgres(name, owner_id, now, expires_at)
        return await self._acquire_fallback(name, owner_id, now, expires_at)

    async def _acquire_postgres(
        self, name: str, owner_id: str, now: datetime, expires_at: datetime
    ) -> tuple[WorkerLease, bool]:
        """Atomic upsert using INSERT ... ON CONFLICT DO UPDATE.

        The UPDATE fires only if the lease is expired OR owned by the same
        worker, preventing two workers from both thinking they acquired it.
        """
        stmt = text("""
            INSERT INTO worker_leases (name, owner_id, heartbeat_at, expires_at)
            VALUES (:name, :owner_id, :now, :expires_at)
            ON CONFLICT (name) DO UPDATE
              SET owner_id     = :owner_id,
                  heartbeat_at = :now,
                  expires_at   = :expires_at
              WHERE worker_leases.owner_id = :owner_id
                 OR worker_leases.expires_at <= :now
            RETURNING owner_id
        """)
        result = await self.session.execute(
            stmt, {"name": name, "owner_id": owner_id, "now": now, "expires_at": expires_at}
        )
        row = result.fetchone()
        await self.session.flush()

        lease = await self.get(name)
        if lease is None:
            # Should not happen after upsert, but defensive
            return WorkerLease(name=name, owner_id="", heartbeat_at=now, expires_at=now), False

        acquired = row is not None and lease.owner_id == owner_id
        return lease, acquired

    async def _acquire_fallback(
        self, name: str, owner_id: str, now: datetime, expires_at: datetime
    ) -> tuple[WorkerLease, bool]:
        """Non-atomic fallback for SQLite (test environment).

        Uses SELECT + conditional logic. Acceptable for tests where
        concurrency is not a real concern.
        """
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
