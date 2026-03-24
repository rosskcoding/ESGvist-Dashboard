from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.repositories.audit_repo import AuditRepository
from app.repositories.calculation_rule_repo import CalculationRuleRepository
from app.schemas.calculations import (
    CalculationRuleCreate,
    CalculationRuleListOut,
    CalculationRuleOut,
    RecalculateResult,
)
from app.services.calculation_service import CalculationService

router = APIRouter(prefix="/api/calculation-rules", tags=["Calculation Rules"])


def _get_service(session: AsyncSession) -> CalculationService:
    return CalculationService(
        repo=CalculationRuleRepository(session),
        session=session,
        audit_repo=AuditRepository(session),
    )


@router.post("", response_model=CalculationRuleOut, status_code=status.HTTP_201_CREATED)
async def create_rule(
    payload: CalculationRuleCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).create_rule(payload, ctx)


@router.get("", response_model=CalculationRuleListOut)
async def list_rules(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).list_rules(ctx, page, page_size)


@router.post(
    "/projects/{project_id}/recalculate",
    response_model=RecalculateResult,
)
async def recalculate_project(
    project_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).recalculate_for_project(project_id, ctx)
