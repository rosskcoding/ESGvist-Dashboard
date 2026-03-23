from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.boundary import BoundaryDefinition
from app.core.exceptions import AppError
from app.db.models.boundary import BoundaryDefinition, BoundaryMembership
from app.db.models.project import MetricAssignment, ReportingProject, ReportingProjectStandard


class ProjectRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- Projects ---
    async def create_project(self, org_id: int, **kwargs) -> ReportingProject:
        p = ReportingProject(organization_id=org_id, **kwargs)
        self.session.add(p)
        await self.session.flush()
        return p

    async def get_project(self, project_id: int) -> ReportingProject | None:
        result = await self.session.execute(
            select(ReportingProject).where(ReportingProject.id == project_id)
        )
        return result.scalar_one_or_none()

    async def get_or_raise(self, project_id: int) -> ReportingProject:
        p = await self.get_project(project_id)
        if not p:
            raise AppError("NOT_FOUND", 404, f"Project {project_id} not found")
        return p

    async def get_boundary_or_raise(self, boundary_id: int) -> BoundaryDefinition:
        result = await self.session.execute(
            select(BoundaryDefinition).where(BoundaryDefinition.id == boundary_id)
        )
        boundary = result.scalar_one_or_none()
        if not boundary:
            raise AppError("NOT_FOUND", 404, f"Boundary {boundary_id} not found")
        return boundary

    async def list_projects(
        self, org_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[list[ReportingProject], int]:
        count_q = select(func.count()).select_from(ReportingProject).where(
            ReportingProject.organization_id == org_id
        )
        total = (await self.session.execute(count_q)).scalar_one()
        q = (
            select(ReportingProject)
            .where(ReportingProject.organization_id == org_id)
            .order_by(ReportingProject.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(q)
        return list(result.scalars().all()), total

    async def update_project(self, project_id: int, **kwargs) -> ReportingProject:
        p = await self.get_or_raise(project_id)
        for k, v in kwargs.items():
            if v is not None:
                setattr(p, k, v)
        await self.session.flush()
        return p

    # --- Project Standards ---
    async def add_standard(self, project_id: int, standard_id: int, is_base: bool = False):
        ps = ReportingProjectStandard(
            reporting_project_id=project_id,
            standard_id=standard_id,
            is_base_standard=is_base,
        )
        self.session.add(ps)
        await self.session.flush()
        return ps

    # --- Assignments ---
    async def create_assignment(self, project_id: int, **kwargs) -> MetricAssignment:
        a = MetricAssignment(reporting_project_id=project_id, **kwargs)
        self.session.add(a)
        await self.session.flush()
        return a

    async def list_assignments(self, project_id: int) -> list[MetricAssignment]:
        q = select(MetricAssignment).where(
            MetricAssignment.reporting_project_id == project_id
        )
        result = await self.session.execute(q)
        return list(result.scalars().all())

    # --- Boundaries ---
    async def create_boundary(self, org_id: int, **kwargs) -> BoundaryDefinition:
        b = BoundaryDefinition(organization_id=org_id, **kwargs)
        self.session.add(b)
        await self.session.flush()
        return b

    async def list_boundaries(self, org_id: int) -> list[BoundaryDefinition]:
        q = select(BoundaryDefinition).where(
            BoundaryDefinition.organization_id == org_id
        )
        result = await self.session.execute(q)
        return list(result.scalars().all())
