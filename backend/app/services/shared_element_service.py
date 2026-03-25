from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.db.models.shared_element import SharedElement
from app.policies.standard_policy import StandardPolicy
from app.repositories.shared_element_repo import SharedElementRepository
from app.schemas.shared_elements import (
    DimensionCreate,
    DimensionOut,
    SharedElementCreate,
    SharedElementListOut,
    SharedElementOut,
)


class SharedElementService:
    def __init__(self, repo: SharedElementRepository, policy: StandardPolicy):
        self.repo = repo
        self.policy = policy

    async def _to_out(self, el: SharedElement) -> SharedElementOut:
        dims = await self.repo.list_dimensions(el.id)
        return SharedElementOut(
            id=el.id,
            code=el.code,
            name=el.name,
            description=el.description,
            concept_domain=el.concept_domain,
            default_value_type=el.default_value_type,
            default_unit_code=el.default_unit_code,
            dimensions=[DimensionOut.model_validate(d) for d in dims],
        )

    async def list_elements(
        self,
        page: int = 1,
        page_size: int = 50,
        ctx: RequestContext | None = None,
    ) -> SharedElementListOut:
        if ctx is not None:
            self.policy.require_admin(ctx)
        items, total = await self.repo.list_elements(page, page_size)
        out_items = [await self._to_out(el) for el in items]
        return SharedElementListOut(items=out_items, total=total)

    async def create_element(
        self, payload: SharedElementCreate, ctx: RequestContext
    ) -> SharedElementOut:
        self.policy.require_admin(ctx)

        existing = await self.repo.get_by_code(payload.code)
        if existing:
            raise AppError("CONFLICT", 409, f"Shared element '{payload.code}' already exists")

        el = await self.repo.create(**payload.model_dump())
        return await self._to_out(el)

    async def get_element(
        self,
        element_id: int,
        ctx: RequestContext | None = None,
    ) -> SharedElementOut:
        if ctx is not None:
            self.policy.require_admin(ctx)
        el = await self.repo.get_or_raise(element_id)
        return await self._to_out(el)

    async def create_dimension(
        self, element_id: int, payload: DimensionCreate, ctx: RequestContext
    ) -> DimensionOut:
        self.policy.require_admin(ctx)
        await self.repo.get_or_raise(element_id)
        dim = await self.repo.create_dimension(element_id, **payload.model_dump())
        return DimensionOut.model_validate(dim)

    async def list_dimensions(
        self,
        element_id: int,
        ctx: RequestContext | None = None,
    ) -> list[DimensionOut]:
        if ctx is not None:
            self.policy.require_admin(ctx)
        await self.repo.get_or_raise(element_id)
        dims = await self.repo.list_dimensions(element_id)
        return [DimensionOut.model_validate(d) for d in dims]
