from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.repositories.entity_repo import EntityRepository
from app.repositories.role_binding_repo import RoleBindingRepository
from app.schemas.entities import (
    ControlLinkCreate,
    ControlLinkOut,
    EntityCreate,
    EntityListOut,
    EntityOut,
    OrgSetupRequest,
    OwnershipLinkCreate,
    OwnershipLinkOut,
)


class EntityService:
    def __init__(
        self,
        repo: EntityRepository,
        role_binding_repo: RoleBindingRepository | None = None,
    ):
        self.repo = repo
        self.role_binding_repo = role_binding_repo

    def _require_write(self, ctx: RequestContext) -> None:
        if ctx.role not in ("admin", "esg_manager", "platform_admin"):
            raise AppError("FORBIDDEN", 403, "Only admin/esg_manager can manage entities")

    # --- Org Setup ---
    async def setup_organization(
        self, payload: OrgSetupRequest, ctx: RequestContext
    ) -> dict:
        """Create organization + root entity + admin role binding."""
        org = await self.repo.create_organization(
            name=payload.name,
            country=payload.country,
            industry=payload.industry,
            default_currency=payload.default_currency,
            setup_completed=True,
        )

        root = await self.repo.create_entity(
            org_id=org.id,
            name=payload.name,
            entity_type="parent_company",
            country=payload.country,
            status="active",
        )

        # Assign creator as admin of this org
        if self.role_binding_repo:
            await self.role_binding_repo.create(
                user_id=ctx.user_id,
                role="admin",
                scope_type="organization",
                scope_id=org.id,
                created_by=ctx.user_id,
            )

        return {
            "organization_id": org.id,
            "root_entity_id": root.id,
        }

    # --- Entities ---
    async def list_entities(
        self, ctx: RequestContext, page: int = 1, page_size: int = 50
    ) -> EntityListOut:
        if not ctx.organization_id:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required")
        items, total = await self.repo.list_entities(ctx.organization_id, page, page_size)
        return EntityListOut(
            items=[EntityOut.model_validate(e) for e in items],
            total=total,
        )

    async def create_entity(
        self, payload: EntityCreate, ctx: RequestContext
    ) -> EntityOut:
        self._require_write(ctx)
        if not ctx.organization_id:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required")
        e = await self.repo.create_entity(ctx.organization_id, **payload.model_dump())
        return EntityOut.model_validate(e)

    # --- Ownership ---
    async def create_ownership(
        self, payload: OwnershipLinkCreate, ctx: RequestContext
    ) -> OwnershipLinkOut:
        self._require_write(ctx)

        if payload.parent_entity_id == payload.child_entity_id:
            raise AppError("SELF_OWNERSHIP_NOT_ALLOWED", 422, "Entity cannot own itself")

        # Check sum ≤ 100%
        current_sum = await self.repo.get_ownership_sum(payload.child_entity_id)
        if current_sum + payload.ownership_percent > 100:
            raise AppError(
                "OWNERSHIP_EXCEEDS_100", 422,
                f"Total ownership would be {current_sum + payload.ownership_percent}%"
            )

        link = await self.repo.create_ownership(**payload.model_dump())
        return OwnershipLinkOut.model_validate(link)

    # --- Control ---
    async def create_control(
        self, payload: ControlLinkCreate, ctx: RequestContext
    ) -> ControlLinkOut:
        self._require_write(ctx)

        if payload.controlling_entity_id == payload.controlled_entity_id:
            raise AppError("SELF_CONTROL_NOT_ALLOWED", 422, "Entity cannot control itself")

        link = await self.repo.create_control(**payload.model_dump())
        return ControlLinkOut.model_validate(link)
