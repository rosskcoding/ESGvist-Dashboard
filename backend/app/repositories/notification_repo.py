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
        self, user_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[list[Notification], int]:
        count_q = select(func.count()).select_from(Notification).where(Notification.user_id == user_id)
        total = (await self.session.execute(count_q)).scalar_one()

        q = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(q)
        return list(result.scalars().all()), total

    async def mark_read(self, notification_id: int, user_id: int) -> None:
        await self.session.execute(
            update(Notification)
            .where(Notification.id == notification_id, Notification.user_id == user_id)
            .values(is_read=True)
        )

    async def mark_all_read(self, user_id: int) -> None:
        await self.session.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read == False)
            .values(is_read=True)
        )

    async def unread_count(self, user_id: int) -> int:
        q = select(func.count()).select_from(Notification).where(
            Notification.user_id == user_id, Notification.is_read == False
        )
        return (await self.session.execute(q)).scalar_one()
