from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.policies.standard_policy import StandardPolicy
from app.repositories.mapping_repo import MappingRepository
from app.schemas.mappings import (
    CrossStandardElement,
    MappingCreate,
    MappingListOut,
    MappingOut,
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
    page_size: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).list_mappings(page, page_size)


@router.post("", response_model=MappingOut, status_code=status.HTTP_201_CREATED)
async def create_mapping(
    payload: MappingCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).create_mapping(payload, ctx)


@router.get("/cross-standard", response_model=list[CrossStandardElement])
async def cross_standard(session: AsyncSession = Depends(get_session)):
    return await _get_service(session).get_cross_standard()
