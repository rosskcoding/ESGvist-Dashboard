"""Event handlers that write audit log entries."""

from app.events.bus import (
    BoundaryAppliedToProject,
    DataPointApproved,
    DataPointRejected,
    DataPointSubmitted,
    OrganizationCreated,
)


class AuditEventHandler:
    def __init__(self, audit_repo):
        self.audit_repo = audit_repo

    async def on_data_point_submitted(self, event: DataPointSubmitted):
        await self.audit_repo.log(
            entity_type="DataPoint",
            entity_id=event.data_point_id,
            action="submit",
            user_id=event.submitted_by,
        )

    async def on_data_point_approved(self, event: DataPointApproved):
        await self.audit_repo.log(
            entity_type="DataPoint",
            entity_id=event.data_point_id,
            action="approve",
            user_id=event.reviewed_by,
        )

    async def on_data_point_rejected(self, event: DataPointRejected):
        await self.audit_repo.log(
            entity_type="DataPoint",
            entity_id=event.data_point_id,
            action="reject",
            user_id=event.reviewed_by,
            changes={"comment": event.comment},
        )

    async def on_boundary_applied(self, event: BoundaryAppliedToProject):
        await self.audit_repo.log(
            entity_type="ReportingProject",
            entity_id=event.project_id,
            action="apply_boundary",
            changes={"boundary_id": event.boundary_id},
        )

    async def on_organization_created(self, event: OrganizationCreated):
        await self.audit_repo.log(
            entity_type="Organization",
            entity_id=event.organization_id,
            action="create",
            changes={"root_entity_id": event.root_entity_id},
        )
