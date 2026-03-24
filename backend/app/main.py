from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (
    ai,
    audit,
    auth,
    calculations,
    comments,
    completeness,
    dashboard,
    data_points,
    deltas,
    entities,
    entity_tree,
    export,
    form_configs,
    health,
    impact,
    invitations,
    mappings,
    merge,
    notifications,
    platform,
    projects,
    references,
    requirement_items,
    reuse,
    review,
    runtime,
    shared_elements,
    snapshots,
    sso,
    standards,
    users,
    webhooks,
    workflow,
)
from app.core.config import settings
from app.core.csrf import CSRFMiddleware
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from app.core.metrics_middleware import MetricsMiddleware
from app.core.middleware import RequestIdMiddleware
from app.core.rate_limit import RateLimitMiddleware
from app.core.security_headers import SecurityHeadersMiddleware


def create_app() -> FastAPI:
    configure_logging(debug=settings.debug)
    settings.validate_runtime_configuration()
    logger = structlog.get_logger("app.runtime_config")

    for warning in settings.runtime_warnings():
        logger.warning(
            "runtime_configuration_warning",
            category="cors_origins",
            warning=warning,
            app_env=settings.app_env,
        )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        try:
            from app.core.schema_runtime import ensure_database_schema

            await ensure_database_schema(
                settings.database_url,
                auto_upgrade=getattr(settings, "db_auto_upgrade", False),
                require_current=getattr(settings, "require_current_db_revision", False),
            )
        except ImportError:
            pass  # alembic not installed — skip runtime schema check (tests, minimal envs)
        yield

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    # Middleware (order matters: outermost runs first)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(CSRFMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Request-Duration"],
    )

    # Exception handlers
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        request_id = getattr(request.state, "request_id", "unknown")
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_response(request_id),
        )

    # Routers
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(standards.router)
    app.include_router(requirement_items.router)
    app.include_router(shared_elements.router)
    app.include_router(mappings.router)
    app.include_router(entities.router)
    app.include_router(entity_tree.router)
    app.include_router(projects.router)
    app.include_router(data_points.router)
    app.include_router(workflow.router)
    app.include_router(completeness.router)
    app.include_router(reuse.router)
    app.include_router(notifications.router)
    app.include_router(review.router)
    app.include_router(runtime.router)
    app.include_router(export.router)
    app.include_router(audit.router)
    app.include_router(merge.router)
    app.include_router(deltas.router)
    app.include_router(ai.router)
    app.include_router(platform.router)
    app.include_router(users.router)
    app.include_router(comments.router)
    app.include_router(invitations.router)
    app.include_router(impact.router)
    app.include_router(references.router)
    app.include_router(snapshots.router)
    app.include_router(dashboard.router)
    app.include_router(webhooks.router)
    app.include_router(sso.router)
    app.include_router(calculations.router)
    app.include_router(form_configs.router)

    # Wire event bus
    from app.events.registry import register_event_handlers

    register_event_handlers()

    return app


app = create_app()
