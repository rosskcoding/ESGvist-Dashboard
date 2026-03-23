from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.core.exceptions import AppError
from app.db.models.delta import RequirementDelta
from app.db.session import get_session

router = APIRouter(prefix="/api/deltas", tags=["Deltas"])


class DeltaCreate(BaseModel):
    requirement_item_id: int
    standard_id: int
    delta_type: str = Field(
        pattern=r"^(additional_item|extra_dimension|stricter_validation|extra_narrative|extra_document)$"
    )
    description: str | None = None
    condition: dict | None = None


class DeltaOut(BaseModel):
    id: int
    requirement_item_id: int
    standard_id: int
    delta_type: str
    description: str | None
    condition: dict | None

    model_config = {"from_attributes": True}


@router.post("", response_model=DeltaOut, status_code=status.HTTP_201_CREATED)
async def create_delta(
    payload: DeltaCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    if ctx.role not in ("admin", "platform_admin"):
        raise AppError("FORBIDDEN", 403, "Only admin can create deltas")

    delta = RequirementDelta(**payload.model_dump())
    session.add(delta)
    await session.flush()
    return DeltaOut.model_validate(delta)


@router.get("", response_model=list[DeltaOut])
async def list_deltas(
    standard_id: int | None = None,
    session: AsyncSession = Depends(get_session),
):
    q = select(RequirementDelta)
    if standard_id:
        q = q.where(RequirementDelta.standard_id == standard_id)
    result = await session.execute(q)
    return [DeltaOut.model_validate(d) for d in result.scalars().all()]
