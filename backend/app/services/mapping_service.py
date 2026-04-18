from datetime import date

from sqlalchemy.exc import IntegrityError

from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.policies.standard_policy import StandardPolicy
from app.repositories.mapping_repo import MappingRepository
from app.schemas.mappings import (
    CrossStandardElement,
    MappingCreate,
    MappingDiffChange,
    MappingDiffOut,
    MappingListOut,
    MappingOut,
    MappingVersionListOut,
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
            payload.requirement_item_id,
            payload.shared_element_id,
            for_update=True,
        )
        try:
            if existing:
                # Retire the current mapping and create the next version under the same lock.
                existing.is_current = False
                existing.valid_to = date.today()
                await self.repo.session.flush()

                m = await self.repo.create(
                    requirement_item_id=payload.requirement_item_id,
                    shared_element_id=payload.shared_element_id,
                    mapping_type=payload.mapping_type,
                    version=existing.version + 1,
                    is_current=True,
                    valid_from=date.today(),
                )
                return MappingOut.model_validate(m)

            m = await self.repo.create(
                **payload.model_dump(),
                valid_from=date.today(),
            )
            return MappingOut.model_validate(m)
        except IntegrityError as exc:
            raise AppError(
                "MAPPING_CONFLICT",
                409,
                "Another mapping update was saved for this item and shared element. Please retry.",
            ) from exc

    async def list_mappings(
        self,
        page: int = 1,
        page_size: int = 50,
        ctx: RequestContext | None = None,
    ) -> MappingListOut:
        if ctx is not None:
            self.policy.require_admin(ctx)
        items, total = await self.repo.list_all(page, page_size)
        return MappingListOut(
            items=[MappingOut.model_validate(m) for m in items],
            total=total,
        )

    async def list_versions(
        self,
        item_id: int,
        element_id: int,
        ctx: RequestContext | None = None,
    ) -> MappingVersionListOut:
        if ctx is not None:
            self.policy.require_admin(ctx)
        versions = await self.repo.list_versions(item_id, element_id)
        return MappingVersionListOut(
            items=[MappingOut.model_validate(v) for v in versions],
            total=len(versions),
        )

    async def diff_versions(
        self,
        item_id: int,
        element_id: int,
        v1: int,
        v2: int,
        ctx: RequestContext | None = None,
    ) -> MappingDiffOut:
        if ctx is not None:
            self.policy.require_admin(ctx)
        ver1 = await self.repo.get_version(item_id, element_id, v1)
        ver2 = await self.repo.get_version(item_id, element_id, v2)
        if not ver1 or not ver2:
            raise AppError("NOT_FOUND", 404, f"Version {v1 if not ver1 else v2} not found")

        changes: list[MappingDiffChange] = []
        compare_fields = ["mapping_type", "valid_from", "valid_to"]
        for field in compare_fields:
            old_val = getattr(ver1, field)
            new_val = getattr(ver2, field)
            if old_val != new_val:
                changes.append(MappingDiffChange(
                    field=field,
                    old_value=str(old_val) if old_val is not None else None,
                    new_value=str(new_val) if new_val is not None else None,
                ))
        return MappingDiffOut(v1=v1, v2=v2, changes=changes)

    async def get_cross_standard(
        self,
        ctx: RequestContext | None = None,
    ) -> list[CrossStandardElement]:
        if ctx is not None:
            self.policy.require_admin(ctx)
        elements = await self.repo.get_cross_standard_elements()
        return [CrossStandardElement(**el) for el in elements]
