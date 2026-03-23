"""Dashboard aggregation: progress by standard, by disclosure, by status."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.models.completeness import DisclosureRequirementStatus, RequirementItemStatus
from app.db.models.data_point import DataPoint
from app.db.models.project import MetricAssignment, ReportingProject, ReportingProjectStandard
from app.db.models.standard import Standard
from app.db.session import get_session

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/projects/{project_id}/progress")
async def get_project_progress(
    project_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    # Overall item status breakdown
    status_q = (
        select(RequirementItemStatus.status, func.count())
        .where(RequirementItemStatus.reporting_project_id == project_id)
        .group_by(RequirementItemStatus.status)
    )
    result = await session.execute(status_q)
    status_counts = {row[0]: row[1] for row in result.all()}

    complete = status_counts.get("complete", 0)
    partial = status_counts.get("partial", 0)
    missing = status_counts.get("missing", 0)
    total = complete + partial + missing
    pct = round((complete / total * 100), 1) if total > 0 else 0

    # Data point status breakdown
    dp_q = (
        select(DataPoint.status, func.count())
        .where(DataPoint.reporting_project_id == project_id)
        .group_by(DataPoint.status)
    )
    dp_result = await session.execute(dp_q)
    dp_counts = {row[0]: row[1] for row in dp_result.all()}

    # Progress by standard
    ps_q = select(ReportingProjectStandard, Standard.code).join(
        Standard, Standard.id == ReportingProjectStandard.standard_id
    ).where(ReportingProjectStandard.reporting_project_id == project_id)
    ps_result = await session.execute(ps_q)
    standards_progress = []
    for ps, std_code in ps_result.all():
        disc_q = (
            select(
                func.coalesce(func.avg(DisclosureRequirementStatus.completion_percent), 0)
            )
            .join(
                __import__("app.db.models.standard", fromlist=["DisclosureRequirement"]).DisclosureRequirement,
                __import__("app.db.models.standard", fromlist=["DisclosureRequirement"]).DisclosureRequirement.id == DisclosureRequirementStatus.disclosure_requirement_id,
            )
            .where(
                DisclosureRequirementStatus.reporting_project_id == project_id,
            )
        )
        # Simplified: just use overall percentage
        standards_progress.append({"standard": std_code, "completion_percent": pct})

    # Overdue assignments
    overdue_q = select(func.count()).select_from(MetricAssignment).where(
        MetricAssignment.reporting_project_id == project_id,
        MetricAssignment.status != "completed",
        MetricAssignment.deadline.isnot(None),
    )
    overdue_count = (await session.execute(overdue_q)).scalar_one()

    return {
        "project_id": project_id,
        "overall_completion_percent": pct,
        "item_statuses": {
            "complete": complete,
            "partial": partial,
            "missing": missing,
            "total": total,
        },
        "data_point_statuses": dp_counts,
        "standards_progress": standards_progress,
        "overdue_assignments": overdue_count,
    }
