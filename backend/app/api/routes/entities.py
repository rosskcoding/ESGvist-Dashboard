from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    RequestContext,
    get_current_context,
    get_current_onboarding_context,
)
from app.db.session import get_session
from app.repositories.audit_repo import AuditRepository
from app.repositories.entity_repo import EntityRepository
from app.repositories.role_binding_repo import RoleBindingRepository
from app.schemas.entities import (
    ControlLinkCreate,
    ControlLinkOut,
    EntityCreate,
    EntityListOut,
    EntityOut,
    EntityUpdate,
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
        audit_repo=AuditRepository(session),
    )


@router.post("/api/organizations/setup", status_code=status.HTTP_201_CREATED)
async def setup_organization(
    payload: OrgSetupRequest,
    ctx: RequestContext = Depends(get_current_onboarding_context),
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


@router.patch("/api/entities/{entity_id}", response_model=EntityOut)
async def update_entity(
    entity_id: int,
    payload: EntityUpdate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).update_entity(entity_id, payload, ctx)


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


# -- Organization Settings ---------------------------------------------------


class OrgSettingsUpdate(BaseModel):
    name: str | None = None
    legal_name: str | None = None
    country: str | None = None
    jurisdiction: str | None = None
    industry: str | None = None
    default_currency: str | None = None
    default_reporting_year: int | None = None
    default_consolidation_approach: str | None = None
    default_ghg_scope_approach: str | None = None


@router.get("/api/organizations/settings")
async def get_org_settings(
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).get_org_settings(ctx)


@router.patch("/api/organizations/settings")
async def update_org_settings(
    payload: OrgSettingsUpdate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).update_org_settings(
        payload.model_dump(exclude_unset=True), ctx
    )
