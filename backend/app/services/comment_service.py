from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import get_data_point_for_ctx
from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.db.models.comment import Comment
from app.db.models.completeness import RequirementItemStatus
from app.db.models.data_point import DataPoint
from app.db.models.mapping import RequirementItemSharedElement
from app.db.models.project import ReportingProject
from app.db.models.requirement_item import RequirementItem
from app.db.models.user import User


class CommentService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _validate_requirement_item_access(
        self,
        requirement_item_id: int,
        ctx: RequestContext,
        *,
        data_point_id: int | None,
    ) -> None:
        """Validate item existence and, when scoped to a data point, project/mapping context."""
        if data_point_id is None:
            raise AppError(
                "COMMENT_SCOPE_UNSUPPORTED",
                422,
                "Requirement item comments require a data point context",
            )

        result = await self.session.execute(
            select(RequirementItem.id)
            .join(
                RequirementItemSharedElement,
                RequirementItemSharedElement.requirement_item_id == RequirementItem.id,
            )
            .join(
                DataPoint,
                DataPoint.id == data_point_id,
            )
            .join(
                RequirementItemStatus,
                RequirementItemStatus.requirement_item_id == RequirementItem.id,
            )
            .where(
                RequirementItem.id == requirement_item_id,
                RequirementItemSharedElement.is_current.is_(True),
                RequirementItemSharedElement.shared_element_id == DataPoint.shared_element_id,
                RequirementItemStatus.reporting_project_id == DataPoint.reporting_project_id,
            )
            .limit(1)
        )
        item_id = result.scalars().first()
        if not item_id:
            existing_item = await self.session.execute(
                select(RequirementItem.id).where(RequirementItem.id == requirement_item_id)
            )
            if existing_item.scalars().first() is None:
                raise AppError(
                    "NOT_FOUND",
                    404,
                    f"Requirement item {requirement_item_id} not found",
                )
            raise AppError(
                "INVALID_REQUIREMENT_ITEM_CONTEXT",
                422,
                "Requirement item is not valid for this data point context",
            )

    async def _validate_legacy_requirement_item_comment_access(
        self,
        requirement_item_id: int,
        ctx: RequestContext,
    ) -> None:
        """Allow resolving legacy requirement-item-only comments within the current org."""
        if ctx.organization_id is None:
            raise AppError(
                "COMMENT_SCOPE_UNSUPPORTED",
                422,
                "Requirement item comments require an organization context",
            )

        result = await self.session.execute(
            select(RequirementItem.id)
            .join(
                RequirementItemStatus,
                RequirementItemStatus.requirement_item_id == RequirementItem.id,
            )
            .join(
                ReportingProject,
                ReportingProject.id == RequirementItemStatus.reporting_project_id,
            )
            .where(
                RequirementItem.id == requirement_item_id,
                ReportingProject.organization_id == ctx.organization_id,
            )
            .limit(1)
        )
        item_id = result.scalars().first()
        if item_id is not None:
            return

        existing_item = await self.session.execute(
            select(RequirementItem.id).where(RequirementItem.id == requirement_item_id)
        )
        if existing_item.scalars().first() is None:
            raise AppError(
                "NOT_FOUND",
                404,
                f"Requirement item {requirement_item_id} not found",
            )
        raise AppError(
            "INVALID_REQUIREMENT_ITEM_CONTEXT",
            422,
            "Requirement item is not valid for the current organization context",
        )

    async def _validate_parent_comment(
        self,
        parent_comment_id: int,
        *,
        data_point_id: int | None,
        requirement_item_id: int | None,
        ctx: RequestContext,
    ) -> Comment:
        """Validate parent comment exists, is accessible, and context matches."""
        result = await self.session.execute(
            select(Comment).where(Comment.id == parent_comment_id)
        )
        parent = result.scalar_one_or_none()
        if not parent:
            raise AppError("NOT_FOUND", 404, f"Parent comment {parent_comment_id} not found")

        # Parent must have same object binding
        if parent.data_point_id != data_point_id:
            raise AppError(
                "INVALID_PARENT_COMMENT", 422,
                "Reply must be on the same data point as the parent comment"
            )
        if parent.requirement_item_id != requirement_item_id:
            raise AppError(
                "INVALID_PARENT_COMMENT", 422,
                "Reply must be on the same requirement item as the parent comment"
            )

        # Validate access to parent's object
        if parent.data_point_id is not None:
            await get_data_point_for_ctx(self.session, parent.data_point_id, ctx)

        return parent

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

        # Must be bound to at least one object
        if data_point_id is None and requirement_item_id is None and parent_comment_id is None:
            raise AppError(
                "INVALID_COMMENT", 422,
                "Comment must be linked to a data point, requirement item, or parent comment"
            )
        if data_point_id is None and requirement_item_id is not None:
            raise AppError(
                "COMMENT_SCOPE_UNSUPPORTED",
                422,
                "Requirement item-only comments are not supported without a data point context",
            )

        # Validate object-level access
        if data_point_id is not None:
            await get_data_point_for_ctx(self.session, data_point_id, ctx)

        if requirement_item_id is not None:
            await self._validate_requirement_item_access(
                requirement_item_id,
                ctx,
                data_point_id=data_point_id,
            )

        # Validate parent comment consistency
        if parent_comment_id is not None:
            await self._validate_parent_comment(
                parent_comment_id,
                data_point_id=data_point_id,
                requirement_item_id=requirement_item_id,
                ctx=ctx,
            )

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

        user_ids = list({comment.user_id for comment in comments if comment.user_id is not None})
        user_names: dict[int, str] = {}
        if user_ids:
            user_result = await self.session.execute(
                select(User.id, User.full_name).where(User.id.in_(user_ids))
            )
            user_names = {user_id: full_name for user_id, full_name in user_result.all()}

        # Build threaded structure
        by_id: dict[int, dict] = {}
        roots: list[dict] = []

        for c in comments:
            d = self._to_dict(c, user_names.get(c.user_id))
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

        # Object-level access check for ALL comments, not just data-point ones
        if c.data_point_id is not None:
            await get_data_point_for_ctx(self.session, c.data_point_id, ctx)
        elif c.requirement_item_id is not None:
            if c.data_point_id is None:
                if ctx.role == "reviewer":
                    raise AppError(
                        "COMMENT_SCOPE_UNSUPPORTED",
                        422,
                        (
                            "Legacy requirement item comments can only be resolved by "
                            "organization managers"
                        ),
                    )
                await self._validate_legacy_requirement_item_comment_access(
                    c.requirement_item_id,
                    ctx,
                )
            else:
                await self._validate_requirement_item_access(
                    c.requirement_item_id,
                    ctx,
                    data_point_id=c.data_point_id,
                )

        if ctx.role == "collector":
            raise AppError("FORBIDDEN", 403, "Collectors cannot resolve comments")
        if ctx.role not in ("reviewer", "admin", "esg_manager", "platform_admin"):
            raise AppError("FORBIDDEN", 403, "You don't have permission to resolve comments")
        c.is_resolved = True
        await self.session.flush()
        return {"id": c.id, "is_resolved": True}

    @staticmethod
    def _to_dict(c: Comment, author_name: str | None = None) -> dict:
        return {
            "id": c.id,
            "user_id": c.user_id,
            "author_name": author_name,
            "body": c.body,
            "content": c.body,
            "comment_type": c.comment_type,
            "type": c.comment_type,
            "data_point_id": c.data_point_id,
            "requirement_item_id": c.requirement_item_id,
            "parent_comment_id": c.parent_comment_id,
            "parent_id": c.parent_comment_id,
            "is_resolved": c.is_resolved,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
