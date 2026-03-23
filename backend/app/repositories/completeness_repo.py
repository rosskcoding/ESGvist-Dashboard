from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.completeness import (
    DisclosureRequirementStatus,
    RequirementItemDataPoint,
    RequirementItemStatus,
)
from app.db.models.data_point import DataPoint
from app.db.models.evidence import DataPointEvidence
from app.db.models.requirement_item import RequirementItem
from app.db.models.project import ReportingProjectStandard
from app.db.models.standard import DisclosureRequirement, Standard


class CompletenessRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- Bindings ---
    async def create_binding(
        self, project_id: int, item_id: int, dp_id: int, binding_type: str = "direct"
    ) -> RequirementItemDataPoint:
        b = RequirementItemDataPoint(
            reporting_project_id=project_id,
            requirement_item_id=item_id,
            data_point_id=dp_id,
            binding_type=binding_type,
        )
        self.session.add(b)
        await self.session.flush()
        return b

    async def get_bindings(self, project_id: int, item_id: int) -> list[RequirementItemDataPoint]:
        q = select(RequirementItemDataPoint).where(
            RequirementItemDataPoint.reporting_project_id == project_id,
            RequirementItemDataPoint.requirement_item_id == item_id,
        )
        result = await self.session.execute(q)
        return list(result.scalars().all())

    # --- Data points by binding ---
    async def get_bound_data_points(self, project_id: int, item_id: int) -> list[DataPoint]:
        q = (
            select(DataPoint)
            .join(RequirementItemDataPoint, RequirementItemDataPoint.data_point_id == DataPoint.id)
            .where(
                RequirementItemDataPoint.reporting_project_id == project_id,
                RequirementItemDataPoint.requirement_item_id == item_id,
            )
        )
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def get_bound_data_points_for_items(
        self, project_id: int, item_ids: list[int]
    ) -> dict[int, list[DataPoint]]:
        if not item_ids:
            return {}

        q = (
            select(RequirementItemDataPoint.requirement_item_id, DataPoint)
            .join(DataPoint, RequirementItemDataPoint.data_point_id == DataPoint.id)
            .where(
                RequirementItemDataPoint.reporting_project_id == project_id,
                RequirementItemDataPoint.requirement_item_id.in_(item_ids),
            )
        )
        result = await self.session.execute(q)
        grouped: dict[int, list[DataPoint]] = {}
        for item_id, data_point in result.all():
            grouped.setdefault(item_id, []).append(data_point)
        return grouped

    # --- Evidence count ---
    async def count_evidence_for_dp(self, dp_id: int) -> int:
        q = select(func.count()).select_from(DataPointEvidence).where(
            DataPointEvidence.data_point_id == dp_id
        )
        return (await self.session.execute(q)).scalar_one()

    # --- Item status ---
    async def upsert_item_status(
        self, project_id: int, item_id: int, status: str, reason: str | None = None
    ) -> RequirementItemStatus:
        existing = await self.session.execute(
            select(RequirementItemStatus).where(
                RequirementItemStatus.reporting_project_id == project_id,
                RequirementItemStatus.requirement_item_id == item_id,
            )
        )
        s = existing.scalar_one_or_none()
        if s:
            s.status = status
            s.status_reason = reason
        else:
            s = RequirementItemStatus(
                reporting_project_id=project_id,
                requirement_item_id=item_id,
                status=status,
                status_reason=reason,
            )
            self.session.add(s)
        await self.session.flush()
        return s

    async def get_item_status(self, project_id: int, item_id: int) -> RequirementItemStatus | None:
        q = select(RequirementItemStatus).where(
            RequirementItemStatus.reporting_project_id == project_id,
            RequirementItemStatus.requirement_item_id == item_id,
        )
        result = await self.session.execute(q)
        return result.scalar_one_or_none()

    # --- Disclosure status ---
    async def upsert_disclosure_status(
        self, project_id: int, disclosure_id: int, status: str, completion_percent: float
    ) -> DisclosureRequirementStatus:
        existing = await self.session.execute(
            select(DisclosureRequirementStatus).where(
                DisclosureRequirementStatus.reporting_project_id == project_id,
                DisclosureRequirementStatus.disclosure_requirement_id == disclosure_id,
            )
        )
        s = existing.scalar_one_or_none()
        if s:
            s.status = status
            s.completion_percent = completion_percent
        else:
            s = DisclosureRequirementStatus(
                reporting_project_id=project_id,
                disclosure_requirement_id=disclosure_id,
                status=status,
                completion_percent=completion_percent,
            )
            self.session.add(s)
        await self.session.flush()
        return s

    # --- Items by disclosure ---
    async def get_required_items(self, disclosure_id: int) -> list[RequirementItem]:
        q = select(RequirementItem).where(
            RequirementItem.disclosure_requirement_id == disclosure_id,
            RequirementItem.is_required == True,
        )
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def list_project_items(
        self, project_id: int, standard_id: int | None = None
    ) -> list[tuple[RequirementItem, DisclosureRequirement]]:
        q = (
            select(RequirementItem, DisclosureRequirement)
            .join(
                DisclosureRequirement,
                DisclosureRequirement.id == RequirementItem.disclosure_requirement_id,
            )
            .join(
                ReportingProjectStandard,
                ReportingProjectStandard.standard_id == DisclosureRequirement.standard_id,
            )
            .where(
                ReportingProjectStandard.reporting_project_id == project_id,
                RequirementItem.is_required == True,
            )
            .order_by(DisclosureRequirement.id, RequirementItem.sort_order, RequirementItem.id)
        )
        if standard_id is not None:
            q = q.where(DisclosureRequirement.standard_id == standard_id)
        result = await self.session.execute(q)
        return [(row[0], row[1]) for row in result.all()]

    async def list_project_item_statuses(
        self, project_id: int, item_ids: list[int]
    ) -> list[RequirementItemStatus]:
        if not item_ids:
            return []
        q = select(RequirementItemStatus).where(
            RequirementItemStatus.reporting_project_id == project_id,
            RequirementItemStatus.requirement_item_id.in_(item_ids),
        )
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def list_project_disclosure_statuses(
        self, project_id: int, standard_id: int | None = None
    ) -> list[tuple[DisclosureRequirementStatus, DisclosureRequirement]]:
        q = (
            select(DisclosureRequirementStatus, DisclosureRequirement)
            .join(
                DisclosureRequirement,
                DisclosureRequirement.id == DisclosureRequirementStatus.disclosure_requirement_id,
            )
            .join(
                ReportingProjectStandard,
                ReportingProjectStandard.standard_id == DisclosureRequirement.standard_id,
            )
            .where(DisclosureRequirementStatus.reporting_project_id == project_id)
            .order_by(DisclosureRequirement.id)
        )
        if standard_id is not None:
            q = q.where(DisclosureRequirement.standard_id == standard_id)
        result = await self.session.execute(q)
        return [(row[0], row[1]) for row in result.all()]

    async def list_project_standards(self, project_id: int) -> list[tuple[int, str, str]]:
        q = (
            select(Standard.id, Standard.code, Standard.name)
            .join(ReportingProjectStandard, ReportingProjectStandard.standard_id == Standard.id)
            .where(ReportingProjectStandard.reporting_project_id == project_id)
            .order_by(Standard.id)
        )
        result = await self.session.execute(q)
        return [(row[0], row[1], row[2]) for row in result.all()]
