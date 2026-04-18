from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.domain.catalog import build_requirement_item_key
from app.db.models.standard import DisclosureRequirement, Standard
from app.policies.standard_policy import StandardPolicy
from app.repositories.requirement_item_repo import RequirementItemRepository
from app.schemas.requirement_items import (
    DependencyCreate,
    DependencyOut,
    RequirementItemCreate,
    RequirementItemListOut,
    RequirementItemOut,
)


class RequirementItemService:
    def __init__(self, repo: RequirementItemRepository, policy: StandardPolicy):
        self.repo = repo
        self.policy = policy

    async def list_items(
        self, disclosure_id: int, page: int = 1, page_size: int = 50
    ) -> RequirementItemListOut:
        items, total = await self.repo.list_by_disclosure(disclosure_id, page, page_size)
        return RequirementItemListOut(
            items=[RequirementItemOut.model_validate(i) for i in items],
            total=total,
        )

    async def create_item(
        self, disclosure_id: int, payload: RequirementItemCreate, ctx: RequestContext
    ) -> RequirementItemOut:
        self.policy.require_admin(ctx)
        disclosure = await self.repo.session.get(DisclosureRequirement, disclosure_id)
        if disclosure is None:
            raise AppError("NOT_FOUND", 404, f"Disclosure {disclosure_id} not found")
        standard = await self.repo.session.get(Standard, disclosure.standard_id)
        if standard is None:
            raise AppError("NOT_FOUND", 404, f"Standard {disclosure.standard_id} not found")

        item = await self.repo.create(
            disclosure_id,
            catalog_key=build_requirement_item_key(
                standard.code,
                disclosure.code,
                payload.item_code,
                payload.name,
            ),
            **payload.model_dump(),
        )
        return RequirementItemOut.model_validate(item)

    async def list_dependencies(self, item_id: int) -> list[DependencyOut]:
        deps = await self.repo.list_dependencies(item_id)
        return [DependencyOut.model_validate(d) for d in deps]

    async def create_dependency(
        self, item_id: int, payload: DependencyCreate, ctx: RequestContext
    ) -> DependencyOut:
        self.policy.require_admin(ctx)
        await self.repo.get_or_raise(item_id)
        dep = await self.repo.create_dependency(item_id, **payload.model_dump())
        return DependencyOut.model_validate(dep)
