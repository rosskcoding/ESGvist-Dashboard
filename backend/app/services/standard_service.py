from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.policies.standard_policy import StandardPolicy
from app.repositories.standard_repo import StandardRepository
from app.schemas.standards import (
    DisclosureCreate,
    DisclosureListOut,
    DisclosureOut,
    SectionCreate,
    SectionOut,
    StandardCreate,
    StandardListOut,
    StandardOut,
    StandardUpdate,
)
from app.services.standard_catalog import build_standard_out


class StandardService:
    def __init__(self, repo: StandardRepository, policy: StandardPolicy):
        self.repo = repo
        self.policy = policy

    # --- Standards ---
    async def list_standards(self, page: int = 1, page_size: int = 20) -> StandardListOut:
        items, total = await self.repo.list_standards(page, page_size)
        return StandardListOut(
            items=[build_standard_out(s) for s in items],
            total=total,
        )

    async def create_standard(self, payload: StandardCreate, ctx: RequestContext) -> StandardOut:
        self.policy.require_admin(ctx)

        existing = await self.repo.get_by_code(payload.code)
        if existing:
            raise AppError("CONFLICT", 409, f"Standard with code '{payload.code}' already exists")

        s = await self.repo.create_standard(**payload.model_dump())
        return build_standard_out(s)

    async def get_standard(self, standard_id: int) -> StandardOut:
        s = await self.repo.get_or_raise(standard_id)
        return build_standard_out(s)

    async def update_standard(
        self, standard_id: int, payload: StandardUpdate, ctx: RequestContext
    ) -> StandardOut:
        self.policy.require_admin(ctx)
        s = await self.repo.update_standard(standard_id, **payload.model_dump(exclude_unset=True))
        return build_standard_out(s)

    async def deactivate_standard(self, standard_id: int, ctx: RequestContext) -> StandardOut:
        self.policy.require_admin(ctx)
        s = await self.repo.update_standard(standard_id, is_active=False)
        return build_standard_out(s)

    # --- Sections ---
    async def list_sections(self, standard_id: int) -> list[SectionOut]:
        await self.repo.get_or_raise(standard_id)
        sections = await self.repo.list_sections(standard_id)

        # Build tree
        by_id: dict[int, SectionOut] = {}
        roots: list[SectionOut] = []

        for s in sections:
            out = SectionOut.model_validate(s)
            out.children = []
            by_id[s.id] = out

        for s in sections:
            out = by_id[s.id]
            if s.parent_section_id and s.parent_section_id in by_id:
                by_id[s.parent_section_id].children.append(out)
            else:
                roots.append(out)

        return roots

    async def create_section(
        self, standard_id: int, payload: SectionCreate, ctx: RequestContext
    ) -> SectionOut:
        self.policy.require_admin(ctx)
        await self.repo.get_or_raise(standard_id)
        s = await self.repo.create_section(standard_id, **payload.model_dump())
        return SectionOut.model_validate(s)

    # --- Disclosures ---
    async def list_disclosures(
        self, standard_id: int, page: int = 1, page_size: int = 50
    ) -> DisclosureListOut:
        await self.repo.get_or_raise(standard_id)
        items, total = await self.repo.list_disclosures(standard_id, page, page_size)
        return DisclosureListOut(
            items=[DisclosureOut.model_validate(d) for d in items],
            total=total,
        )

    async def create_disclosure(
        self, standard_id: int, payload: DisclosureCreate, ctx: RequestContext
    ) -> DisclosureOut:
        self.policy.require_admin(ctx)
        await self.repo.get_or_raise(standard_id)

        existing = await self.repo.get_disclosure_by_code(standard_id, payload.code)
        if existing:
            raise AppError(
                "CONFLICT", 409,
                f"Disclosure with code '{payload.code}' already exists in this standard"
            )

        d = await self.repo.create_disclosure(standard_id, **payload.model_dump())
        return DisclosureOut.model_validate(d)
