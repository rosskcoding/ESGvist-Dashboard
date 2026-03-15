"""ESGvist Dashboard - FastAPI Application Entry Point."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError

from app.api.errors import CompanyContextRequiredError
from app.api.exception_handlers import integrity_error_handler
from app.api.exception_handlers import company_context_required_handler
from app.middleware.correlation import CorrelationMiddleware
from app.middleware.csrf import CSRFMiddleware
from app.middleware.metrics import MetricsMiddleware, metrics_endpoint
from app.api.v1 import (
    admin,
    audit_checks,
    auth,
    companies,
    esg,
    evidence,
    health,
    role_assignments,
)
from app.config import settings
from app.infra.database import async_session_factory, close_db
from app.infra.redis import close_redis

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown events."""
    # Seed development users (idempotent, development only)
    if settings.environment == "development" or settings.debug:
        try:
            from app.seeds.dev_users import seed_corporate_lead_user, seed_e2e_user

            async with async_session_factory() as session:
                changed_e2e = await seed_e2e_user(session)
                changed_corporate_lead = await seed_corporate_lead_user(session)

                if changed_e2e or changed_corporate_lead:
                    await session.commit()
                    logger.info(
                        "Seeded/updated dev users: e2e-test@example.com and lead@kazenergo.kz"
                    )
        except Exception as e:
            logger.warning(f"Failed to seed dev users: {e}")

    yield
    # Shutdown
    with suppress(Exception):
        await close_db()
    with suppress(Exception):
        await close_redis()


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title="ESGvist Dashboard API",
        version=settings.app_version,
        description="ESGvist Dashboard - ESG Data Management & RBAC API",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )

    # Exception handlers
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(CompanyContextRequiredError, company_context_required_handler)

    # Metrics middleware (innermost - records all requests)
    app.add_middleware(MetricsMiddleware)

    # Correlation ID middleware (sets request_id context)
    app.add_middleware(CorrelationMiddleware)

    # CSRF middleware (double-submit cookie protection)
    app.add_middleware(CSRFMiddleware)

    # CORS middleware (must be added last = outermost)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*", "X-CSRF-Token"],
    )

    # Prometheus metrics endpoint
    app.add_route("/metrics", metrics_endpoint, methods=["GET"])

    # Include routers
    app.include_router(health.router, tags=["Health"])
    app.include_router(auth.router, prefix="/api/v1")
    # Multi-tenant RBAC
    app.include_router(companies.router, prefix="/api/v1")
    app.include_router(role_assignments.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")
    app.include_router(evidence.router, prefix="/api/v1")
    app.include_router(audit_checks.router, prefix="/api/v1")
    # ESG Data
    app.include_router(esg.router, prefix="/api/v1")

    return app


app = create_app()
