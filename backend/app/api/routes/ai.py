import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.schemas.ai import (
    AIResponse,
    AIStatusOut,
    AskRequest,
    ExplainEvidenceRequest,
    ExplainRequest,
    ReviewAssistResponse,
)
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


@router.post("/explain/evidence", response_model=AIResponse)
async def explain_evidence(
    payload: ExplainEvidenceRequest,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).explain_evidence(payload, ctx)


@router.post("/ask", response_model=AIResponse)
async def ask(
    payload: AskRequest,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).ask(payload, ctx)


@router.post("/ask/stream")
async def ask_stream(
    payload: AskRequest,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    """Streaming Q&A endpoint.

    Returns NDJSON (newline-delimited JSON). Each line is one of:
    - ``{"type": "chunk", "text": "..."}``   — partial text
    - ``{"type": "done", "response": {...}}`` — final AIResponse
    - ``{"type": "error", "message": "..."}`` — LLM-level error (rare)

    Gate errors (rate limit, permission, prompt injection) raise **before**
    ``StreamingResponse`` is created, so the client receives a normal
    HTTP 400 / 403 / 429 with the standard error envelope — never a 200
    with an NDJSON error event.  Blocked requests are audit-logged.
    """
    service = _get_service(session)

    # ── Gates + context run OUTSIDE the generator ────────────────────
    # If any gate throws, FastAPI returns a proper HTTP error and the
    # service logs the blocked interaction.
    prepared = await service.ask_stream_prepare(payload, ctx)

    # ── Streaming generator (only reached if gates passed) ───────────
    async def stream_generator():
        try:
            async for event_type, data in service.ask_stream_generate(
                prepared, payload, ctx
            ):
                if event_type == "chunk":
                    yield json.dumps({"type": "chunk", "text": data}) + "\n"
                elif event_type == "done":
                    yield json.dumps({
                        "type": "done",
                        "response": data.model_dump(mode="json"),
                    }) + "\n"
        except Exception as exc:
            # Only LLM-level failures land here (gates already passed)
            error_msg = getattr(exc, "message", str(exc))
            yield json.dumps({"type": "error", "message": error_msg}) + "\n"

    return StreamingResponse(
        stream_generator(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/review-assist", response_model=ReviewAssistResponse | AIResponse)
async def review_assist(
    data_point_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).review_assist(data_point_id, ctx)
