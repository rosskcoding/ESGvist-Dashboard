"""Event handlers that write audit log entries."""

from app.events.bus import (
    AssignmentCreated,
    AssignmentUpdated,
    BoundaryAppliedToProject,
    BoundaryCreated,
    BoundaryUpdated,
    ControlCreated,
    ControlUpdated,
    DataPointApproved,
    DataPointRejected,
    DataPointSubmitted,
    EntityCreated,
    EntityUpdated,
    EvidenceCreated,
    EvidenceLinked,
    EvidenceUnlinked,
    GateChecked,
    ManualBoundaryOverride,
    OrganizationCreated,
    OwnershipCreated,
    OwnershipUpdated,
    SnapshotSaved,
)


class AuditEventHandler:
    _dispatch_map: dict[type, str] = {
        DataPointSubmitted: "on_data_point_submitted",
        DataPointApproved: "on_data_point_approved",
        DataPointRejected: "on_data_point_rejected",
        EntityCreated: "on_entity_created",
        EntityUpdated: "on_entity_updated",
        OwnershipCreated: "on_ownership_created",
        OwnershipUpdated: "on_ownership_updated",
        ControlCreated: "on_control_created",
        ControlUpdated: "on_control_updated",
        BoundaryCreated: "on_boundary_created",
        BoundaryUpdated: "on_boundary_updated",
        BoundaryAppliedToProject: "on_boundary_applied",
        SnapshotSaved: "on_snapshot_saved",
        ManualBoundaryOverride: "on_manual_boundary_override",
        AssignmentCreated: "on_assignment_created",
        AssignmentUpdated: "on_assignment_updated",
        EvidenceCreated: "on_evidence_created",
        EvidenceLinked: "on_evidence_linked",
        EvidenceUnlinked: "on_evidence_unlinked",
        GateChecked: "on_gate_checked",
        OrganizationCreated: "on_organization_created",
    }

    def __init__(self, audit_repo=None):
        self.audit_repo = audit_repo

    async def __call__(self, event):
        method_name = self._dispatch_map.get(type(event))
        if method_name:
            method = getattr(self, method_name, None)
            if method:
                await method(event)

    # --- Data Point events ---
    async def on_data_point_submitted(self, event: DataPointSubmitted):
        await self.audit_repo.log(
            entity_type="DataPoint",
            entity_id=event.data_point_id,
            action="data_point_submitted",
            user_id=event.submitted_by,
        )

    async def on_data_point_approved(self, event: DataPointApproved):
        await self.audit_repo.log(
            entity_type="DataPoint",
            entity_id=event.data_point_id,
            action="data_point_approved",
            user_id=event.reviewed_by,
        )

    async def on_data_point_rejected(self, event: DataPointRejected):
        await self.audit_repo.log(
            entity_type="DataPoint",
            entity_id=event.data_point_id,
            action="data_point_rejected",
            user_id=event.reviewed_by,
            changes={"comment": event.comment},
        )

    # --- Entity events ---
    async def on_entity_created(self, event: EntityCreated):
        await self.audit_repo.log(
            entity_type="CompanyEntity",
            entity_id=event.entity_id,
            action="create_entity",
            organization_id=event.organization_id,
            changes={"entity_type": event.entity_type},
        )

    async def on_entity_updated(self, event: EntityUpdated):
        await self.audit_repo.log(
            entity_type="CompanyEntity",
            entity_id=event.entity_id,
            action="update_entity",
            changes=event.changes,
        )

    # --- Ownership events ---
    async def on_ownership_created(self, event: OwnershipCreated):
        await self.audit_repo.log(
            entity_type="OwnershipLink",
            action="create_ownership",
            changes={
                "parent_entity_id": event.parent_entity_id,
                "child_entity_id": event.child_entity_id,
                "ownership_percent": event.ownership_percent,
            },
        )

    async def on_ownership_updated(self, event: OwnershipUpdated):
        await self.audit_repo.log(
            entity_type="OwnershipLink",
            entity_id=event.link_id,
            action="update_ownership",
            changes=event.changes,
        )

    # --- Control events ---
    async def on_control_created(self, event: ControlCreated):
        await self.audit_repo.log(
            entity_type="ControlLink",
            action="create_control",
            changes={
                "controlling_entity_id": event.controlling_entity_id,
                "controlled_entity_id": event.controlled_entity_id,
            },
        )

    async def on_control_updated(self, event: ControlUpdated):
        await self.audit_repo.log(
            entity_type="ControlLink",
            entity_id=event.link_id,
            action="update_control",
            changes=event.changes,
        )

    # --- Boundary events ---
    async def on_boundary_created(self, event: BoundaryCreated):
        await self.audit_repo.log(
            entity_type="BoundaryDefinition",
            entity_id=event.boundary_id,
            action="create_boundary",
            organization_id=event.organization_id,
        )

    async def on_boundary_updated(self, event: BoundaryUpdated):
        await self.audit_repo.log(
            entity_type="BoundaryDefinition",
            entity_id=event.boundary_id,
            action="update_boundary",
            changes=event.changes,
        )

    async def on_boundary_applied(self, event: BoundaryAppliedToProject):
        await self.audit_repo.log(
            entity_type="ReportingProject",
            entity_id=event.project_id,
            action="apply_boundary_to_project",
            changes={"boundary_id": event.boundary_id},
        )

    # --- Snapshot events ---
    async def on_snapshot_saved(self, event: SnapshotSaved):
        await self.audit_repo.log(
            entity_type="BoundarySnapshot",
            entity_id=event.snapshot_id,
            action="save_snapshot",
            changes={
                "project_id": event.project_id,
                "boundary_id": event.boundary_id,
            },
        )

    async def on_manual_boundary_override(self, event: ManualBoundaryOverride):
        await self.audit_repo.log(
            entity_type="BoundaryMembership",
            entity_id=event.boundary_id,
            action="manual_boundary_override",
            user_id=event.overridden_by,
            changes={
                "entity_id": event.entity_id,
                "included": event.included,
            },
        )

    # --- Assignment events ---
    async def on_assignment_created(self, event: AssignmentCreated):
        await self.audit_repo.log(
            entity_type="MetricAssignment",
            entity_id=event.assignment_id,
            action="assignment_created",
            changes={"collector_id": event.collector_id},
        )

    async def on_assignment_updated(self, event: AssignmentUpdated):
        await self.audit_repo.log(
            entity_type="MetricAssignment",
            entity_id=event.assignment_id,
            action="assignment_updated",
            changes=event.changes,
        )

    # --- Evidence events ---
    async def on_evidence_created(self, event: EvidenceCreated):
        await self.audit_repo.log(
            entity_type="Evidence",
            entity_id=event.evidence_id,
            action="evidence_created",
            changes={"type": event.type},
        )

    async def on_evidence_linked(self, event: EvidenceLinked):
        await self.audit_repo.log(
            entity_type="Evidence",
            entity_id=event.evidence_id,
            action="evidence_linked",
            user_id=event.linked_by,
            changes={"data_point_id": event.data_point_id},
        )

    async def on_evidence_unlinked(self, event: EvidenceUnlinked):
        await self.audit_repo.log(
            entity_type="Evidence",
            entity_id=event.evidence_id,
            action="evidence_unlinked",
            user_id=event.unlinked_by,
            changes={"data_point_id": event.data_point_id},
        )

    # --- Gate events ---
    async def on_gate_checked(self, event: GateChecked):
        await self.audit_repo.log(
            entity_type="DataPoint",
            entity_id=event.data_point_id,
            action="gate_check",
            changes={
                "gate_action": event.action,
                "allowed": event.allowed,
                "failed_codes": event.failed_codes,
            },
        )

    # --- Organization events ---
    async def on_organization_created(self, event: OrganizationCreated):
        await self.audit_repo.log(
            entity_type="Organization",
            entity_id=event.organization_id,
            action="create",
            changes={"root_entity_id": event.root_entity_id},
        )
