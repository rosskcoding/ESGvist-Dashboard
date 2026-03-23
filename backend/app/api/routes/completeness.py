from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.repositories.completeness_repo import CompletenessRepository
from app.schemas.completeness import BindRequest
from app.services.completeness_service import CompletenessService

router = APIRouter(tags=["Completeness"])


def _get_service(session: AsyncSession) -> CompletenessService:
    return CompletenessService(repo=CompletenessRepository(session))


@router.post("/api/projects/{project_id}/bindings", status_code=status.HTTP_201_CREATED)
async def bind_data_point(
    project_id: int,
    payload: BindRequest,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    service = _get_service(session)
    return await service.bind_data_point(
        project_id, payload.requirement_item_id, payload.data_point_id
    )


@router.get("/api/projects/{project_id}/completeness/items/{item_id}")
async def get_item_status(
    project_id: int,
    item_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    service = _get_service(session)
    status_val = await service.calculate_item_status(project_id, item_id)
    return {"requirement_item_id": item_id, "status": status_val}


@router.get("/api/projects/{project_id}/completeness/disclosures/{disclosure_id}")
async def get_disclosure_status(
    project_id: int,
    disclosure_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    service = _get_service(session)
    return await service.aggregate_disclosure_status(project_id, disclosure_id)
