from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.db.models.evidence import DataPointEvidence, Evidence, EvidenceFile, EvidenceLink
from app.db.models.requirement_item_evidence import RequirementItemEvidence


class EvidenceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, org_id: int, **kwargs) -> Evidence:
        ev = Evidence(organization_id=org_id, **kwargs)
        self.session.add(ev)
        await self.session.flush()
        return ev

    async def get_by_id(self, ev_id: int) -> Evidence | None:
        result = await self.session.execute(select(Evidence).where(Evidence.id == ev_id))
        return result.scalar_one_or_none()

    async def get_or_raise(self, ev_id: int) -> Evidence:
        ev = await self.get_by_id(ev_id)
        if not ev:
            raise AppError("EVIDENCE_NOT_FOUND", 404, f"Evidence {ev_id} not found")
        return ev

    async def list_by_org(
        self,
        org_id: int,
        page: int = 1,
        page_size: int = 50,
        created_by: int | None = None,
    ) -> tuple[list[Evidence], int]:
        filters = [Evidence.organization_id == org_id]
        if created_by is not None:
            filters.append(Evidence.created_by == created_by)

        count_q = select(func.count()).select_from(Evidence).where(*filters)
        total = (await self.session.execute(count_q)).scalar_one()

        q = (
            select(Evidence)
            .where(*filters)
            .order_by(Evidence.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(q)
        return list(result.scalars().all()), total

    async def create_file(self, evidence_id: int, **kwargs) -> EvidenceFile:
        f = EvidenceFile(evidence_id=evidence_id, **kwargs)
        self.session.add(f)
        await self.session.flush()
        return f

    async def create_link(self, evidence_id: int, **kwargs) -> EvidenceLink:
        l = EvidenceLink(evidence_id=evidence_id, **kwargs)
        self.session.add(l)
        await self.session.flush()
        return l

    async def link_to_data_point(self, dp_id: int, ev_id: int, user_id: int | None) -> DataPointEvidence:
        dpe = DataPointEvidence(data_point_id=dp_id, evidence_id=ev_id, linked_by=user_id)
        self.session.add(dpe)
        await self.session.flush()
        return dpe

    async def count_for_data_point(self, dp_id: int) -> int:
        q = select(func.count()).select_from(DataPointEvidence).where(
            DataPointEvidence.data_point_id == dp_id
        )
        return (await self.session.execute(q)).scalar_one()

    async def requirement_item_link_exists(self, requirement_item_id: int, evidence_id: int) -> bool:
        result = await self.session.execute(
            select(RequirementItemEvidence).where(
                RequirementItemEvidence.requirement_item_id == requirement_item_id,
                RequirementItemEvidence.evidence_id == evidence_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def link_to_requirement_item(
        self, requirement_item_id: int, evidence_id: int, user_id: int
    ) -> RequirementItemEvidence:
        binding = RequirementItemEvidence(
            requirement_item_id=requirement_item_id,
            evidence_id=evidence_id,
            linked_by=user_id,
        )
        self.session.add(binding)
        await self.session.flush()
        return binding
