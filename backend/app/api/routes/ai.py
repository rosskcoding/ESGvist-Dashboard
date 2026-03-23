from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser, get_current_user
from app.db.session import get_session

router = APIRouter(prefix="/api/ai", tags=["AI Assistant"])


class ExplainRequest(BaseModel):
    requirement_item_id: int | None = None
    project_id: int | None = None
    entity_id: int | None = None
    disclosure_id: int | None = None


class AskRequest(BaseModel):
    question: str
    screen: str | None = None
    context: dict | None = None


class AIResponse(BaseModel):
    text: str
    reasons: list[str] | None = None
    next_actions: list[dict] | None = None
    confidence: str = "high"


@router.post("/explain/field", response_model=AIResponse)
async def explain_field(
    payload: ExplainRequest,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Explain a field — stub returning structured response."""
    return AIResponse(
        text="This field represents a quantitative ESG metric that needs to be reported according to the selected standard.",
        reasons=["Required by the standard disclosure requirement"],
        confidence="high",
    )


@router.post("/explain/completeness", response_model=AIResponse)
async def explain_completeness(
    payload: ExplainRequest,
    user: CurrentUser = Depends(get_current_user),
):
    return AIResponse(
        text="This disclosure is incomplete. Some required data points are missing or not yet approved.",
        reasons=["Missing data for required items", "Some data points pending review"],
        next_actions=[
            {"label": "Fill missing data", "action_type": "navigate", "target": "/collection"},
        ],
        confidence="high",
    )


@router.post("/explain/boundary", response_model=AIResponse)
async def explain_boundary(
    payload: ExplainRequest,
    user: CurrentUser = Depends(get_current_user),
):
    return AIResponse(
        text="This entity is included in the project boundary based on the selected consolidation approach.",
        reasons=["Entity is financially controlled", "Ownership is 100%"],
        confidence="high",
    )


@router.post("/ask", response_model=AIResponse)
async def ask(
    payload: AskRequest,
    user: CurrentUser = Depends(get_current_user),
):
    return AIResponse(
        text=f"Thank you for your question about: {payload.question}. AI assistance will be fully enabled in a future release.",
        confidence="low",
    )


@router.post("/review-assist")
async def review_assist(
    data_point_id: int,
    user: CurrentUser = Depends(get_current_user),
):
    return {
        "summary": "Data point contains a numeric value for Scope 1 emissions.",
        "anomalies": [],
        "missing_evidence": [],
        "draft_comment": None,
        "reuse_impact": "Used in 1 standard.",
    }
