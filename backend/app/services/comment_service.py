from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import get_data_point_for_ctx
from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.db.models.comment import Comment
from app.policies.auth_policy import AuthPolicy


class CommentService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        ctx: RequestContext,
        body: str,
        comment_type: str = "general",
        data_point_id: int | None = None,
        requirement_item_id: int | None = None,
        parent_comment_id: int | None = None,
    ) -> dict:
        if ctx.role == "auditor":
            raise AppError("FORBIDDEN", 403, "Auditor has read-only access")
        if data_point_id is not None:
            await get_data_point_for_ctx(self.session, data_point_id, ctx)

        c = Comment(
            user_id=ctx.user_id,
            body=body,
            comment_type=comment_type,
            data_point_id=data_point_id,
            requirement_item_id=requirement_item_id,
            parent_comment_id=parent_comment_id,
        )
        self.session.add(c)
        await self.session.flush()
        return self._to_dict(c)

    async def list_for_data_point(self, dp_id: int, ctx: RequestContext) -> list[dict]:
        await get_data_point_for_ctx(self.session, dp_id, ctx)
        q = select(Comment).where(Comment.data_point_id == dp_id).order_by(Comment.created_at)
        result = await self.session.execute(q)
        comments = list(result.scalars().all())

        # Build threaded structure
        by_id: dict[int, dict] = {}
        roots: list[dict] = []

        for c in comments:
            d = self._to_dict(c)
            d["replies"] = []
            by_id[c.id] = d

        for c in comments:
            d = by_id[c.id]
            if c.parent_comment_id and c.parent_comment_id in by_id:
                by_id[c.parent_comment_id]["replies"].append(d)
            else:
                roots.append(d)

        return roots

    async def resolve(self, comment_id: int, ctx: RequestContext) -> dict:
        result = await self.session.execute(select(Comment).where(Comment.id == comment_id))
        c = result.scalar_one_or_none()
        if not c:
            raise AppError("NOT_FOUND", 404, f"Comment {comment_id} not found")
        if c.data_point_id is not None:
            await get_data_point_for_ctx(self.session, c.data_point_id, ctx)
        if ctx.role == "reviewer" and c.user_id != ctx.user_id:
            raise AppError("FORBIDDEN", 403, "Reviewers can only resolve their own comments")
        if ctx.role == "collector":
            raise AppError("FORBIDDEN", 403, "Collectors cannot resolve comments")
        if ctx.role not in ("reviewer", "admin", "esg_manager", "platform_admin"):
            raise AppError("FORBIDDEN", 403, "You don't have permission to resolve comments")
        c.is_resolved = True
        await self.session.flush()
        return {"id": c.id, "is_resolved": True}

    @staticmethod
    def _to_dict(c: Comment) -> dict:
        return {
            "id": c.id,
            "user_id": c.user_id,
            "body": c.body,
            "comment_type": c.comment_type,
            "data_point_id": c.data_point_id,
            "requirement_item_id": c.requirement_item_id,
            "parent_comment_id": c.parent_comment_id,
            "is_resolved": c.is_resolved,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
