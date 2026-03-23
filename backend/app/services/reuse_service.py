from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.completeness import RequirementItemDataPoint
from app.db.models.data_point import DataPoint


class ReuseService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_reuse(
        self,
        project_id: int,
        shared_element_id: int,
        unit_code: str | None = None,
        entity_id: int | None = None,
    ) -> list[dict]:
        """Find existing data points that match identity parameters for reuse."""
        q = select(DataPoint).where(
            DataPoint.reporting_project_id == project_id,
            DataPoint.shared_element_id == shared_element_id,
        )
        if unit_code:
            q = q.where(DataPoint.unit_code == unit_code)
        if entity_id:
            q = q.where(DataPoint.entity_id == entity_id)

        result = await self.session.execute(q)
        candidates = result.scalars().all()

        return [
            {
                "data_point_id": dp.id,
                "numeric_value": float(dp.numeric_value) if dp.numeric_value else None,
                "text_value": dp.text_value,
                "unit_code": dp.unit_code,
                "status": dp.status,
                "entity_id": dp.entity_id,
            }
            for dp in candidates
        ]

    async def get_reuse_info(self, data_point_id: int) -> dict:
        """Get reuse info: how many bindings this data point has."""
        q = select(RequirementItemDataPoint).where(
            RequirementItemDataPoint.data_point_id == data_point_id
        )
        result = await self.session.execute(q)
        bindings = list(result.scalars().all())

        return {
            "data_point_id": data_point_id,
            "binding_count": len(bindings),
            "reused_in": [
                {"requirement_item_id": b.requirement_item_id, "project_id": b.reporting_project_id}
                for b in bindings
            ],
        }
