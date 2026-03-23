from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.db.models.company_entity import CompanyEntity, ControlLink, OwnershipLink
from app.db.models.organization import Organization


class EntityRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- Organization ---
    async def create_organization(self, **kwargs) -> Organization:
        org = Organization(**kwargs)
        self.session.add(org)
        await self.session.flush()
        return org

    async def get_organization(self, org_id: int) -> Organization | None:
        result = await self.session.execute(select(Organization).where(Organization.id == org_id))
        return result.scalar_one_or_none()

    # --- Entities ---
    async def get_entity(self, entity_id: int) -> CompanyEntity | None:
        result = await self.session.execute(
            select(CompanyEntity).where(CompanyEntity.id == entity_id)
        )
        return result.scalar_one_or_none()

    async def get_or_raise(self, entity_id: int) -> CompanyEntity:
        e = await self.get_entity(entity_id)
        if not e:
            raise AppError("NOT_FOUND", 404, f"Entity {entity_id} not found")
        return e

    async def list_entities(
        self, org_id: int, page: int = 1, page_size: int = 50
    ) -> tuple[list[CompanyEntity], int]:
        count_q = select(func.count()).select_from(CompanyEntity).where(
            CompanyEntity.organization_id == org_id
        )
        total = (await self.session.execute(count_q)).scalar_one()

        q = (
            select(CompanyEntity)
            .where(CompanyEntity.organization_id == org_id)
            .order_by(CompanyEntity.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(q)
        return list(result.scalars().all()), total

    async def create_entity(self, org_id: int, **kwargs) -> CompanyEntity:
        e = CompanyEntity(organization_id=org_id, **kwargs)
        self.session.add(e)
        await self.session.flush()
        return e

    # --- Ownership ---
    async def create_ownership(self, **kwargs) -> OwnershipLink:
        link = OwnershipLink(**kwargs)
        self.session.add(link)
        await self.session.flush()
        return link

    async def get_ownership_sum(self, child_entity_id: int) -> float:
        q = select(func.coalesce(func.sum(OwnershipLink.ownership_percent), 0)).where(
            OwnershipLink.child_entity_id == child_entity_id
        )
        result = await self.session.execute(q)
        return float(result.scalar_one())

    # --- Control ---
    async def create_control(self, **kwargs) -> ControlLink:
        link = ControlLink(**kwargs)
        self.session.add(link)
        await self.session.flush()
        return link
