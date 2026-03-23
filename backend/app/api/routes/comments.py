from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser, RequestContext, get_current_context, get_current_user
from app.db.session import get_session
from app.services.comment_service import CommentService

router = APIRouter(prefix="/api/comments", tags=["Comments"])


class CommentCreate(BaseModel):
    body: str = Field(min_length=1)
    comment_type: str = "general"
    data_point_id: int | None = None
    requirement_item_id: int | None = None
    parent_comment_id: int | None = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_comment(
    payload: CommentCreate,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    service = CommentService(session)
    return await service.create(
        user_id=user.id,
        body=payload.body,
        comment_type=payload.comment_type,
        data_point_id=payload.data_point_id,
        requirement_item_id=payload.requirement_item_id,
        parent_comment_id=payload.parent_comment_id,
    )


@router.get("/data-point/{dp_id}")
async def list_comments(dp_id: int, ctx: RequestContext = Depends(get_current_context), session: AsyncSession = Depends(get_session)):
    service = CommentService(session)
    return await service.list_for_data_point(dp_id)


@router.patch("/{comment_id}/resolve")
async def resolve_comment(comment_id: int, session: AsyncSession = Depends(get_session)):
    service = CommentService(session)
    return await service.resolve(comment_id)
