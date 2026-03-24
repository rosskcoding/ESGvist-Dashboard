from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.policies.standard_policy import StandardPolicy
from app.repositories.requirement_item_repo import RequirementItemRepository
from app.schemas.requirement_items import (
    DependencyCreate,
    DependencyOut,
    RequirementItemCreate,
    RequirementItemListOut,
    RequirementItemOut,
)
from app.services.requirement_item_service import RequirementItemService

router = APIRouter(tags=["Requirement Items"])


def _get_service(session: AsyncSession) -> RequirementItemService:
    return RequirementItemService(
        repo=RequirementItemRepository(session),
        policy=StandardPolicy(),
    )


@router.get("/api/disclosures/{disclosure_id}/items", response_model=RequirementItemListOut)
async def list_items(
    disclosure_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).list_items(disclosure_id, page, page_size)


@router.post(
    "/api/disclosures/{disclosure_id}/items",
    response_model=RequirementItemOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_item(
    disclosure_id: int,
    payload: RequirementItemCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).create_item(disclosure_id, payload, ctx)


@router.get("/api/items/{item_id}/dependencies", response_model=list[DependencyOut])
async def list_dependencies(
    item_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).list_dependencies(item_id)


@router.post(
    "/api/items/{item_id}/dependencies",
    response_model=DependencyOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_dependency(
    item_id: int,
    payload: DependencyCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).create_dependency(item_id, payload, ctx)
