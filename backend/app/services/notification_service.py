from sqlalchemy import select

from app.db.models.notification import Notification
from app.repositories.notification_repo import NotificationRepository


class NotificationService:
    def __init__(self, repo: NotificationRepository):
        self.repo = repo

    async def notify(
        self,
        user_id: int,
        org_id: int,
        type: str,
        title: str,
        message: str,
        entity_type: str | None = None,
        entity_id: int | None = None,
        severity: str = "info",
        triggered_by: int | None = None,
    ) -> dict | None:
        # No self-notify: don't notify the user who triggered the action
        if triggered_by and triggered_by == user_id:
            return None

        # Deduplication: don't create duplicate notification for same user+type+entity
        existing = await self.repo.session.execute(
            select(Notification).where(
                Notification.user_id == user_id,
                Notification.type == type,
                Notification.entity_type == entity_type,
                Notification.entity_id == entity_id,
                Notification.is_read == False,
            )
        )
        if existing.scalar_one_or_none():
            return None  # Already notified, skip

        n = await self.repo.create(
            organization_id=org_id,
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            entity_type=entity_type,
            entity_id=entity_id,
            severity=severity,
        )
        return {"id": n.id, "type": n.type, "title": n.title}

    async def list_notifications(self, user_id: int, page: int = 1, page_size: int = 20) -> dict:
        items, total = await self.repo.list_for_user(user_id, page, page_size)
        return {
            "items": [
                {
                    "id": n.id,
                    "type": n.type,
                    "title": n.title,
                    "message": n.message,
                    "entity_type": n.entity_type,
                    "entity_id": n.entity_id,
                    "severity": n.severity,
                    "is_read": n.is_read,
                    "created_at": n.created_at.isoformat() if n.created_at else None,
                }
                for n in items
            ],
            "total": total,
        }

    async def mark_read(self, notification_id: int, user_id: int) -> dict:
        await self.repo.mark_read(notification_id, user_id)
        return {"id": notification_id, "is_read": True}

    async def mark_all_read(self, user_id: int) -> dict:
        await self.repo.mark_all_read(user_id)
        return {"marked_all_read": True}

    async def unread_count(self, user_id: int) -> dict:
        count = await self.repo.unread_count(user_id)
        return {"unread_count": count}
