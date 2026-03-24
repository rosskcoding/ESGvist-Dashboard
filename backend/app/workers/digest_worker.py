from __future__ import annotations

from collections.abc import Callable

import structlog
from sqlalchemy import select

from app.core.metrics import record_non_blocking_failure
from app.db.models.notification import Notification
from app.db.models.user import User
from app.infrastructure.email import get_email_sender
from app.repositories.notification_repo import NotificationRepository
from app.services.notification_service import DEFAULT_NOTIFICATION_PREFS

logger = structlog.get_logger("app.digest_worker")


class DigestWorker:
    def __init__(self, session_factory: Callable):
        self.session_factory = session_factory

    async def run_daily_digest(self) -> int:
        return await self._run_digest("daily")

    async def run_weekly_digest(self) -> int:
        return await self._run_digest("weekly")

    async def _run_digest(self, frequency: str) -> int:
        async with self.session_factory() as session:
            repo = NotificationRepository(session)
            pending = await repo.list_pending_digest()
            if not pending:
                return 0

            # Filter to users who have this digest frequency
            user_ids = list(pending.keys())
            result = await session.execute(select(User).where(User.id.in_(user_ids)))
            users = {u.id: u for u in result.scalars().all()}

            email_sender = get_email_sender()
            total_sent = 0

            for user_id, notifications in pending.items():
                user = users.get(user_id)
                if not user:
                    continue

                prefs = {**DEFAULT_NOTIFICATION_PREFS, **(user.notification_prefs or {})}
                if prefs.get("digest_frequency") != frequency:
                    continue

                # Render digest email
                subject = (
                    f"ESGvist {frequency.capitalize()} Digest — "
                    f"{len(notifications)} notification(s)"
                )
                body = self._render_digest(notifications, user)

                try:
                    await email_sender.send(
                        to_email=user.email,
                        subject=subject,
                        body=body,
                    )
                    await repo.mark_digest_sent([n.id for n in notifications])
                    total_sent += 1
                except Exception:
                    record_non_blocking_failure("digest_worker", "email_delivery")
                    logger.warning(
                        "digest_delivery_failed",
                        user_id=user_id,
                        frequency=frequency,
                        notification_count=len(notifications),
                        exc_info=True,
                    )

            await session.commit()
            return total_sent

    @staticmethod
    def _render_digest(notifications: list[Notification], user: User) -> str:
        lines = [
            f"Hello {user.full_name or user.email},",
            "",
            f"Here is your notification digest ({len(notifications)} items):",
            "",
        ]
        for n in notifications[:50]:  # Cap at 50 items
            severity_icon = {
                "critical": "[!]",
                "important": "[*]",
                "warning": "[~]",
                "info": "[-]",
            }.get(n.severity, "[-]")
            lines.append(f"  {severity_icon} {n.title}: {n.message}")

        if len(notifications) > 50:
            lines.append(f"  ... and {len(notifications) - 50} more")

        lines.extend(
            [
                "",
                "Log in to ESGvist to view full details.",
                "",
                "— ESGvist Team",
            ]
        )
        return "\n".join(lines)
