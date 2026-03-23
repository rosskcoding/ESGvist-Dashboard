"""Dashboard aggregation: progress by standard, by disclosure, by status."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.services.dashboard_analytics_service import DashboardAnalyticsService
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/projects/{project_id}/overview")
async def get_project_overview(
    project_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await DashboardService(session).get_project_progress(project_id, ctx)


@router.get("/projects/{project_id}/progress")
async def get_project_progress(
    project_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await DashboardService(session).get_project_progress(project_id, ctx)


@router.get("/projects/{project_id}/priority-tasks")
async def get_project_priority_tasks(
    project_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await DashboardService(session).get_project_priority_tasks(project_id, ctx)


@router.get("/projects/{project_id}/analytics/trends")
async def get_project_trends(
    project_id: int,
    days: int = 30,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await DashboardAnalyticsService(session).get_project_trends(project_id, ctx, days=days)


@router.get("/projects/{project_id}/analytics/activity")
async def get_project_activity(
    project_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await DashboardAnalyticsService(session).get_project_activity(project_id, ctx)
