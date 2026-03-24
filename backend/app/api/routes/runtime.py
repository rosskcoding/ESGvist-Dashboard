import structlog
from fastapi import APIRouter, Request, status

from app.core.metrics import record_client_runtime_event
from app.schemas.runtime_events import ClientRuntimeEventIn, ClientRuntimeEventOut

router = APIRouter(prefix="/api/runtime", tags=["Runtime"])
logger = structlog.get_logger("app.client_runtime")


@router.post(
    "/client-events",
    response_model=ClientRuntimeEventOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_client_event(payload: ClientRuntimeEventIn, request: Request):
    record_client_runtime_event(payload.event_type, payload.level)
    log_method = getattr(logger, payload.level, logger.error)
    log_method(
        "client_runtime_event",
        event_type=payload.event_type,
        path=payload.path,
        status=payload.status,
        code=payload.code,
        request_id=payload.request_id or getattr(request.state, "request_id", "unknown"),
        user_agent=payload.user_agent,
        details=payload.details,
        message=payload.message,
    )
    return ClientRuntimeEventOut()
