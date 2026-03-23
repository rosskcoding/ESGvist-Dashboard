from sqlalchemy import select

from app.db.models.notification import Notification
from app.db.models.role_binding import RoleBinding
from app.repositories.notification_repo import NotificationRepository

EVENT_ROUTING: dict[str, dict] = {
    "data_point_submitted": {"roles": ["reviewer"], "severity": "important"},
    "data_point_approved": {"roles": ["collector"], "severity": "info"},
    "data_point_rejected": {"roles": ["collector"], "severity": "important"},
    "assignment_created": {"roles": ["collector"], "severity": "important"},
    "assignment_overdue": {"roles": ["collector", "esg_manager"], "severity": "critical"},
    "project_started": {"roles": ["esg_manager", "admin"], "severity": "info"},
    "project_published": {"roles": ["esg_manager", "admin"], "severity": "important"},
    "boundary_changed": {"roles": ["esg_manager", "admin"], "severity": "warning"},
    "boundary_snapshot_created": {"roles": ["esg_manager", "admin"], "severity": "info"},
    "review_requested": {"roles": ["reviewer"], "severity": "important"},
}


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

    async def notify_event(
        self,
        event_type: str,
        context: dict,
        triggered_by: int | None = None,
    ) -> list[dict]:
        """Route an event to the appropriate users based on EVENT_ROUTING.

        Args:
            event_type: Key from EVENT_ROUTING (e.g. "data_point_submitted").
            context: Must include "org_id". May include "entity_type", "entity_id",
                     "title", "message" to customise the notification.
            triggered_by: User who caused the event (will be excluded via no-self-notify).
        """
        routing = EVENT_ROUTING.get(event_type)
        if not routing:
            return []

        org_id = context.get("org_id")
        if not org_id:
            return []

        target_roles = routing["roles"]
        severity = routing["severity"]

        # Look up users with matching roles in this org
        result = await self.repo.session.execute(
            select(RoleBinding.user_id).where(
                RoleBinding.scope_type == "organization",
                RoleBinding.scope_id == org_id,
                RoleBinding.role.in_(target_roles),
            )
        )
        user_ids = list({row[0] for row in result.all()})

        title = context.get("title", event_type.replace("_", " ").title())
        message = context.get("message", f"Event: {event_type}")
        entity_type = context.get("entity_type")
        entity_id = context.get("entity_id")

        results = []
        for uid in user_ids:
            notif = await self.notify(
                user_id=uid,
                org_id=org_id,
                type=event_type,
                title=title,
                message=message,
                entity_type=entity_type,
                entity_id=entity_id,
                severity=severity,
                triggered_by=triggered_by,
            )
            if notif:
                results.append(notif)

        return results
