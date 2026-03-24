from fastapi import APIRouter, Depends

from app.core.access import get_project_for_ctx
from app.core.dependencies import RequestContext, get_current_context
from app.core.exceptions import AppError
from app.db.session import get_session
from app.events.bus import SnapshotSaved, get_event_bus
from app.policies.auth_policy import AuthPolicy
from app.policies.boundary_policy import BoundaryPolicy
from app.repositories.audit_repo import AuditRepository
from app.repositories.snapshot_repo import SnapshotRepository
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["Boundary Snapshots"])


def _repo(session: AsyncSession) -> SnapshotRepository:
    return SnapshotRepository(session)


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

    repo = _repo(session)
    boundary = await repo.get_boundary(proj.boundary_definition_id)
    memberships = await repo.list_memberships(proj.boundary_definition_id)

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

    existing = await repo.get_snapshot_by_project(project_id)
    if existing:
        existing.snapshot_data = snapshot_data
        existing.boundary_definition_id = proj.boundary_definition_id
        existing.created_by = ctx.user_id
        await session.flush()
        snapshot_id = existing.id
    else:
        snap = await repo.create_snapshot(
            reporting_project_id=project_id,
            boundary_definition_id=proj.boundary_definition_id,
            snapshot_data=snapshot_data,
            created_by=ctx.user_id,
        )
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
    snap = await _repo(session).get_snapshot_by_project(project_id)
    if not snap:
        raise AppError("NOT_FOUND", 404, "Snapshot not found")
    return {
        "id": snap.id,
        "project_id": snap.reporting_project_id,
        "boundary_id": snap.boundary_definition_id,
        "snapshot_data": snap.snapshot_data,
        "created_at": snap.created_at.isoformat() if snap.created_at else None,
    }
