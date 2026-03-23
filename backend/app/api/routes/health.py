import time

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session
from app.schemas.common import HealthResponse

try:
    from redis.asyncio import from_url as redis_from_url
except ModuleNotFoundError:  # pragma: no cover - fallback for minimal test envs
    redis_from_url = None

router = APIRouter(tags=["Health"])
STARTED_AT = time.monotonic()


def _uptime_seconds() -> int:
    return int(time.monotonic() - STARTED_AT)


async def _check_database(session: AsyncSession) -> str:
    try:
        await session.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "error"


async def _check_redis() -> str:
    if redis_from_url is None:
        return "error"
    try:
        client = redis_from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
        try:
            await client.ping()
        finally:
            await client.aclose()
        return "ok"
    except Exception:
        return "error"


async def _check_storage() -> str:
    if settings.storage_backend in {"local", "stub"}:
        return "ok"
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
