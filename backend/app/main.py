from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (
    auth,
    entities,
    health,
    mappings,
    projects,
    requirement_items,
    shared_elements,
    standards,
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
        expose_headers=["X-Request-ID"],
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
    app.include_router(projects.router)

    return app


app = create_app()
