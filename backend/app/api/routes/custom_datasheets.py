from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.repositories.custom_datasheet_repo import CustomDatasheetRepository
from app.schemas.custom_datasheets import (
    CustomDatasheetCreate,
    CustomDatasheetCreateCustomMetric,
    CustomDatasheetDetailOut,
    CustomDatasheetItemCreate,
    CustomDatasheetItemOut,
    CustomDatasheetItemUpdate,
    CustomDatasheetListOut,
    CustomDatasheetOptionSearchListOut,
    CustomDatasheetOut,
    CustomDatasheetUpdate,
)
from app.services.custom_datasheet_service import CustomDatasheetService

router = APIRouter(tags=["Custom Datasheets"])


def _get_service(session: AsyncSession) -> CustomDatasheetService:
    return CustomDatasheetService(
        repo=CustomDatasheetRepository(session),
        session=session,
    )


@router.get("/api/projects/{project_id}/custom-datasheets", response_model=CustomDatasheetListOut)
async def list_project_custom_datasheets(
    project_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).list_project_datasheets(project_id, ctx, page, page_size)


@router.post(
    "/api/projects/{project_id}/custom-datasheets",
    response_model=CustomDatasheetOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_project_custom_datasheet(
    project_id: int,
    payload: CustomDatasheetCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).create_datasheet(project_id, payload, ctx)


@router.get(
    "/api/projects/{project_id}/custom-datasheets/{datasheet_id}/item-options",
    response_model=CustomDatasheetOptionSearchListOut,
)
async def search_custom_datasheet_item_options(
    project_id: int,
    datasheet_id: int,
    source: str = Query(...),
    q: str | None = Query(default=None),
    limit: int = Query(20, ge=1, le=50),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).search_add_item_options(
        project_id,
        datasheet_id,
        source=source,
        q=q,
        limit=limit,
        ctx=ctx,
    )


@router.get(
    "/api/projects/{project_id}/custom-datasheets/{datasheet_id}",
    response_model=CustomDatasheetDetailOut,
)
async def get_project_custom_datasheet(
    project_id: int,
    datasheet_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).get_datasheet_detail(project_id, datasheet_id, ctx)


@router.post(
    "/api/projects/{project_id}/custom-datasheets/{datasheet_id}/items",
    response_model=CustomDatasheetItemOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_project_custom_datasheet_item(
    project_id: int,
    datasheet_id: int,
    payload: CustomDatasheetItemCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).add_item(project_id, datasheet_id, payload, ctx)


@router.post(
    "/api/projects/{project_id}/custom-datasheets/{datasheet_id}/items/create-custom",
    response_model=CustomDatasheetItemOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_custom_metric_and_add_project_custom_datasheet_item(
    project_id: int,
    datasheet_id: int,
    payload: CustomDatasheetCreateCustomMetric,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).create_custom_metric_and_add_item(project_id, datasheet_id, payload, ctx)


@router.patch(
    "/api/projects/{project_id}/custom-datasheets/{datasheet_id}",
    response_model=CustomDatasheetOut,
)
async def update_project_custom_datasheet(
    project_id: int,
    datasheet_id: int,
    payload: CustomDatasheetUpdate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).update_datasheet(project_id, datasheet_id, payload, ctx)


@router.patch(
    "/api/projects/{project_id}/custom-datasheets/{datasheet_id}/items/{item_id}",
    response_model=CustomDatasheetItemOut,
)
async def update_project_custom_datasheet_item(
    project_id: int,
    datasheet_id: int,
    item_id: int,
    payload: CustomDatasheetItemUpdate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).update_item(project_id, datasheet_id, item_id, payload, ctx)


@router.post(
    "/api/projects/{project_id}/custom-datasheets/{datasheet_id}/archive",
    response_model=CustomDatasheetOut,
)
async def archive_project_custom_datasheet(
    project_id: int,
    datasheet_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).archive_datasheet(project_id, datasheet_id, ctx)


@router.post(
    "/api/projects/{project_id}/custom-datasheets/{datasheet_id}/items/{item_id}/archive",
    response_model=CustomDatasheetItemOut,
)
async def archive_project_custom_datasheet_item(
    project_id: int,
    datasheet_id: int,
    item_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).archive_item(project_id, datasheet_id, item_id, ctx)
