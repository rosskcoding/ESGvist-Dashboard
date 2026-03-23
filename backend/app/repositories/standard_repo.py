from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.db.models.standard import DisclosureRequirement, Standard, StandardSection


class StandardRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- Standard ---
    async def get_by_id(self, standard_id: int) -> Standard | None:
        result = await self.session.execute(select(Standard).where(Standard.id == standard_id))
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Standard | None:
        result = await self.session.execute(select(Standard).where(Standard.code == code))
        return result.scalar_one_or_none()

    async def get_or_raise(self, standard_id: int) -> Standard:
        s = await self.get_by_id(standard_id)
        if not s:
            raise AppError("NOT_FOUND", 404, f"Standard {standard_id} not found")
        return s

    async def list_standards(self, page: int = 1, page_size: int = 20) -> tuple[list[Standard], int]:
        count_q = select(func.count()).select_from(Standard)
        total = (await self.session.execute(count_q)).scalar_one()

        q = select(Standard).order_by(Standard.id).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(q)
        return list(result.scalars().all()), total

    async def create_standard(self, **kwargs) -> Standard:
        s = Standard(**kwargs)
        self.session.add(s)
        await self.session.flush()
        return s

    async def update_standard(self, standard_id: int, **kwargs) -> Standard:
        s = await self.get_or_raise(standard_id)
        for key, value in kwargs.items():
            if value is not None:
                setattr(s, key, value)
        await self.session.flush()
        return s

    async def has_disclosures(self, standard_id: int) -> bool:
        q = select(func.count()).select_from(DisclosureRequirement).where(
            DisclosureRequirement.standard_id == standard_id
        )
        return (await self.session.execute(q)).scalar_one() > 0

    # --- Sections ---
    async def list_sections(self, standard_id: int) -> list[StandardSection]:
        q = (
            select(StandardSection)
            .where(StandardSection.standard_id == standard_id)
            .order_by(StandardSection.sort_order)
        )
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def create_section(self, standard_id: int, **kwargs) -> StandardSection:
        s = StandardSection(standard_id=standard_id, **kwargs)
        self.session.add(s)
        await self.session.flush()
        return s

    # --- Disclosures ---
    async def list_disclosures(
        self, standard_id: int, page: int = 1, page_size: int = 50
    ) -> tuple[list[DisclosureRequirement], int]:
        count_q = select(func.count()).select_from(DisclosureRequirement).where(
            DisclosureRequirement.standard_id == standard_id
        )
        total = (await self.session.execute(count_q)).scalar_one()

        q = (
            select(DisclosureRequirement)
            .where(DisclosureRequirement.standard_id == standard_id)
            .order_by(DisclosureRequirement.sort_order)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(q)
        return list(result.scalars().all()), total

    async def get_disclosure_by_code(self, standard_id: int, code: str) -> DisclosureRequirement | None:
        q = select(DisclosureRequirement).where(
            DisclosureRequirement.standard_id == standard_id,
            DisclosureRequirement.code == code,
        )
        result = await self.session.execute(q)
        return result.scalar_one_or_none()

    async def create_disclosure(self, standard_id: int, **kwargs) -> DisclosureRequirement:
        d = DisclosureRequirement(standard_id=standard_id, **kwargs)
        self.session.add(d)
        await self.session.flush()
        return d
