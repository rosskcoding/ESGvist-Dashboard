from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.delta import RequirementDelta


class DeltaRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> RequirementDelta:
        delta = RequirementDelta(**kwargs)
        self.session.add(delta)
        await self.session.flush()
        return delta

    async def list(self, *, standard_id: int | None = None) -> list[RequirementDelta]:
        q = select(RequirementDelta)
        if standard_id:
            q = q.where(RequirementDelta.standard_id == standard_id)
        result = await self.session.execute(q)
        return list(result.scalars().all())
