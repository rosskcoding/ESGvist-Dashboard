from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.schemas.ai import AIResponse, AIStatusOut, AskRequest, ExplainRequest, ReviewAssistResponse
from app.services.ai_service import AIAssistantService

router = APIRouter(prefix="/api/ai", tags=["AI Assistant"])


def _get_service(session: AsyncSession) -> AIAssistantService:
    return AIAssistantService(session)


@router.get("/status", response_model=AIStatusOut)
async def ai_status(
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return _get_service(session).get_status()


@router.post("/explain/field", response_model=AIResponse)
async def explain_field(
    payload: ExplainRequest,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).explain_field(payload, ctx)


@router.post("/explain/completeness", response_model=AIResponse)
async def explain_completeness(
    payload: ExplainRequest,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).explain_completeness(payload, ctx)


@router.post("/explain/boundary", response_model=AIResponse)
async def explain_boundary(
    payload: ExplainRequest,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).explain_boundary(payload, ctx)


@router.post("/ask", response_model=AIResponse)
async def ask(
    payload: AskRequest,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).ask(payload, ctx)


@router.post("/review-assist", response_model=ReviewAssistResponse | AIResponse)
async def review_assist(
    data_point_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).review_assist(data_point_id, ctx)
