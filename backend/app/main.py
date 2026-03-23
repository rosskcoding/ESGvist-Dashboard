from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (
    ai,
    audit,
    auth,
    comments,
    completeness,
    dashboard,
    data_points,
    deltas,
    entities,
    entity_tree,
    export,
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
    shared_elements,
    snapshots,
    standards,
    workflow,
)
from app.core.config import settings
from app.core.exceptions import AppError
from app.core.middleware import RequestIdMiddleware


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # Middleware
    app.add_middleware(RequestIdMiddleware)
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
    app.include_router(export.router)
    app.include_router(audit.router)
    app.include_router(merge.router)
    app.include_router(deltas.router)
    app.include_router(ai.router)
    app.include_router(platform.router)
    app.include_router(comments.router)
    app.include_router(invitations.router)
    app.include_router(impact.router)
    app.include_router(references.router)
    app.include_router(snapshots.router)
    app.include_router(dashboard.router)

    # Wire event bus
    from app.events.bus import get_event_bus
    from app.events.handlers.audit_handler import AuditEventHandler
    get_event_bus().subscribe("*", AuditEventHandler())

    return app


app = create_app()
