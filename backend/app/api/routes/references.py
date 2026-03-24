from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.policies.auth_policy import AuthPolicy
from app.repositories.reference_repo import ReferenceRepository

router = APIRouter(prefix="/api/references", tags=["References"])


def _repo(session: AsyncSession) -> ReferenceRepository:
    return ReferenceRepository(session)


class RefCreate(BaseModel):
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    category: str | None = None
    description: str | None = None


@router.get("/units")
async def list_units(ctx: RequestContext = Depends(get_current_context), session: AsyncSession = Depends(get_session)):
    units = await _repo(session).list_units()
    return [{"id": u.id, "code": u.code, "name": u.name, "category": u.category} for u in units]


@router.post("/units", status_code=status.HTTP_201_CREATED)
async def create_unit(
    payload: RefCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.require_role(ctx, ["admin", "platform_admin"])
    u = await _repo(session).create_unit(code=payload.code, name=payload.name, category=payload.category)
    return {"id": u.id, "code": u.code, "name": u.name}


@router.get("/methodologies")
async def list_methodologies(ctx: RequestContext = Depends(get_current_context), session: AsyncSession = Depends(get_session)):
    methods = await _repo(session).list_methodologies()
    return [{"id": m.id, "code": m.code, "name": m.name, "description": m.description} for m in methods]


@router.post("/methodologies", status_code=status.HTTP_201_CREATED)
async def create_methodology(
    payload: RefCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.require_role(ctx, ["admin", "platform_admin"])
    m = await _repo(session).create_methodology(code=payload.code, name=payload.name, description=payload.description)
    return {"id": m.id, "code": m.code, "name": m.name}


@router.get("/boundary-approaches")
async def list_approaches(ctx: RequestContext = Depends(get_current_context), session: AsyncSession = Depends(get_session)):
    approaches = await _repo(session).list_boundary_approaches()
    return [{"id": b.id, "code": b.code, "name": b.name} for b in approaches]


@router.post("/boundary-approaches", status_code=status.HTTP_201_CREATED)
async def create_approach(
    payload: RefCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.require_role(ctx, ["admin", "platform_admin"])
    b = await _repo(session).create_boundary_approach(code=payload.code, name=payload.name, description=payload.description)
    return {"id": b.id, "code": b.code, "name": b.name}
