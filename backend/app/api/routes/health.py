import time

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.metrics import generate_metrics_response, record_health_check_result
from app.db.session import get_session
from app.schemas.common import HealthResponse

try:
    from redis.asyncio import from_url as redis_from_url
except ModuleNotFoundError:  # pragma: no cover - fallback for minimal test envs
    redis_from_url = None

router = APIRouter(tags=["Health"])
STARTED_AT = time.monotonic()
logger = structlog.get_logger("app.health")


def _uptime_seconds() -> int:
    return int(time.monotonic() - STARTED_AT)


async def _check_database(session: AsyncSession) -> str:
    try:
        await session.execute(text("SELECT 1"))
        record_health_check_result("database", "ok")
        return "ok"
    except Exception:
        record_health_check_result("database", "error")
        logger.warning("health_check_failed", dependency="database", exc_info=True)
        return "error"


async def _check_redis() -> str:
    if redis_from_url is None:
        record_health_check_result("redis", "error")
        logger.warning("health_check_dependency_unavailable", dependency="redis")
        return "error"
    try:
        client = redis_from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
        try:
            await client.ping()
        finally:
            await client.aclose()
        record_health_check_result("redis", "ok")
        return "ok"
    except Exception:
        record_health_check_result("redis", "error")
        logger.warning("health_check_failed", dependency="redis", exc_info=True)
        return "error"


async def _check_storage() -> str:
    if settings.storage_backend in {"local", "stub"}:
        record_health_check_result("storage", "ok")
        return "ok"
    try:
        from app.infrastructure.storage import get_storage

        healthy = await get_storage().health_check()
        status = "ok" if healthy else "error"
        record_health_check_result("storage", status)
        if status == "error":
            logger.warning("health_check_failed", dependency="storage", reason="health_check_false")
        return status
    except Exception:
        record_health_check_result("storage", "error")
        logger.warning("health_check_failed", dependency="storage", exc_info=True)
        return "error"


@router.get("/api/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="healthy",
        checks={"api": "ok"},
        version=settings.app_version,
        uptime=_uptime_seconds(),
    )


@router.get("/api/health/db", response_model=HealthResponse)
async def health_db(session: AsyncSession = Depends(get_session)):
    db_status = await _check_database(session)

    return HealthResponse(
        status="healthy" if db_status == "ok" else "unhealthy",
        checks={"database": db_status},
        version=settings.app_version,
        uptime=_uptime_seconds(),
    )


@router.get("/api/health/redis", response_model=HealthResponse)
async def health_redis():
    redis_status = await _check_redis()
    return HealthResponse(
        status="healthy" if redis_status == "ok" else "unhealthy",
        checks={"redis": redis_status},
        version=settings.app_version,
        uptime=_uptime_seconds(),
    )


@router.get("/api/health/storage", response_model=HealthResponse)
async def health_storage():
    storage_status = await _check_storage()
    return HealthResponse(
        status="healthy" if storage_status == "ok" else "unhealthy",
        checks={"storage": storage_status},
        version=settings.app_version,
        uptime=_uptime_seconds(),
    )


@router.get("/api/metrics")
async def metrics():
    body, content_type = generate_metrics_response()
    return Response(content=body, media_type=content_type)
