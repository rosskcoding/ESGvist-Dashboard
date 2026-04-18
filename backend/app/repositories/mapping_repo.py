from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.db.models.mapping import RequirementItemSharedElement
from app.db.models.requirement_item import RequirementItem
from app.db.models.shared_element import SharedElement
from app.db.models.standard import DisclosureRequirement


class MappingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> RequirementItemSharedElement:
        m = RequirementItemSharedElement(**kwargs)
        self.session.add(m)
        await self.session.flush()
        return m

    async def get_by_item_and_element(
        self,
        item_id: int,
        element_id: int,
        current_only: bool = True,
        for_update: bool = False,
    ) -> RequirementItemSharedElement | None:
        q = select(RequirementItemSharedElement).where(
            RequirementItemSharedElement.requirement_item_id == item_id,
            RequirementItemSharedElement.shared_element_id == element_id,
        )
        if current_only:
            q = q.where(RequirementItemSharedElement.is_current == True)  # noqa: E712
        q = q.order_by(RequirementItemSharedElement.version.desc(), RequirementItemSharedElement.id.desc())
        if for_update:
            q = q.with_for_update()
        if current_only:
            q = q.limit(2)
        result = await self.session.execute(q)
        items = list(result.scalars().all())
        return items[0] if items else None

    async def list_versions(
        self, item_id: int, element_id: int,
    ) -> list[RequirementItemSharedElement]:
        q = (
            select(RequirementItemSharedElement)
            .where(
                RequirementItemSharedElement.requirement_item_id == item_id,
                RequirementItemSharedElement.shared_element_id == element_id,
            )
            .order_by(RequirementItemSharedElement.version.desc())
        )
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def get_version(
        self, item_id: int, element_id: int, version: int,
    ) -> RequirementItemSharedElement | None:
        q = select(RequirementItemSharedElement).where(
            RequirementItemSharedElement.requirement_item_id == item_id,
            RequirementItemSharedElement.shared_element_id == element_id,
            RequirementItemSharedElement.version == version,
        )
        result = await self.session.execute(q)
        return result.scalar_one_or_none()

    async def list_all(
        self, page: int = 1, page_size: int = 50
    ) -> tuple[list[RequirementItemSharedElement], int]:
        count_q = select(func.count()).select_from(RequirementItemSharedElement)
        total = (await self.session.execute(count_q)).scalar_one()

        q = (
            select(RequirementItemSharedElement)
            .order_by(RequirementItemSharedElement.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(q)
        return list(result.scalars().all()), total

    async def get_cross_standard_elements(self) -> list[dict]:
        """Find shared elements mapped to items from 2+ different standards."""
        q = (
            select(
                SharedElement.id,
                SharedElement.code,
                SharedElement.name,
                func.count(RequirementItemSharedElement.id).label("mapping_count"),
                func.count(func.distinct(DisclosureRequirement.standard_id)).label("std_count"),
            )
            .join(
                RequirementItemSharedElement,
                RequirementItemSharedElement.shared_element_id == SharedElement.id,
            )
            .join(
                RequirementItem,
                RequirementItem.id == RequirementItemSharedElement.requirement_item_id,
            )
            .join(
                DisclosureRequirement,
                DisclosureRequirement.id == RequirementItem.disclosure_requirement_id,
            )
            .where(
                RequirementItemSharedElement.is_current == True,  # noqa: E712
                RequirementItem.is_current == True,  # noqa: E712
                SharedElement.is_current == True,  # noqa: E712
            )
            .group_by(SharedElement.id, SharedElement.code, SharedElement.name)
            .having(func.count(func.distinct(DisclosureRequirement.standard_id)) > 1)
        )
        result = await self.session.execute(q)
        rows = result.all()

        # For each, get the standard codes
        elements = []
        for row in rows:
            std_q = (
                select(func.distinct(DisclosureRequirement.standard_id))
                .join(RequirementItem)
                .join(RequirementItemSharedElement)
                .where(
                    RequirementItemSharedElement.shared_element_id == row.id,
                    RequirementItemSharedElement.is_current == True,  # noqa: E712
                    RequirementItem.is_current == True,  # noqa: E712
                )
            )
            std_result = await self.session.execute(std_q)
            std_ids = [r[0] for r in std_result.all()]

            from app.db.models.standard import Standard

            std_names_q = select(Standard.code).where(Standard.id.in_(std_ids))
            std_names_result = await self.session.execute(std_names_q)
            std_codes = [r[0] for r in std_names_result.all()]

            elements.append({
                "shared_element_id": row.id,
                "shared_element_code": row.code,
                "shared_element_name": row.name,
                "standards": std_codes,
                "mapping_count": row.mapping_count,
            })

        return elements
