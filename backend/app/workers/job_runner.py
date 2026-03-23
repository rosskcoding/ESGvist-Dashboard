import argparse
import asyncio
from collections.abc import Awaitable, Callable

from app.db.session import async_session_factory
from app.repositories.notification_repo import NotificationRepository
from app.repositories.webhook_repo import WebhookRepository
from app.services.sla_service import SLAService
from app.services.webhook_service import WebhookService


class JobRunner:
    def __init__(
        self,
        session_factory: Callable[[], Awaitable] = async_session_factory,
        webhook_sender=None,
    ):
        self.session_factory = session_factory
        self.webhook_sender = webhook_sender

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

    async def run_all(self, limit: int = 100) -> dict:
        return {
            "sla_check": await self.run_sla_check(),
            "project_deadlines": await self.run_project_deadlines(),
            "webhook_retries": await self.run_webhook_retries(limit=limit),
        }


async def _main_async(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description="Run scheduled ESGvist backend jobs")
    parser.add_argument(
        "job",
        choices=("sla-check", "project-deadlines", "webhook-retries", "all"),
        default="all",
        nargs="?",
    )
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args(argv)

    runner = JobRunner()
    if args.job == "sla-check":
        return await runner.run_sla_check()
    if args.job == "project-deadlines":
        return await runner.run_project_deadlines()
    if args.job == "webhook-retries":
        return await runner.run_webhook_retries(limit=args.limit)
    return await runner.run_all(limit=args.limit)


def main(argv: list[str] | None = None) -> dict:
    return asyncio.run(_main_async(argv))


if __name__ == "__main__":
    main()
