from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.db.models.calculation_rule import CalculationRule


class CalculationRuleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> CalculationRule:
        rule = CalculationRule(**kwargs)
        self.session.add(rule)
        await self.session.flush()
        return rule

    async def get_by_id(self, rule_id: int) -> CalculationRule | None:
        result = await self.session.execute(
            select(CalculationRule).where(CalculationRule.id == rule_id)
        )
        return result.scalar_one_or_none()

    async def get_or_raise(self, rule_id: int) -> CalculationRule:
        rule = await self.get_by_id(rule_id)
        if not rule:
            raise AppError("NOT_FOUND", 404, f"Calculation rule {rule_id} not found")
        return rule

    async def list_by_org(
        self, org_id: int, page: int = 1, page_size: int = 50
    ) -> tuple[list[CalculationRule], int]:
        filters = [CalculationRule.organization_id == org_id]
        count_q = select(func.count()).select_from(CalculationRule).where(*filters)
        total = (await self.session.execute(count_q)).scalar_one()
        q = (
            select(CalculationRule)
            .where(*filters)
            .order_by(CalculationRule.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(q)
        return list(result.scalars().all()), total

    async def find_by_input_element(
        self, org_id: int, element_id: int
    ) -> list[CalculationRule]:
        # JSON array contains check — works with PostgreSQL
        result = await self.session.execute(
            select(CalculationRule).where(
                CalculationRule.organization_id == org_id,
                CalculationRule.is_active == True,  # noqa: E712
                CalculationRule.input_element_ids.contains([element_id]),
            )
        )
        return list(result.scalars().all())
