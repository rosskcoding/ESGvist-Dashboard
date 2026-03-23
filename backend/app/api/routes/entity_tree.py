from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.services.entity_tree_service import EntityTreeService

router = APIRouter(tags=["Entity Tree"])


@router.get("/api/entities/tree")
async def get_entity_tree(
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    service = EntityTreeService(session)
    return await service.get_tree(ctx.organization_id)


@router.get("/api/entities/{entity_id}/effective-ownership")
async def get_effective_ownership(
    entity_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    service = EntityTreeService(session)
    return await service.calculate_effective_ownership(ctx.organization_id, entity_id)
