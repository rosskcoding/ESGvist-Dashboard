from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import get_project_for_ctx
from app.core.dependencies import RequestContext, get_current_context
from app.core.exceptions import AppError
from app.db.models.boundary import BoundaryDefinition, BoundaryMembership
from app.db.models.boundary_snapshot import BoundarySnapshot
from app.db.session import get_session
from app.policies.auth_policy import AuthPolicy
from app.policies.boundary_policy import BoundaryPolicy
from app.repositories.audit_repo import AuditRepository
from app.events.bus import SnapshotSaved, get_event_bus

router = APIRouter(tags=["Boundary Snapshots"])


@router.post("/api/projects/{project_id}/boundary/snapshot")
async def create_snapshot(
    project_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.require_manager_or_admin(ctx)
    proj = await get_project_for_ctx(session, project_id, ctx, allow_collectors=False, allow_reviewers=False)
    BoundaryPolicy.snapshot_immutable(proj.status)
    if not proj.boundary_definition_id:
        raise AppError("BOUNDARY_NOT_DEFINED", 422, "No boundary defined for project")

    # Build snapshot data
    boundary = (await session.execute(
        select(BoundaryDefinition).where(BoundaryDefinition.id == proj.boundary_definition_id)
    )).scalar_one()

    memberships = (await session.execute(
        select(BoundaryMembership).where(
            BoundaryMembership.boundary_definition_id == proj.boundary_definition_id
        )
    )).scalars().all()

    snapshot_data = {
        "boundary": {
            "id": boundary.id,
            "name": boundary.name,
            "boundary_type": boundary.boundary_type,
        },
        "memberships": [
            {
                "entity_id": m.entity_id,
                "included": m.included,
                "inclusion_source": m.inclusion_source,
                "consolidation_method": m.consolidation_method,
            }
            for m in memberships
        ],
    }

    # Upsert snapshot
    existing = (await session.execute(
        select(BoundarySnapshot).where(BoundarySnapshot.reporting_project_id == project_id)
    )).scalar_one_or_none()

    if existing:
        existing.snapshot_data = snapshot_data
        existing.boundary_definition_id = proj.boundary_definition_id
        existing.created_by = ctx.user_id
        snapshot_id = existing.id
    else:
        snap = BoundarySnapshot(
            reporting_project_id=project_id,
            boundary_definition_id=proj.boundary_definition_id,
            snapshot_data=snapshot_data,
            created_by=ctx.user_id,
        )
        session.add(snap)
        snapshot_id = None

    await session.flush()
    if snapshot_id is None:
        snapshot_id = snap.id

    await AuditRepository(session).log(
        entity_type="BoundarySnapshot",
        entity_id=snapshot_id,
        action="save_snapshot",
        user_id=ctx.user_id,
        organization_id=ctx.organization_id,
        changes={"project_id": project_id, "boundary_id": proj.boundary_definition_id},
    )
    await get_event_bus().publish(
        SnapshotSaved(
            snapshot_id=snapshot_id,
            project_id=project_id,
            boundary_id=proj.boundary_definition_id,
            organization_id=proj.organization_id,
            saved_by=ctx.user_id,
        )
    )
    return {"project_id": project_id, "snapshot_created": True, "entities_count": len(memberships)}


@router.get("/api/projects/{project_id}/boundary/snapshot")
async def get_snapshot(
    project_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.require_role(ctx, ["admin", "esg_manager", "reviewer", "auditor", "platform_admin"])
    await get_project_for_ctx(session, project_id, ctx, allow_collectors=False, allow_reviewers=True)
    snap = (await session.execute(
        select(BoundarySnapshot).where(BoundarySnapshot.reporting_project_id == project_id)
    )).scalar_one_or_none()

    if not snap:
        raise AppError("NOT_FOUND", 404, "Snapshot not found")

    return {
        "id": snap.id,
        "project_id": snap.reporting_project_id,
        "boundary_id": snap.boundary_definition_id,
        "snapshot_data": snap.snapshot_data,
        "created_at": snap.created_at.isoformat() if snap.created_at else None,
    }
