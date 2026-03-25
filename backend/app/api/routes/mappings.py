from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.policies.standard_policy import StandardPolicy
from app.repositories.mapping_repo import MappingRepository
from app.schemas.mappings import (
    CrossStandardElement,
    MappingCreate,
    MappingDiffOut,
    MappingListOut,
    MappingOut,
    MappingVersionListOut,
)
from app.services.mapping_service import MappingService

router = APIRouter(prefix="/api/mappings", tags=["Mappings"])


def _get_service(session: AsyncSession) -> MappingService:
    return MappingService(
        repo=MappingRepository(session),
        policy=StandardPolicy(),
    )


@router.get("", response_model=MappingListOut)
async def list_mappings(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).list_mappings(page, page_size, ctx)


@router.post("", response_model=MappingOut, status_code=status.HTTP_201_CREATED)
async def create_mapping(
    payload: MappingCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).create_mapping(payload, ctx)


@router.get("/{item_id}/{element_id}/history", response_model=MappingVersionListOut)
async def mapping_history(
    item_id: int,
    element_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).list_versions(item_id, element_id, ctx)


@router.get("/{item_id}/{element_id}/diff", response_model=MappingDiffOut)
async def mapping_diff(
    item_id: int,
    element_id: int,
    v1: int = Query(..., ge=1),
    v2: int = Query(..., ge=1),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).diff_versions(item_id, element_id, v1, v2, ctx)


@router.get("/cross-standard", response_model=list[CrossStandardElement])
async def cross_standard(
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).get_cross_standard(ctx)
