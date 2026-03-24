from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.repositories.delta_repo import DeltaRepository
from app.services.delta_service import DeltaService

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


def _get_service(session: AsyncSession) -> DeltaService:
    return DeltaService(repo=DeltaRepository(session))


@router.post("", response_model=DeltaOut, status_code=status.HTTP_201_CREATED)
async def create_delta(
    payload: DeltaCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    delta = await _get_service(session).create(payload.model_dump(), ctx)
    return DeltaOut.model_validate(delta)


@router.get("", response_model=list[DeltaOut])
async def list_deltas(
    standard_id: int | None = None,
    session: AsyncSession = Depends(get_session),
):
    deltas = await _get_service(session).list(standard_id=standard_id)
    return [DeltaOut.model_validate(d) for d in deltas]
