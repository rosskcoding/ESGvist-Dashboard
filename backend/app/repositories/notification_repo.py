from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.notification import Notification


class NotificationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> Notification:
        n = Notification(**kwargs)
        self.session.add(n)
        await self.session.flush()
        return n

    async def list_for_user(
        self,
        user_id: int,
        organization_id: int,
        page: int = 1,
        page_size: int = 20,
        *,
        type: str | None = None,
        severity: str | None = None,
        is_read: bool | None = None,
    ) -> tuple[list[Notification], int]:
        conditions = [
            Notification.user_id == user_id,
            Notification.organization_id == organization_id,
        ]
        if type:
            conditions.append(Notification.type == type)
        if severity:
            conditions.append(Notification.severity == severity)
        if is_read is not None:
            conditions.append(Notification.is_read == is_read)

        count_q = select(func.count()).select_from(Notification).where(*conditions)
        total = (await self.session.execute(count_q)).scalar_one()

        q = (
            select(Notification)
            .where(*conditions)
            .order_by(Notification.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(q)
        return list(result.scalars().all()), total

    async def mark_read(self, notification_id: int, user_id: int, organization_id: int) -> None:
        await self.session.execute(
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
                Notification.organization_id == organization_id,
            )
            .values(is_read=True, read_at=datetime.now(timezone.utc))
        )

    async def mark_all_read(self, user_id: int, organization_id: int) -> None:
        await self.session.execute(
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.organization_id == organization_id,
                Notification.is_read == False,
            )
            .values(is_read=True, read_at=datetime.now(timezone.utc))
        )

    async def unread_count(self, user_id: int, organization_id: int) -> int:
        q = select(func.count()).select_from(Notification).where(
            Notification.user_id == user_id,
            Notification.organization_id == organization_id,
            Notification.is_read == False,
        )
        return (await self.session.execute(q)).scalar_one()

    async def list_pending_digest(self) -> dict[int, list[Notification]]:
        q = select(Notification).where(
            Notification.email_sent == False,
            Notification.digest_sent == False,
            Notification.is_read == False,
        ).order_by(Notification.user_id, Notification.created_at.desc())
        result = await self.session.execute(q)
        notifications = list(result.scalars().all())
        grouped: dict[int, list[Notification]] = {}
        for n in notifications:
            grouped.setdefault(n.user_id, []).append(n)
        return grouped

    async def mark_digest_sent(self, notification_ids: list[int]) -> None:
        if not notification_ids:
            return
        await self.session.execute(
            update(Notification)
            .where(Notification.id.in_(notification_ids))
            .values(digest_sent=True, digest_sent_at=datetime.now(timezone.utc))
        )
