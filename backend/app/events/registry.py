from collections.abc import Callable

from app.db.session import async_session_factory
from app.events.bus import (
    AssignmentCreated,
    AssignmentUpdated,
    BoundaryAppliedToProject,
    CompletenessUpdated,
    DataPointApproved,
    DataPointRejected,
    DataPointRevisionRequested,
    DataPointRolledBack,
    DataPointSubmitted,
    EvidenceCreated,
    ProjectPublished,
    ProjectReviewStarted,
    ProjectStarted,
    SnapshotSaved,
    get_event_bus,
)
from app.events.handlers.notification_handler import NotificationEventHandler
from app.events.handlers.webhook_handler import WebhookEventHandler

_event_session_factory: Callable = async_session_factory


def configure_event_session_factory(session_factory: Callable) -> None:
    global _event_session_factory
    _event_session_factory = session_factory


def register_event_handlers() -> None:
    bus = get_event_bus()
    bus.reset()

    notification_handler = NotificationEventHandler(_event_session_factory)
    webhook_handler = WebhookEventHandler(_event_session_factory)
    for event_type in (
        DataPointSubmitted,
        DataPointApproved,
        DataPointRejected,
        DataPointRevisionRequested,
        DataPointRolledBack,
        AssignmentCreated,
        AssignmentUpdated,
        EvidenceCreated,
        CompletenessUpdated,
        ProjectStarted,
        ProjectReviewStarted,
        ProjectPublished,
        BoundaryAppliedToProject,
        SnapshotSaved,
    ):
        bus.subscribe(event_type, notification_handler)
        bus.subscribe(event_type, webhook_handler)
