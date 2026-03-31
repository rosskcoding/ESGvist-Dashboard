from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.policies.standard_policy import StandardPolicy
from app.repositories.standard_repo import StandardRepository
from app.schemas.standards import (
    DisclosureCreate,
    DisclosureListOut,
    DisclosureOut,
    SectionCreate,
    SectionOut,
    StandardCreate,
    StandardListOut,
    StandardOut,
    StandardUpdate,
)
from app.services.standard_service import StandardService

router = APIRouter(prefix="/api/standards", tags=["Standards"])


def _get_service(session: AsyncSession) -> StandardService:
    return StandardService(
        repo=StandardRepository(session),
        policy=StandardPolicy(),
    )


# --- Standards ---
@router.get("", response_model=StandardListOut)
async def list_standards(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    service = _get_service(session)
    return await service.list_standards(page, page_size)


@router.post("", response_model=StandardOut, status_code=status.HTTP_201_CREATED)
async def create_standard(
    payload: StandardCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    service = _get_service(session)
    return await service.create_standard(payload, ctx)


@router.get("/{standard_id}", response_model=StandardOut)
async def get_standard(
    standard_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    service = _get_service(session)
    return await service.get_standard(standard_id)


@router.patch("/{standard_id}", response_model=StandardOut)
async def update_standard(
    standard_id: int,
    payload: StandardUpdate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    service = _get_service(session)
    return await service.update_standard(standard_id, payload, ctx)


@router.post("/{standard_id}/deactivate", response_model=StandardOut)
async def deactivate_standard(
    standard_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    service = _get_service(session)
    return await service.deactivate_standard(standard_id, ctx)


# --- Sections ---
@router.get("/{standard_id}/sections", response_model=list[SectionOut])
async def list_sections(
    standard_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    service = _get_service(session)
    return await service.list_sections(standard_id)


@router.post(
    "/{standard_id}/sections", response_model=SectionOut, status_code=status.HTTP_201_CREATED
)
async def create_section(
    standard_id: int,
    payload: SectionCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    service = _get_service(session)
    return await service.create_section(standard_id, payload, ctx)


# --- Disclosures ---
@router.get("/{standard_id}/disclosures", response_model=DisclosureListOut)
async def list_disclosures(
    standard_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    service = _get_service(session)
    return await service.list_disclosures(standard_id, page, page_size)


@router.post(
    "/{standard_id}/disclosures",
    response_model=DisclosureOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_disclosure(
    standard_id: int,
    payload: DisclosureCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    service = _get_service(session)
    return await service.create_disclosure(standard_id, payload, ctx)
