from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.boundary import BoundaryDefinition, BoundaryMembership
from app.db.models.boundary_snapshot import BoundarySnapshot


class SnapshotRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_boundary(self, boundary_id: int) -> BoundaryDefinition:
        result = await self.session.execute(
            select(BoundaryDefinition).where(BoundaryDefinition.id == boundary_id)
        )
        return result.scalar_one()

    async def list_memberships(self, boundary_id: int) -> list[BoundaryMembership]:
        result = await self.session.execute(
            select(BoundaryMembership).where(
                BoundaryMembership.boundary_definition_id == boundary_id
            )
        )
        return list(result.scalars().all())

    async def get_snapshot_by_project(self, project_id: int) -> BoundarySnapshot | None:
        result = await self.session.execute(
            select(BoundarySnapshot).where(BoundarySnapshot.reporting_project_id == project_id)
        )
        return result.scalar_one_or_none()

    async def create_snapshot(self, **kwargs) -> BoundarySnapshot:
        snap = BoundarySnapshot(**kwargs)
        self.session.add(snap)
        await self.session.flush()
        return snap
