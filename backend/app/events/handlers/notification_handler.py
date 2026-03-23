"""Event handlers that persist notifications."""

from collections.abc import Awaitable, Callable

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
    ProjectPublished,
    ProjectReviewStarted,
    ProjectStarted,
    SnapshotSaved,
)
from app.repositories.notification_repo import NotificationRepository
from app.services.notification_service import NotificationService


class NotificationEventHandler:
    """Creates notifications in response to domain events."""

    _dispatch_map: dict[type, str] = {
        DataPointSubmitted: "on_data_point_submitted",
        DataPointApproved: "on_data_point_approved",
        DataPointRejected: "on_data_point_rejected",
        DataPointRevisionRequested: "on_data_point_revision_requested",
        DataPointRolledBack: "on_data_point_rolled_back",
        AssignmentCreated: "on_assignment_created",
        AssignmentUpdated: "on_assignment_updated",
        ProjectStarted: "on_project_started",
        ProjectReviewStarted: "on_project_review_started",
        ProjectPublished: "on_project_published",
        BoundaryAppliedToProject: "on_boundary_applied",
        SnapshotSaved: "on_snapshot_saved",
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

    async def _run(self, callback: Callable[[NotificationService], Awaitable[None]]) -> None:
        async with self.session_factory() as session:
            try:
                service = NotificationService(NotificationRepository(session))
                await callback(service)
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def _notify_users(
        self,
        *,
        user_ids: list[int],
        org_id: int,
        type: str,
        title: str,
        message: str,
        entity_type: str | None,
        entity_id: int | None,
        severity: str,
        triggered_by: int | None,
    ) -> None:
        unique_user_ids = sorted({user_id for user_id in user_ids if user_id})
        if not unique_user_ids or not org_id:
            return

        async def callback(service: NotificationService) -> None:
            for user_id in unique_user_ids:
                await service.notify(
                    user_id=user_id,
                    org_id=org_id,
                    type=type,
                    title=title,
                    message=message,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    severity=severity,
                    triggered_by=triggered_by,
                )

        await self._run(callback)

    async def _route_event(
        self,
        event_type: str,
        context: dict,
        triggered_by: int | None = None,
    ) -> None:
        async def callback(service: NotificationService) -> None:
            await service.notify_event(event_type, context, triggered_by=triggered_by)

        await self._run(callback)

    async def on_data_point_submitted(self, event: DataPointSubmitted):
        await self._notify_users(
            user_ids=event.target_user_ids,
            org_id=event.organization_id,
            type="data_point_submitted",
            title="New data point for review",
            message=f"Data point #{event.data_point_id} has been submitted for review.",
            entity_type="DataPoint",
            entity_id=event.data_point_id,
            severity="important",
            triggered_by=event.submitted_by,
        )

    async def on_data_point_approved(self, event: DataPointApproved):
        await self._notify_users(
            user_ids=event.target_user_ids,
            org_id=event.organization_id,
            type="data_point_approved",
            title="Data point approved",
            message=f"Your data point #{event.data_point_id} has been approved.",
            entity_type="DataPoint",
            entity_id=event.data_point_id,
            severity="info",
            triggered_by=event.reviewed_by,
        )

    async def on_data_point_rejected(self, event: DataPointRejected):
        await self._notify_users(
            user_ids=event.target_user_ids,
            org_id=event.organization_id,
            type="data_point_rejected",
            title="Data point rejected",
            message=f"Your data point #{event.data_point_id} was rejected. {event.comment or ''}".strip(),
            entity_type="DataPoint",
            entity_id=event.data_point_id,
            severity="critical",
            triggered_by=event.reviewed_by,
        )

    async def on_data_point_revision_requested(self, event: DataPointRevisionRequested):
        await self._notify_users(
            user_ids=event.target_user_ids,
            org_id=event.organization_id,
            type="data_point_revision_requested",
            title="Revision requested",
            message=f"Data point #{event.data_point_id} needs revision. {event.comment or ''}".strip(),
            entity_type="DataPoint",
            entity_id=event.data_point_id,
            severity="important",
            triggered_by=event.reviewed_by,
        )

    async def on_data_point_rolled_back(self, event: DataPointRolledBack):
        await self._notify_users(
            user_ids=event.target_user_ids,
            org_id=event.organization_id,
            type="data_point_rolled_back",
            title="Data point rolled back",
            message=f"Data point #{event.data_point_id} was rolled back to draft. {event.reason or ''}".strip(),
            entity_type="DataPoint",
            entity_id=event.data_point_id,
            severity="important",
            triggered_by=event.rolled_back_by,
        )

    async def on_assignment_created(self, event: AssignmentCreated):
        if event.collector_id:
            await self._notify_users(
                user_ids=[event.collector_id],
                org_id=event.organization_id,
                type="assignment_created",
                title="New assignment",
                message=f"You were assigned a metric in project #{event.project_id}.",
                entity_type="MetricAssignment",
                entity_id=event.assignment_id,
                severity="important",
                triggered_by=event.assigned_by,
            )
        if event.reviewer_id:
            await self._notify_users(
                user_ids=[event.reviewer_id],
                org_id=event.organization_id,
                type="review_requested",
                title="Review assignment",
                message=f"You were assigned to review data in project #{event.project_id}.",
                entity_type="MetricAssignment",
                entity_id=event.assignment_id,
                severity="important",
                triggered_by=event.assigned_by,
            )

    async def on_assignment_updated(self, event: AssignmentUpdated):
        changed_fields = ", ".join(sorted(event.changes.keys())) or "assignment details"
        await self._notify_users(
            user_ids=event.affected_user_ids,
            org_id=event.organization_id,
            type="assignment_updated",
            title="Assignment updated",
            message=f"Assignment #{event.assignment_id} was updated ({changed_fields}).",
            entity_type="MetricAssignment",
            entity_id=event.assignment_id,
            severity="info",
            triggered_by=event.updated_by,
        )

    async def on_project_started(self, event: ProjectStarted):
        await self._route_event(
            "project_started",
            {
                "org_id": event.organization_id,
                "title": "Project started",
                "message": f"Project '{event.project_name or event.project_id}' is now active.",
                "entity_type": "ReportingProject",
                "entity_id": event.project_id,
            },
            triggered_by=event.started_by,
        )

    async def on_project_review_started(self, event: ProjectReviewStarted):
        await self._notify_users(
            user_ids=event.target_user_ids,
            org_id=event.organization_id,
            type="review_requested",
            title="Project ready for review",
            message=f"Project '{event.project_name or event.project_id}' is ready for review.",
            entity_type="ReportingProject",
            entity_id=event.project_id,
            severity="important",
            triggered_by=event.started_by,
        )
        await self._route_event(
            "project_in_review",
            {
                "org_id": event.organization_id,
                "title": "Project moved to review",
                "message": f"Project '{event.project_name or event.project_id}' is now in review.",
                "entity_type": "ReportingProject",
                "entity_id": event.project_id,
            },
            triggered_by=event.started_by,
        )

    async def on_project_published(self, event: ProjectPublished):
        await self._route_event(
            "project_published",
            {
                "org_id": event.organization_id,
                "title": "Project published",
                "message": f"Project '{event.project_name or event.project_id}' has been published.",
                "entity_type": "ReportingProject",
                "entity_id": event.project_id,
            },
            triggered_by=event.published_by,
        )

    async def on_boundary_applied(self, event: BoundaryAppliedToProject):
        await self._route_event(
            "boundary_changed",
            {
                "org_id": event.organization_id,
                "title": "Boundary updated",
                "message": f"Boundary #{event.boundary_id} was applied to project #{event.project_id}.",
                "entity_type": "ReportingProject",
                "entity_id": event.project_id,
            },
            triggered_by=event.applied_by,
        )

    async def on_snapshot_saved(self, event: SnapshotSaved):
        await self._route_event(
            "boundary_snapshot_created",
            {
                "org_id": event.organization_id,
                "title": "Boundary snapshot saved",
                "message": f"Boundary snapshot #{event.snapshot_id} was saved for project #{event.project_id}.",
                "entity_type": "BoundarySnapshot",
                "entity_id": event.snapshot_id,
            },
            triggered_by=event.saved_by,
        )

    async def on_completeness_updated(self, event: CompletenessUpdated):
        event_type = "completeness_100_percent" if event.overall_status == "complete" else "completeness_recalculated"
        title = "Project completeness reached 100%" if event.overall_status == "complete" else "Project completeness recalculated"
        message = (
            f"Project #{event.project_id} is now {event.overall_percent}% complete."
            if event.overall_status == "complete"
            else (
                f"Project #{event.project_id} completeness updated to {event.overall_percent}% "
                f"(complete={event.complete_count}, partial={event.partial_count}, missing={event.missing_count})."
            )
        )
        await self._route_event(
            event_type,
            {
                "org_id": event.organization_id,
                "title": title,
                "message": message,
                "entity_type": "ReportingProject",
                "entity_id": event.project_id,
            },
            triggered_by=event.triggered_by,
        )
