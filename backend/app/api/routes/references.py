from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.models.unit_reference import BoundaryApproach, Methodology, UnitReference
from app.db.session import get_session

router = APIRouter(prefix="/api/references", tags=["References"])


class RefCreate(BaseModel):
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    category: str | None = None
    description: str | None = None


@router.get("/units")
async def list_units(ctx: RequestContext = Depends(get_current_context), session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(UnitReference).order_by(UnitReference.code))
    return [{"id": u.id, "code": u.code, "name": u.name, "category": u.category} for u in result.scalars().all()]


@router.post("/units", status_code=status.HTTP_201_CREATED)
async def create_unit(payload: RefCreate, session: AsyncSession = Depends(get_session)):
    u = UnitReference(code=payload.code, name=payload.name, category=payload.category)
    session.add(u)
    await session.flush()
    return {"id": u.id, "code": u.code, "name": u.name}


@router.get("/methodologies")
async def list_methodologies(ctx: RequestContext = Depends(get_current_context), session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Methodology).order_by(Methodology.code))
    return [{"id": m.id, "code": m.code, "name": m.name, "description": m.description} for m in result.scalars().all()]


@router.post("/methodologies", status_code=status.HTTP_201_CREATED)
async def create_methodology(payload: RefCreate, session: AsyncSession = Depends(get_session)):
    m = Methodology(code=payload.code, name=payload.name, description=payload.description)
    session.add(m)
    await session.flush()
    return {"id": m.id, "code": m.code, "name": m.name}


@router.get("/boundary-approaches")
async def list_approaches(ctx: RequestContext = Depends(get_current_context), session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(BoundaryApproach).order_by(BoundaryApproach.code))
    return [{"id": b.id, "code": b.code, "name": b.name} for b in result.scalars().all()]


@router.post("/boundary-approaches", status_code=status.HTTP_201_CREATED)
async def create_approach(payload: RefCreate, session: AsyncSession = Depends(get_session)):
    b = BoundaryApproach(code=payload.code, name=payload.name, description=payload.description)
    session.add(b)
    await session.flush()
    return {"id": b.id, "code": b.code, "name": b.name}
