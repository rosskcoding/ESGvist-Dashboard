from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.db.models.data_point import DataPoint
from app.db.models.project import MetricAssignment, ReportingProject
from app.policies.auth_policy import AuthPolicy


async def get_project_or_raise(session: AsyncSession, project_id: int) -> ReportingProject:
    result = await session.execute(
        select(ReportingProject).where(ReportingProject.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise AppError("NOT_FOUND", 404, f"Project {project_id} not found")
    return project


async def get_project_for_ctx(
    session: AsyncSession,
    project_id: int,
    ctx: RequestContext,
    *,
    allow_collectors: bool = True,
    allow_reviewers: bool = True,
) -> ReportingProject:
    project = await get_project_or_raise(session, project_id)
    AuthPolicy.check_tenant_isolation(ctx, project.organization_id)

    if ctx.role == "collector":
        if not allow_collectors:
            raise AppError("FORBIDDEN", 403, "Collectors cannot access this project view")
        if not await user_has_project_assignment(session, project_id, ctx.user_id, "collector"):
            raise AppError("FORBIDDEN", 403, "Collectors can only access assigned projects")

    if ctx.role == "reviewer":
        if not allow_reviewers:
            raise AppError("FORBIDDEN", 403, "Reviewers cannot access this project view")
        if not await user_has_project_assignment(session, project_id, ctx.user_id, "reviewer"):
            raise AppError("FORBIDDEN", 403, "Reviewers can only access assigned projects")

    return project


async def user_has_project_assignment(
    session: AsyncSession,
    project_id: int,
    user_id: int,
    role: str,
) -> bool:
    assignment_column = (
        MetricAssignment.collector_id if role == "collector" else MetricAssignment.reviewer_id
    )
    result = await session.execute(
        select(MetricAssignment.id).where(
            MetricAssignment.reporting_project_id == project_id,
            assignment_column == user_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def get_user_assignments(
    session: AsyncSession,
    project_id: int,
    user_id: int,
    role: str,
) -> list[MetricAssignment]:
    assignment_column = (
        MetricAssignment.collector_id if role == "collector" else MetricAssignment.reviewer_id
    )
    result = await session.execute(
        select(MetricAssignment).where(
            MetricAssignment.reporting_project_id == project_id,
            assignment_column == user_id,
        )
    )
    return list(result.scalars().all())


def assignment_matches_data_point(assignment: MetricAssignment, data_point: DataPoint) -> bool:
    if assignment.shared_element_id != data_point.shared_element_id:
        return False
    if assignment.entity_id is not None and assignment.entity_id != data_point.entity_id:
        return False
    if assignment.facility_id is not None and assignment.facility_id != data_point.facility_id:
        return False
    return True


async def get_matching_assignment(
    session: AsyncSession,
    data_point: DataPoint,
    user_id: int,
    role: str,
) -> MetricAssignment | None:
    assignment_column = (
        MetricAssignment.collector_id if role == "collector" else MetricAssignment.reviewer_id
    )
    query = select(MetricAssignment).where(
        MetricAssignment.reporting_project_id == data_point.reporting_project_id,
        MetricAssignment.shared_element_id == data_point.shared_element_id,
        assignment_column == user_id,
    )
    if data_point.entity_id is not None:
        query = query.where(
            or_(
                MetricAssignment.entity_id == data_point.entity_id,
                MetricAssignment.entity_id.is_(None),
            )
        )
    if data_point.facility_id is not None:
        query = query.where(
            or_(
                MetricAssignment.facility_id == data_point.facility_id,
                MetricAssignment.facility_id.is_(None),
            )
        )
    result = await session.execute(query.order_by(MetricAssignment.id))
    return result.scalars().first()


async def get_data_point_for_ctx(
    session: AsyncSession,
    dp_id: int,
    ctx: RequestContext,
) -> tuple[DataPoint, ReportingProject, MetricAssignment | None]:
    result = await session.execute(select(DataPoint).where(DataPoint.id == dp_id))
    data_point = result.scalar_one_or_none()
    if not data_point:
        raise AppError("NOT_FOUND", 404, f"Data point {dp_id} not found")

    project = await get_project_for_ctx(session, data_point.reporting_project_id, ctx)
    assignment = None

    if ctx.role == "collector":
        assignment = await get_matching_assignment(session, data_point, ctx.user_id, "collector")
        if data_point.created_by != ctx.user_id and assignment is None:
            raise AppError("FORBIDDEN", 403, "Collectors can only access their own or assigned data points")

    if ctx.role == "reviewer":
        assignment = await get_matching_assignment(session, data_point, ctx.user_id, "reviewer")
        if assignment is None:
            raise AppError("FORBIDDEN", 403, "Reviewers can only access assigned data points")

    return data_point, project, assignment
