from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.db.models.requirement_item import RequirementItem, RequirementItemDependency


class RequirementItemRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, item_id: int) -> RequirementItem | None:
        result = await self.session.execute(
            select(RequirementItem).where(RequirementItem.id == item_id)
        )
        return result.scalar_one_or_none()

    async def get_or_raise(self, item_id: int) -> RequirementItem:
        item = await self.get_by_id(item_id)
        if not item:
            raise AppError("NOT_FOUND", 404, f"Requirement item {item_id} not found")
        return item

    async def list_by_disclosure(
        self, disclosure_id: int, page: int = 1, page_size: int = 50
    ) -> tuple[list[RequirementItem], int]:
        count_q = select(func.count()).select_from(RequirementItem).where(
            RequirementItem.disclosure_requirement_id == disclosure_id
        )
        total = (await self.session.execute(count_q)).scalar_one()

        q = (
            select(RequirementItem)
            .where(RequirementItem.disclosure_requirement_id == disclosure_id)
            .order_by(RequirementItem.sort_order)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(q)
        return list(result.scalars().all()), total

    async def create(self, disclosure_id: int, **kwargs) -> RequirementItem:
        item = RequirementItem(disclosure_requirement_id=disclosure_id, **kwargs)
        self.session.add(item)
        await self.session.flush()
        return item

    # --- Dependencies ---
    async def list_dependencies(self, item_id: int) -> list[RequirementItemDependency]:
        q = select(RequirementItemDependency).where(
            RequirementItemDependency.requirement_item_id == item_id
        )
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def create_dependency(self, item_id: int, **kwargs) -> RequirementItemDependency:
        dep = RequirementItemDependency(requirement_item_id=item_id, **kwargs)
        self.session.add(dep)
        await self.session.flush()
        return dep
