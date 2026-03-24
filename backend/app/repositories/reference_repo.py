from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.unit_reference import BoundaryApproach, Methodology, UnitReference


class ReferenceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_units(self) -> list[UnitReference]:
        result = await self.session.execute(select(UnitReference).order_by(UnitReference.code))
        return list(result.scalars().all())

    async def create_unit(self, **kwargs) -> UnitReference:
        u = UnitReference(**kwargs)
        self.session.add(u)
        await self.session.flush()
        return u

    async def list_methodologies(self) -> list[Methodology]:
        result = await self.session.execute(select(Methodology).order_by(Methodology.code))
        return list(result.scalars().all())

    async def create_methodology(self, **kwargs) -> Methodology:
        m = Methodology(**kwargs)
        self.session.add(m)
        await self.session.flush()
        return m

    async def list_boundary_approaches(self) -> list[BoundaryApproach]:
        result = await self.session.execute(select(BoundaryApproach).order_by(BoundaryApproach.code))
        return list(result.scalars().all())

    async def create_boundary_approach(self, **kwargs) -> BoundaryApproach:
        b = BoundaryApproach(**kwargs)
        self.session.add(b)
        await self.session.flush()
        return b
