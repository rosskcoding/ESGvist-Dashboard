"""Health check endpoints."""

from datetime import UTC, datetime
from enum import Enum
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text

from app.config import Settings, get_settings
from app.infra.database import engine
from app.infra.redis import get_redis

router = APIRouter()


class HealthStatus(str, Enum):
    """Health check status values."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ComponentHealth(BaseModel):
    """Health status for a single component."""

    status: HealthStatus
    message: str | None = None


class HealthResponse(BaseModel):
    """Response model for /health endpoint."""

    status: HealthStatus
    version: str
    environment: str
    timestamp: datetime
    components: dict[str, ComponentHealth] | None = None


class ReadyResponse(BaseModel):
    """Response model for /ready endpoint."""

    ready: bool
    checks: dict[str, bool]


@router.get("/health", response_model=HealthResponse)
async def health_check(
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthResponse:
    """
    Basic health check endpoint.

    Returns application status, version, and environment.
    Used for load balancer health checks.
    """
    return HealthResponse(
        status=HealthStatus.HEALTHY,
        version=settings.app_version,
        environment=settings.environment,
        timestamp=datetime.now(UTC),
    )


@router.get("/ready", response_model=ReadyResponse)
async def readiness_check() -> ReadyResponse:
    """
    Readiness check endpoint.

    Verifies that all required dependencies (DB, Redis) are available.
    Used by orchestrators to determine if the service can accept traffic.
    """
    checks: dict[str, bool] = {}

    # Database check
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False

    # Redis check
    try:
        redis_client = get_redis()
        await redis_client.ping()
        checks["redis"] = True
    except Exception:
        checks["redis"] = False

    ready = all(checks.values())
    return ReadyResponse(ready=ready, checks=checks)
