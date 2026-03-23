from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.repositories.entity_repo import EntityRepository
from app.repositories.role_binding_repo import RoleBindingRepository
from app.schemas.entities import (
    ControlLinkCreate,
    ControlLinkOut,
    EntityCreate,
    EntityListOut,
    EntityOut,
    OrgSetupRequest,
    OwnershipLinkCreate,
    OwnershipLinkOut,
)
from app.services.entity_service import EntityService

router = APIRouter(tags=["Company Structure"])


def _get_service(session: AsyncSession) -> EntityService:
    return EntityService(
        repo=EntityRepository(session),
        role_binding_repo=RoleBindingRepository(session),
    )


@router.post("/api/organizations/setup", status_code=status.HTTP_201_CREATED)
async def setup_organization(
    payload: OrgSetupRequest,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).setup_organization(payload, ctx)


@router.get("/api/entities", response_model=EntityListOut)
async def list_entities(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).list_entities(ctx, page, page_size)


@router.post("/api/entities", response_model=EntityOut, status_code=status.HTTP_201_CREATED)
async def create_entity(
    payload: EntityCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).create_entity(payload, ctx)


@router.post("/api/ownership-links", response_model=OwnershipLinkOut, status_code=status.HTTP_201_CREATED)
async def create_ownership(
    payload: OwnershipLinkCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).create_ownership(payload, ctx)


@router.post("/api/control-links", response_model=ControlLinkOut, status_code=status.HTTP_201_CREATED)
async def create_control(
    payload: ControlLinkCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).create_control(payload, ctx)
