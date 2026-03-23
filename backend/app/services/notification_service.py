from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models.notification import Notification
from app.db.models.role_binding import RoleBinding
from app.repositories.notification_repo import NotificationRepository

EVENT_ROUTING: dict[str, dict] = {
    "data_point_submitted": {"roles": ["reviewer"], "severity": "important", "channel": "both"},
    "data_point_approved": {"roles": ["collector"], "severity": "info", "channel": "in_app"},
    "data_point_rejected": {"roles": ["collector"], "severity": "important", "channel": "both"},
    "assignment_created": {"roles": ["collector"], "severity": "important", "channel": "both"},
    "assignment_updated": {
        "roles": ["collector", "reviewer", "esg_manager", "admin"],
        "severity": "info",
        "channel": "in_app",
    },
    "assignment_overdue": {"roles": ["collector", "esg_manager"], "severity": "critical", "channel": "both"},
    "assignment_escalated": {
        "roles": ["collector", "esg_manager"],
        "severity": "critical",
        "channel": "both",
    },
    "sla_breach_level_1": {"roles": ["esg_manager"], "severity": "critical", "channel": "both"},
    "sla_breach_level_2": {"roles": ["admin"], "severity": "critical", "channel": "both"},
    "project_started": {"roles": ["esg_manager", "admin"], "severity": "important", "channel": "both"},
    "project_in_review": {"roles": ["esg_manager", "admin"], "severity": "important", "channel": "in_app"},
    "project_published": {"roles": ["esg_manager", "admin"], "severity": "important", "channel": "both"},
    "project_deadline_approaching": {
        "roles": ["esg_manager", "admin"],
        "severity": "important",
        "channel": "both",
    },
    "boundary_changed": {"roles": ["esg_manager", "admin"], "severity": "warning", "channel": "both"},
    "boundary_snapshot_created": {"roles": ["esg_manager", "admin"], "severity": "info", "channel": "in_app"},
    "review_requested": {"roles": ["reviewer"], "severity": "important", "channel": "both"},
    "completeness_recalculated": {"roles": ["esg_manager"], "severity": "info", "channel": "in_app"},
    "completeness_100_percent": {"roles": ["esg_manager"], "severity": "important", "channel": "both"},
    "webhook_dead_letter": {"roles": ["admin"], "severity": "critical", "channel": "both"},
}


class NotificationService:
    def __init__(self, repo: NotificationRepository):
        self.repo = repo

    def _resolve_channel(self, type: str, severity: str, channel: str | None) -> str:
        if channel:
            return channel
        routing = EVENT_ROUTING.get(type, {})
        if routing.get("channel"):
            return routing["channel"]
        return "both" if severity in {"critical", "important"} else "in_app"

    def _deliver_email(self, channel: str) -> tuple[bool, datetime | None]:
        if channel not in {"email", "both"}:
            return False, None
        return True, datetime.now(timezone.utc)

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
        channel: str | None = None,
        triggered_by: int | None = None,
    ) -> dict | None:
        # No self-notify: don't notify the user who triggered the action
        if triggered_by and triggered_by == user_id:
            return None

        # Deduplication: don't create duplicate notification for same user+type+entity
        existing = await self.repo.session.execute(
            select(Notification).where(
                Notification.organization_id == org_id,
                Notification.user_id == user_id,
                Notification.type == type,
                Notification.entity_type == entity_type,
                Notification.entity_id == entity_id,
                Notification.is_read == False,
            )
        )
        if existing.scalar_one_or_none():
            return None  # Already notified, skip

        resolved_channel = self._resolve_channel(type, severity, channel)
        email_sent, email_sent_at = self._deliver_email(resolved_channel)
        n = await self.repo.create(
            organization_id=org_id,
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            entity_type=entity_type,
            entity_id=entity_id,
            severity=severity,
            channel=resolved_channel,
            email_sent=email_sent,
            email_sent_at=email_sent_at,
        )
        return {
            "id": n.id,
            "type": n.type,
            "title": n.title,
            "channel": n.channel,
            "email_sent": n.email_sent,
        }

    async def list_notifications(
        self,
        user_id: int,
        org_id: int,
        page: int = 1,
        page_size: int = 20,
        *,
        type: str | None = None,
        severity: str | None = None,
        is_read: bool | None = None,
    ) -> dict:
        items, total = await self.repo.list_for_user(
            user_id,
            org_id,
            page,
            page_size,
            type=type,
            severity=severity,
            is_read=is_read,
        )
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
                    "channel": n.channel,
                    "is_read": n.is_read,
                    "read_at": n.read_at.isoformat() if n.read_at else None,
                    "email_sent": n.email_sent,
                    "email_sent_at": n.email_sent_at.isoformat() if n.email_sent_at else None,
                    "created_at": n.created_at.isoformat() if n.created_at else None,
                }
                for n in items
            ],
            "total": total,
        }

    async def mark_read(self, notification_id: int, user_id: int, org_id: int) -> dict:
        await self.repo.mark_read(notification_id, user_id, org_id)
        return {"id": notification_id, "is_read": True}

    async def mark_all_read(self, user_id: int, org_id: int) -> dict:
        await self.repo.mark_all_read(user_id, org_id)
        return {"marked_all_read": True}

    async def unread_count(self, user_id: int, org_id: int) -> dict:
        count = await self.repo.unread_count(user_id, org_id)
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
        channel = routing.get("channel")

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
                channel=channel,
                triggered_by=triggered_by,
            )
            if notif:
                results.append(notif)

        return results
