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
class AssignmentUpdated(DomainEvent):
    assignment_id: int = 0
    changes: dict = field(default_factory=dict)


@dataclass
class EvidenceCreated(DomainEvent):
    evidence_id: int = 0
    type: str = ""


@dataclass
class EvidenceLinked(DomainEvent):
    evidence_id: int = 0
    data_point_id: int = 0
    linked_by: int = 0


@dataclass
class EvidenceUnlinked(DomainEvent):
    evidence_id: int = 0
    data_point_id: int = 0
    unlinked_by: int = 0


@dataclass
class EntityCreated(DomainEvent):
    entity_id: int = 0
    organization_id: int = 0
    entity_type: str = ""


@dataclass
class EntityUpdated(DomainEvent):
    entity_id: int = 0
    changes: dict = field(default_factory=dict)


@dataclass
class OwnershipCreated(DomainEvent):
    parent_entity_id: int = 0
    child_entity_id: int = 0
    ownership_percent: float = 0


@dataclass
class OwnershipUpdated(DomainEvent):
    link_id: int = 0
    changes: dict = field(default_factory=dict)


@dataclass
class ControlCreated(DomainEvent):
    controlling_entity_id: int = 0
    controlled_entity_id: int = 0


@dataclass
class ControlUpdated(DomainEvent):
    link_id: int = 0
    changes: dict = field(default_factory=dict)


@dataclass
class BoundaryCreated(DomainEvent):
    boundary_id: int = 0
    organization_id: int = 0


@dataclass
class BoundaryUpdated(DomainEvent):
    boundary_id: int = 0
    changes: dict = field(default_factory=dict)


@dataclass
class SnapshotSaved(DomainEvent):
    snapshot_id: int = 0
    project_id: int = 0
    boundary_id: int = 0


@dataclass
class ManualBoundaryOverride(DomainEvent):
    boundary_id: int = 0
    entity_id: int = 0
    included: bool = True
    overridden_by: int = 0


@dataclass
class GateChecked(DomainEvent):
    data_point_id: int = 0
    action: str = ""
    allowed: bool = True
    failed_codes: list = field(default_factory=list)


class EventBus:
    """In-process async event bus."""

    def __init__(self):
        self._handlers: dict[type, list[Callable]] = defaultdict(list)

    def subscribe(self, event_type, handler: Callable):
        self._handlers[event_type].append(handler)

    async def publish(self, event: DomainEvent):
        handlers = list(self._handlers.get(type(event), []))
        # Also invoke wildcard subscribers
        handlers.extend(self._handlers.get("*", []))
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Event handler failed: {e}", exc_info=True)


# Global singleton
_bus = EventBus()


def get_event_bus() -> EventBus:
    return _bus
