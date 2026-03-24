from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.repositories.form_config_repo import FormConfigRepository
from app.schemas.form_config import (
    FormConfigCreate,
    FormConfigListOut,
    FormConfigOut,
    FormConfigUpdate,
)
from app.services.form_config_service import FormConfigService

router = APIRouter(prefix="/api/form-configs", tags=["Form Configuration"])


def _get_service(session: AsyncSession) -> FormConfigService:
    return FormConfigService(
        repo=FormConfigRepository(session),
        session=session,
    )


@router.post("", response_model=FormConfigOut, status_code=status.HTTP_201_CREATED)
async def create_config(
    payload: FormConfigCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).create(payload, ctx)


@router.get("", response_model=FormConfigListOut)
async def list_configs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).list_configs(ctx, page, page_size)


@router.get("/{config_id}", response_model=FormConfigOut)
async def get_config(
    config_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).get_config(config_id, ctx)


@router.patch("/{config_id}", response_model=FormConfigOut)
async def update_config(
    config_id: int,
    payload: FormConfigUpdate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).update_config(config_id, payload, ctx)


@router.get("/projects/{project_id}/active", response_model=FormConfigOut | None)
async def get_project_config(
    project_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).get_for_project(project_id, ctx)


@router.post("/projects/{project_id}/generate", response_model=FormConfigOut)
async def generate_config(
    project_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).generate_default(project_id, ctx)


@router.post("/projects/{project_id}/resync", response_model=FormConfigOut)
async def resync_project_config(
    project_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).resync_project_config(project_id, ctx)
