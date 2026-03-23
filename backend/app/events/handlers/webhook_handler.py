"""Event handler that dispatches outbound webhooks."""

from collections.abc import Awaitable, Callable

from app.events.bus import (
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
)
from app.repositories.notification_repo import NotificationRepository
from app.repositories.webhook_repo import WebhookRepository
from app.services.webhook_service import WebhookService


class WebhookEventHandler:
    _dispatch_map: dict[type, str] = {
        DataPointSubmitted: "on_data_point_submitted",
        DataPointApproved: "on_data_point_approved",
        DataPointRejected: "on_data_point_rejected",
        DataPointRevisionRequested: "on_data_point_revision_requested",
        DataPointRolledBack: "on_data_point_rolled_back",
        ProjectStarted: "on_project_started",
        ProjectReviewStarted: "on_project_review_started",
        ProjectPublished: "on_project_published",
        BoundaryAppliedToProject: "on_boundary_applied",
        EvidenceCreated: "on_evidence_created",
        CompletenessUpdated: "on_completeness_updated",
    }

    def __init__(self, session_factory: Callable[[], Awaitable]):
        self.session_factory = session_factory

    async def __call__(self, event):
        method_name = self._dispatch_map.get(type(event))
        if method_name:
            method = getattr(self, method_name, None)
            if method:
                await method(event)

    async def _run(self, organization_id: int, event_type: str, payload: dict) -> None:
        async with self.session_factory() as session:
            try:
                service = WebhookService(
                    repo=WebhookRepository(session),
                    notification_repo=NotificationRepository(session),
                )
                await service.deliver_event(organization_id, event_type, payload)
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def on_data_point_submitted(self, event: DataPointSubmitted):
        await self._run(
            event.organization_id,
            "data_point.submitted",
            {
                "event": "data_point.submitted",
                "timestamp": event.timestamp.isoformat(),
                "data": {
                    "dataPointId": event.data_point_id,
                    "projectId": event.project_id,
                    "organizationId": event.organization_id,
                    "submittedBy": event.submitted_by,
                },
            },
        )

    async def on_data_point_approved(self, event: DataPointApproved):
        await self._run(
            event.organization_id,
            "data_point.approved",
            {
                "event": "data_point.approved",
                "timestamp": event.timestamp.isoformat(),
                "data": {
                    "dataPointId": event.data_point_id,
                    "organizationId": event.organization_id,
                    "reviewedBy": event.reviewed_by,
                },
            },
        )

    async def on_data_point_rejected(self, event: DataPointRejected):
        await self._run(
            event.organization_id,
            "data_point.rejected",
            {
                "event": "data_point.rejected",
                "timestamp": event.timestamp.isoformat(),
                "data": {
                    "dataPointId": event.data_point_id,
                    "organizationId": event.organization_id,
                    "reviewedBy": event.reviewed_by,
                    "comment": event.comment,
                },
            },
        )

    async def on_data_point_revision_requested(self, event: DataPointRevisionRequested):
        await self._run(
            event.organization_id,
            "data_point.needs_revision",
            {
                "event": "data_point.needs_revision",
                "timestamp": event.timestamp.isoformat(),
                "data": {
                    "dataPointId": event.data_point_id,
                    "organizationId": event.organization_id,
                    "reviewedBy": event.reviewed_by,
                    "comment": event.comment,
                },
            },
        )

    async def on_data_point_rolled_back(self, event: DataPointRolledBack):
        await self._run(
            event.organization_id,
            "data_point.rolled_back",
            {
                "event": "data_point.rolled_back",
                "timestamp": event.timestamp.isoformat(),
                "data": {
                    "dataPointId": event.data_point_id,
                    "organizationId": event.organization_id,
                    "rolledBackBy": event.rolled_back_by,
                    "reason": event.reason,
                },
            },
        )

    async def on_project_started(self, event: ProjectStarted):
        await self._run(
            event.organization_id,
            "project.started",
            {
                "event": "project.started",
                "timestamp": event.timestamp.isoformat(),
                "data": {
                    "projectId": event.project_id,
                    "organizationId": event.organization_id,
                    "projectName": event.project_name,
                    "startedBy": event.started_by,
                },
            },
        )

    async def on_project_review_started(self, event: ProjectReviewStarted):
        await self._run(
            event.organization_id,
            "project.in_review",
            {
                "event": "project.in_review",
                "timestamp": event.timestamp.isoformat(),
                "data": {
                    "projectId": event.project_id,
                    "organizationId": event.organization_id,
                    "projectName": event.project_name,
                    "startedBy": event.started_by,
                },
            },
        )

    async def on_project_published(self, event: ProjectPublished):
        await self._run(
            event.organization_id,
            "project.published",
            {
                "event": "project.published",
                "timestamp": event.timestamp.isoformat(),
                "data": {
                    "projectId": event.project_id,
                    "organizationId": event.organization_id,
                    "projectName": event.project_name,
                    "publishedBy": event.published_by,
                },
            },
        )

    async def on_boundary_applied(self, event: BoundaryAppliedToProject):
        await self._run(
            event.organization_id,
            "boundary.changed",
            {
                "event": "boundary.changed",
                "timestamp": event.timestamp.isoformat(),
                "data": {
                    "projectId": event.project_id,
                    "boundaryId": event.boundary_id,
                    "organizationId": event.organization_id,
                    "appliedBy": event.applied_by,
                },
            },
        )

    async def on_evidence_created(self, event: EvidenceCreated):
        await self._run(
            event.organization_id,
            "evidence.created",
            {
                "event": "evidence.created",
                "timestamp": event.timestamp.isoformat(),
                "data": {
                    "evidenceId": event.evidence_id,
                    "organizationId": event.organization_id,
                    "type": event.type,
                    "createdBy": event.created_by,
                },
            },
        )

    async def on_completeness_updated(self, event: CompletenessUpdated):
        await self._run(
            event.organization_id,
            "completeness.updated",
            {
                "event": "completeness.updated",
                "timestamp": event.timestamp.isoformat(),
                "data": {
                    "projectId": event.project_id,
                    "organizationId": event.organization_id,
                    "standardId": event.standard_id,
                    "overallStatus": event.overall_status,
                    "overallPercent": event.overall_percent,
                    "completeCount": event.complete_count,
                    "partialCount": event.partial_count,
                    "missingCount": event.missing_count,
                    "changed": event.changed,
                },
            },
        )
