from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.db.models.data_point import DataPoint, DataPointDimension


class DataPointRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, project_id: int, **kwargs) -> DataPoint:
        dp = DataPoint(reporting_project_id=project_id, **kwargs)
        self.session.add(dp)
        await self.session.flush()
        return dp

    async def get_by_id(self, dp_id: int) -> DataPoint | None:
        result = await self.session.execute(select(DataPoint).where(DataPoint.id == dp_id))
        return result.scalar_one_or_none()

    async def get_or_raise(self, dp_id: int) -> DataPoint:
        dp = await self.get_by_id(dp_id)
        if not dp:
            raise AppError("NOT_FOUND", 404, f"Data point {dp_id} not found")
        return dp

    async def list_by_project(
        self, project_id: int, page: int = 1, page_size: int = 50
    ) -> tuple[list[DataPoint], int]:
        count_q = select(func.count()).select_from(DataPoint).where(
            DataPoint.reporting_project_id == project_id
        )
        total = (await self.session.execute(count_q)).scalar_one()

        q = (
            select(DataPoint)
            .where(DataPoint.reporting_project_id == project_id)
            .order_by(DataPoint.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(q)
        return list(result.scalars().all()), total

    async def update(self, dp_id: int, **kwargs) -> DataPoint:
        dp = await self.get_or_raise(dp_id)
        for k, v in kwargs.items():
            setattr(dp, k, v)
        await self.session.flush()
        return dp

    async def add_dimension(self, dp_id: int, dim_type: str, dim_value: str) -> DataPointDimension:
        dim = DataPointDimension(data_point_id=dp_id, dimension_type=dim_type, dimension_value=dim_value)
        self.session.add(dim)
        await self.session.flush()
        return dim
