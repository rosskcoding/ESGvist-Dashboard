import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class DomainEvent:
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DataPointSubmitted(DomainEvent):
    data_point_id: int = 0
    submitted_by: int = 0
    project_id: int = 0


@dataclass
class DataPointApproved(DomainEvent):
    data_point_id: int = 0
    reviewed_by: int = 0


@dataclass
class DataPointRejected(DomainEvent):
    data_point_id: int = 0
    reviewed_by: int = 0
    comment: str = ""


@dataclass
class DataPointRolledBack(DomainEvent):
    data_point_id: int = 0
    rolled_back_by: int = 0
    reason: str = ""


@dataclass
class BoundaryAppliedToProject(DomainEvent):
    project_id: int = 0
    boundary_id: int = 0


@dataclass
class OrganizationCreated(DomainEvent):
    organization_id: int = 0
    root_entity_id: int = 0


@dataclass
class AssignmentCreated(DomainEvent):
    assignment_id: int = 0
    collector_id: int = 0


@dataclass
class EvidenceCreated(DomainEvent):
    evidence_id: int = 0
    type: str = ""


class EventBus:
    """In-process async event bus."""

    def __init__(self):
        self._handlers: dict[type, list[Callable]] = defaultdict(list)

    def subscribe(self, event_type: type, handler: Callable):
        self._handlers[event_type].append(handler)

    async def publish(self, event: DomainEvent):
        handlers = self._handlers.get(type(event), [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Event handler failed: {e}", exc_info=True)


# Global singleton
_bus = EventBus()


def get_event_bus() -> EventBus:
    return _bus
