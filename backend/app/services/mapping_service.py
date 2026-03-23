from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.policies.standard_policy import StandardPolicy
from app.repositories.mapping_repo import MappingRepository
from app.schemas.mappings import (
    CrossStandardElement,
    MappingCreate,
    MappingListOut,
    MappingOut,
)


class MappingService:
    def __init__(self, repo: MappingRepository, policy: StandardPolicy):
        self.repo = repo
        self.policy = policy

    async def create_mapping(
        self, payload: MappingCreate, ctx: RequestContext
    ) -> MappingOut:
        self.policy.require_admin(ctx)

        existing = await self.repo.get_by_item_and_element(
            payload.requirement_item_id, payload.shared_element_id
        )
        if existing:
            raise AppError(
                "CONFLICT", 409,
                "Mapping already exists for this item and shared element"
            )

        m = await self.repo.create(**payload.model_dump())
        return MappingOut.model_validate(m)

    async def list_mappings(self, page: int = 1, page_size: int = 50) -> MappingListOut:
        items, total = await self.repo.list_all(page, page_size)
        return MappingListOut(
            items=[MappingOut.model_validate(m) for m in items],
            total=total,
        )

    async def get_cross_standard(self) -> list[CrossStandardElement]:
        elements = await self.repo.get_cross_standard_elements()
        return [CrossStandardElement(**el) for el in elements]
