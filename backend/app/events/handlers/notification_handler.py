"""Event handlers that create notifications."""

from app.events.bus import (
    DataPointApproved,
    DataPointRejected,
    DataPointRolledBack,
    DataPointSubmitted,
)


class NotificationEventHandler:
    """Creates notifications in response to domain events."""

    def __init__(self, notification_repo):
        self.notification_repo = notification_repo

    async def on_data_point_submitted(self, event: DataPointSubmitted):
        await self.notification_repo.create(
            organization_id=0,  # would resolve from project
            user_id=0,  # would resolve reviewer from assignment
            type="data_point_submitted",
            title="New data point for review",
            message="A data point has been submitted for your review.",
            entity_type="data_point",
            entity_id=event.data_point_id,
            severity="important",
        )

    async def on_data_point_approved(self, event: DataPointApproved):
        await self.notification_repo.create(
            organization_id=0,
            user_id=0,  # would resolve collector from assignment
            type="data_point_approved",
            title="Data point approved",
            message="Your data point has been approved.",
            entity_type="data_point",
            entity_id=event.data_point_id,
            severity="info",
        )

    async def on_data_point_rejected(self, event: DataPointRejected):
        await self.notification_repo.create(
            organization_id=0,
            user_id=0,  # would resolve collector
            type="data_point_rejected",
            title="Data point rejected",
            message=f"Your data point was rejected: {event.comment}",
            entity_type="data_point",
            entity_id=event.data_point_id,
            severity="critical",
        )

    async def on_data_point_rolled_back(self, event: DataPointRolledBack):
        await self.notification_repo.create(
            organization_id=0,
            user_id=0,
            type="data_point_rolled_back",
            title="Data point rolled back",
            message=f"Data point was rolled back to draft: {event.reason}",
            entity_type="data_point",
            entity_id=event.data_point_id,
            severity="important",
        )
