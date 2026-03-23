from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.policies.standard_policy import StandardPolicy
from app.repositories.shared_element_repo import SharedElementRepository
from app.schemas.shared_elements import (
    DimensionCreate,
    DimensionOut,
    SharedElementCreate,
    SharedElementListOut,
    SharedElementOut,
)
from app.services.shared_element_service import SharedElementService

router = APIRouter(prefix="/api/shared-elements", tags=["Shared Elements"])


def _get_service(session: AsyncSession) -> SharedElementService:
    return SharedElementService(
        repo=SharedElementRepository(session),
        policy=StandardPolicy(),
    )


@router.get("", response_model=SharedElementListOut)
async def list_elements(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).list_elements(page, page_size)


@router.post("", response_model=SharedElementOut, status_code=status.HTTP_201_CREATED)
async def create_element(
    payload: SharedElementCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).create_element(payload, ctx)


@router.get("/{element_id}", response_model=SharedElementOut)
async def get_element(
    element_id: int,
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).get_element(element_id)


@router.get("/{element_id}/dimensions", response_model=list[DimensionOut])
async def list_dimensions(
    element_id: int,
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).list_dimensions(element_id)


@router.post(
    "/{element_id}/dimensions",
    response_model=DimensionOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_dimension(
    element_id: int,
    payload: DimensionCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).create_dimension(element_id, payload, ctx)
