import argparse
import asyncio
import os
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.repositories.audit_repo import AuditRepository
from app.repositories.export_repo import ExportRepository
from app.repositories.notification_repo import NotificationRepository
from app.repositories.webhook_repo import WebhookRepository
from app.repositories.worker_lease_repo import WorkerLeaseRepository
from app.services.export_service import ExportService
from app.services.sla_service import SLAService
from app.services.webhook_service import WebhookService


class JobRunner:
    def __init__(
        self,
        session_factory: Callable[[], Awaitable[AsyncSession]] = async_session_factory,
        webhook_sender=None,
        *,
        owner_id: str | None = None,
        lease_name: str = "primary",
        lease_ttl_seconds: int = 60,
    ):
        self.session_factory = session_factory
        self.webhook_sender = webhook_sender
        self.owner_id = owner_id or f"pid-{os.getpid()}"
        self.lease_name = lease_name
        self.lease_ttl_seconds = lease_ttl_seconds

    async def run_sla_check(self) -> dict:
        async with self.session_factory() as session:
            result = await SLAService(session).check_sla_breaches()
            await session.commit()
            return result

    async def run_project_deadlines(self) -> dict:
        async with self.session_factory() as session:
            result = await SLAService(session).check_project_deadlines()
            await session.commit()
            return result

    async def run_webhook_retries(self, limit: int = 100) -> dict:
        async with self.session_factory() as session:
            service = WebhookService(
                repo=WebhookRepository(session),
                notification_repo=NotificationRepository(session),
                sender=self.webhook_sender,
            )
            result = await service.retry_due_deliveries(limit=limit)
            await session.commit()
            return result

    async def run_export_jobs(self, limit: int = 25) -> dict:
        async with self.session_factory() as session:
            result = await ExportService(
                session,
                repo=ExportRepository(session),
                audit_repo=AuditRepository(session),
            ).process_queued_jobs(limit=limit)
            await session.commit()
            return result

    async def run_all(self, limit: int = 100) -> dict:
        return {
            "sla_check": await self.run_sla_check(),
            "project_deadlines": await self.run_project_deadlines(),
            "webhook_retries": await self.run_webhook_retries(limit=limit),
            "export_jobs": await self.run_export_jobs(limit=limit),
        }

    async def run_selected(self, job: str, *, limit: int = 100) -> dict:
        if job == "sla-check":
            return await self.run_sla_check()
        if job == "project-deadlines":
            return await self.run_project_deadlines()
        if job == "webhook-retries":
            return await self.run_webhook_retries(limit=limit)
        if job == "export-jobs":
            return await self.run_export_jobs(limit=limit)
        return await self.run_all(limit=limit)

    async def collect_status(self) -> dict[str, Any]:
        async with self.session_factory() as session:
            return await self.collect_status_from_session(session)

    async def collect_status_from_session(self, session: AsyncSession) -> dict[str, Any]:
        export_repo = ExportRepository(session)
        webhook_repo = WebhookRepository(session)
        lease_repo = WorkerLeaseRepository(session)
        export_statuses = await export_repo.count_statuses()
        webhook_statuses = await webhook_repo.count_delivery_statuses()
        due_export_retries = await export_repo.count_due_retries()
        due_webhook_retries = await webhook_repo.count_due_retries(datetime.now(timezone.utc))
        active_leases = await lease_repo.list_active()
        return {
            "worker": {
                "lease_name": self.lease_name,
                "owner_id": self.owner_id,
                "lease_ttl_seconds": self.lease_ttl_seconds,
                "active_leases": [
                    {
                        "name": lease.name,
                        "owner_id": lease.owner_id,
                        "heartbeat_at": lease.heartbeat_at.isoformat() if lease.heartbeat_at else None,
                        "expires_at": lease.expires_at.isoformat() if lease.expires_at else None,
                        "last_status": lease.last_status,
                        "last_started_at": lease.last_started_at.isoformat() if lease.last_started_at else None,
                        "last_completed_at": (
                            lease.last_completed_at.isoformat() if lease.last_completed_at else None
                        ),
                    }
                    for lease in active_leases
                ],
            },
            "queues": {
                "exports": {
                    "statuses": export_statuses,
                    "due_retries": due_export_retries,
                    "queue_depth": sum(
                        export_statuses.get(status, 0)
                        for status in ("queued", "running", "retry_scheduled")
                    ),
                },
                "webhooks": {
                    "statuses": webhook_statuses,
                    "due_retries": due_webhook_retries,
                    "queue_depth": sum(
                        webhook_statuses.get(status, 0)
                        for status in ("failed", "dead_letter")
                    ),
                },
            },
        }

    async def run_cycle(self, job: str = "all", *, limit: int = 100) -> dict[str, Any]:
        async with self.session_factory() as session:
            lease_repo = WorkerLeaseRepository(session)
            lease, acquired = await lease_repo.acquire_or_renew(
                name=self.lease_name,
                owner_id=self.owner_id,
                ttl_seconds=self.lease_ttl_seconds,
            )
            if not acquired:
                await session.commit()
                return {
                    "job": job,
                    "owner_id": self.owner_id,
                    "lease_name": self.lease_name,
                    "skipped": True,
                    "lease_owner": lease.owner_id,
                }
            await lease_repo.mark_started(
                name=self.lease_name,
                owner_id=self.owner_id,
                ttl_seconds=self.lease_ttl_seconds,
            )
            await session.commit()

        try:
            result = await self.run_selected(job, limit=limit)
            final_status = "completed"
        except Exception as exc:
            result = {"job": job, "error": str(exc)}
            final_status = "failed"
            async with self.session_factory() as session:
                lease_repo = WorkerLeaseRepository(session)
                await lease_repo.release(
                    name=self.lease_name,
                    owner_id=self.owner_id,
                    status=final_status,
                    result=result,
                )
                await session.commit()
            raise

        async with self.session_factory() as session:
            lease_repo = WorkerLeaseRepository(session)
            await lease_repo.release(
                name=self.lease_name,
                owner_id=self.owner_id,
                status=final_status,
                result=result,
            )
            await session.commit()

        return {
            "job": job,
            "owner_id": self.owner_id,
            "lease_name": self.lease_name,
            "skipped": False,
            "result": result,
        }

    async def run_loop(
        self,
        job: str = "all",
        *,
        limit: int = 100,
        interval_seconds: int = 30,
        iterations: int | None = None,
    ) -> dict[str, Any]:
        runs = []
        current = 0
        while iterations is None or current < iterations:
            runs.append(await self.run_cycle(job, limit=limit))
            current += 1
            if iterations is not None and current >= iterations:
                break
            await asyncio.sleep(interval_seconds)
        return {
            "owner_id": self.owner_id,
            "lease_name": self.lease_name,
            "iterations": current,
            "runs": runs,
        }


async def _main_async(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description="Run scheduled ESGvist backend jobs")
    parser.add_argument(
        "job",
        choices=("sla-check", "project-deadlines", "webhook-retries", "export-jobs", "all"),
        default="all",
        nargs="?",
    )
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval-seconds", type=int, default=30)
    parser.add_argument("--iterations", type=int, default=None)
    parser.add_argument("--lease-seconds", type=int, default=60)
    parser.add_argument("--owner-id", type=str, default=None)
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args(argv)

    runner = JobRunner(
        owner_id=args.owner_id,
        lease_ttl_seconds=args.lease_seconds,
    )
    if args.status:
        return await runner.collect_status()
    if args.loop:
        return await runner.run_loop(
            args.job,
            limit=args.limit,
            interval_seconds=args.interval_seconds,
            iterations=args.iterations,
        )
    return await runner.run_cycle(args.job, limit=args.limit)


def main(argv: list[str] | None = None) -> dict:
    return asyncio.run(_main_async(argv))


if __name__ == "__main__":
    main()
