from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.core.exceptions import AppError
from app.db.models.boundary import BoundaryDefinition, BoundaryMembership
from app.db.models.boundary_snapshot import BoundarySnapshot
from app.db.models.project import ReportingProject
from app.db.session import get_session

router = APIRouter(tags=["Boundary Snapshots"])


@router.post("/api/projects/{project_id}/boundary/snapshot")
async def create_snapshot(
    project_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    proj = (await session.execute(
        select(ReportingProject).where(ReportingProject.id == project_id)
    )).scalar_one_or_none()
    if not proj:
        raise AppError("NOT_FOUND", 404, "Project not found")
    if proj.status == "published":
        raise AppError("SNAPSHOT_IMMUTABLE", 409, "Cannot modify snapshot of published project")
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
    else:
        snap = BoundarySnapshot(
            reporting_project_id=project_id,
            boundary_definition_id=proj.boundary_definition_id,
            snapshot_data=snapshot_data,
            created_by=ctx.user_id,
        )
        session.add(snap)

    await session.flush()
    return {"project_id": project_id, "snapshot_created": True, "entities_count": len(memberships)}


@router.get("/api/projects/{project_id}/boundary/snapshot")
async def get_snapshot(
    project_id: int,
    session: AsyncSession = Depends(get_session),
):
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
