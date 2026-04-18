from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.domain.catalog import prepare_shared_element_defaults
from app.db.models.shared_element import SharedElement, SharedElementDimension


class SharedElementRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, element_id: int) -> SharedElement | None:
        result = await self.session.execute(
            select(SharedElement).where(SharedElement.id == element_id)
        )
        return result.scalar_one_or_none()

    async def get_by_code(
        self,
        code: str,
        *,
        owner_layer: str | None = None,
        organization_id: int | None = None,
    ) -> SharedElement | None:
        query = select(SharedElement).where(SharedElement.code == code)
        if owner_layer is not None:
            query = query.where(SharedElement.owner_layer == owner_layer)
        if organization_id is not None:
            query = query.where(SharedElement.organization_id == organization_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_or_raise(self, element_id: int) -> SharedElement:
        el = await self.get_by_id(element_id)
        if not el:
            raise AppError("NOT_FOUND", 404, f"Shared element {element_id} not found")
        return el

    async def list_elements(
        self, page: int = 1, page_size: int = 50
    ) -> tuple[list[SharedElement], int]:
        count_q = select(func.count()).select_from(SharedElement)
        total = (await self.session.execute(count_q)).scalar_one()

        q = (
            select(SharedElement)
            .order_by(desc(SharedElement.id))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(q)
        return list(result.scalars().unique().all()), total

    async def create(self, **kwargs) -> SharedElement:
        if "element_key" not in kwargs:
            kwargs.update(
                prepare_shared_element_defaults(
                    code=kwargs["code"],
                    owner_layer=kwargs.get("owner_layer", "internal_catalog"),
                    organization_id=kwargs.get("organization_id"),
                    is_custom=kwargs.get("is_custom"),
                    lifecycle_status=kwargs.get("lifecycle_status", "active"),
                    source_element_key=kwargs.get("source_element_key"),
                )
            )
        el = SharedElement(**kwargs)
        self.session.add(el)
        await self.session.flush()
        return el

    async def create_dimension(self, element_id: int, **kwargs) -> SharedElementDimension:
        dim = SharedElementDimension(shared_element_id=element_id, **kwargs)
        self.session.add(dim)
        await self.session.flush()
        return dim

    async def list_dimensions(self, element_id: int) -> list[SharedElementDimension]:
        q = select(SharedElementDimension).where(
            SharedElementDimension.shared_element_id == element_id
        )
        result = await self.session.execute(q)
        return list(result.scalars().all())
