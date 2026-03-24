from datetime import date

from sqlalchemy import select

from app.db.models.boundary import BoundaryDefinition, BoundaryMembership
from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.repositories.audit_repo import AuditRepository
from app.repositories.entity_repo import EntityRepository
from app.repositories.role_binding_repo import RoleBindingRepository
from app.services.invitation_service import InvitationService
from app.schemas.entities import (
    ControlLinkCreate,
    ControlLinkOut,
    EntityCreate,
    EntityListOut,
    EntityOut,
    EntityUpdate,
    OrgSetupRequest,
    OwnershipLinkCreate,
    OwnershipLinkOut,
)

COUNTRY_CURRENCY_MAP: dict[str, str] = {
    "US": "USD",
    "GB": "GBP",
    "DE": "EUR",
    "FR": "EUR",
    "IT": "EUR",
    "ES": "EUR",
    "JP": "JPY",
    "CN": "CNY",
}

BOUNDARY_NAME_BY_TYPE: dict[str, str] = {
    "financial_reporting_default": "Financial Reporting Default",
    "financial_control": "Financial Control Boundary",
    "operational_control": "Operational Control Boundary",
    "equity_share": "Equity Share Boundary",
    "custom": "Custom Boundary",
}


class EntityService:
    def __init__(
        self,
        repo: EntityRepository,
        role_binding_repo: RoleBindingRepository | None = None,
        audit_repo: AuditRepository | None = None,
    ):
        self.repo = repo
        self.role_binding_repo = role_binding_repo
        self.audit_repo = audit_repo

    async def _audit(
        self,
        entity_type: str,
        action: str,
        ctx: RequestContext,
        entity_id: int | None = None,
        changes: dict | None = None,
        organization_id: int | None = None,
    ):
        if self.audit_repo:
            await self.audit_repo.log(
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                user_id=ctx.user_id,
                organization_id=organization_id or ctx.organization_id,
                changes=changes,
                performed_by_platform_admin=ctx.is_platform_admin,
            )

    def _require_write(self, ctx: RequestContext) -> None:
        if ctx.role not in ("admin", "esg_manager", "platform_admin"):
            raise AppError("FORBIDDEN", 403, "Only admin/esg_manager can manage entities")

    def _require_read(self, ctx: RequestContext) -> None:
        if ctx.role not in ("admin", "esg_manager", "platform_admin"):
            raise AppError("FORBIDDEN", 403, "Only admin or ESG manager can view company structure")

    # --- Org Setup ---
    async def setup_organization(
        self, payload: OrgSetupRequest, ctx: RequestContext
    ) -> dict:
        """Create tenant, root entity, optional child entities, defaults, and invites."""
        currency = payload.default_currency
        if currency == "USD" and payload.country:
            currency = COUNTRY_CURRENCY_MAP.get(payload.country.upper(), "USD")

        reporting_year = payload.reporting_year or date.today().year

        org = await self.repo.create_organization(
            name=payload.name,
            legal_name=payload.legal_name,
            registration_number=payload.registration_number,
            country=payload.country,
            jurisdiction=payload.jurisdiction,
            industry=payload.industry,
            default_currency=currency,
            default_reporting_year=reporting_year,
            default_standards=payload.standards,
            default_consolidation_approach=payload.consolidation_approach,
            default_ghg_scope_approach=payload.ghg_scope_approach,
            setup_completed=True,
            status="active",
        )

        root = await self.repo.create_entity(
            org_id=org.id,
            name=payload.name,
            entity_type="parent_company",
            country=payload.country,
            jurisdiction=payload.jurisdiction,
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

        boundary = BoundaryDefinition(
            organization_id=org.id,
            name=BOUNDARY_NAME_BY_TYPE.get(payload.boundary_type, "Financial Reporting Default"),
            boundary_type=payload.boundary_type,
            is_default=True,
        )
        self.repo.session.add(boundary)
        await self.repo.session.flush()

        self.repo.session.add(BoundaryMembership(
            boundary_definition_id=boundary.id,
            entity_id=root.id,
            included=True,
            inclusion_source="automatic",
            consolidation_method="full",
            inclusion_reason="Onboarding root entity",
        ))

        created_entities = 1
        for subsidiary in payload.subsidiaries:
            entity = await self.repo.create_entity(
                org.id,
                parent_entity_id=root.id,
                name=subsidiary.name,
                entity_type=subsidiary.entity_type,
                country=subsidiary.country or payload.country,
                jurisdiction=subsidiary.jurisdiction or payload.jurisdiction,
                status="active",
            )
            created_entities += 1
            await self.repo.create_ownership(
                parent_entity_id=root.id,
                child_entity_id=entity.id,
                ownership_percent=subsidiary.ownership_percent,
                ownership_type="direct",
            )
            self.repo.session.add(BoundaryMembership(
                boundary_definition_id=boundary.id,
                entity_id=entity.id,
                included=True,
                inclusion_source="automatic",
                consolidation_method="full",
                inclusion_reason="Onboarding subsidiary",
            ))
            await self._audit(
                "CompanyEntity",
                "create_entity",
                ctx,
                entity_id=entity.id,
                changes={
                    "organization_id": org.id,
                    "parent_entity_id": root.id,
                    "entity_type": subsidiary.entity_type,
                    "ownership_percent": subsidiary.ownership_percent,
                },
                organization_id=org.id,
            )

        invited_users = 0
        invitation_service = InvitationService(self.repo.session)
        for invite in payload.invite_users:
            await invitation_service.create_invitation(
                org_id=org.id,
                email=invite.email,
                role=invite.role,
                invited_by=ctx.user_id,
            )
            invited_users += 1

        await self.repo.session.flush()

        await self._audit(
            "CompanyEntity",
            "create_entity",
            ctx,
            entity_id=root.id,
            changes={"entity_type": "parent_company", "organization_id": org.id},
            organization_id=org.id,
        )
        await self._audit(
            "BoundaryDefinition",
            "create_boundary",
            ctx,
            entity_id=boundary.id,
            changes={"organization_id": org.id, "boundary_type": payload.boundary_type},
            organization_id=org.id,
        )

        return {
            "organization_id": org.id,
            "root_entity_id": root.id,
            "boundary_id": boundary.id,
            "created_entities": created_entities,
            "invited_users": invited_users,
            "next_step": "/dashboard",
        }

    # --- Entities ---
    async def list_entities(
        self, ctx: RequestContext, page: int = 1, page_size: int = 50
    ) -> EntityListOut:
        self._require_read(ctx)
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
        default_boundary_result = await self.repo.session.execute(
            select(BoundaryDefinition).where(
                BoundaryDefinition.organization_id == ctx.organization_id,
                BoundaryDefinition.is_default == True,  # noqa: E712
            )
        )
        default_boundary = default_boundary_result.scalar_one_or_none()
        if default_boundary is not None:
            self.repo.session.add(
                BoundaryMembership(
                    boundary_definition_id=default_boundary.id,
                    entity_id=e.id,
                    included=True,
                    inclusion_source="automatic",
                    consolidation_method="full",
                    inclusion_reason="Entity created in organization",
                )
            )
        await self._audit("CompanyEntity", "create_entity", ctx, entity_id=e.id,
                          changes=payload.model_dump())
        return EntityOut.model_validate(e)

    async def update_entity(
        self,
        entity_id: int,
        payload: EntityUpdate,
        ctx: RequestContext,
    ) -> EntityOut:
        self._require_write(ctx)
        if not ctx.organization_id:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required")

        entity = await self.repo.get_or_raise(entity_id)
        if entity.organization_id != ctx.organization_id and not ctx.is_platform_admin:
            raise AppError("FORBIDDEN", 403, "Entity does not belong to this organization")

        updates = payload.model_dump(exclude_unset=True)
        updated = await self.repo.update_entity(entity_id, **updates)
        await self._audit("CompanyEntity", "update_entity", ctx, entity_id=entity_id, changes=updates)
        return EntityOut.model_validate(updated)

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

        # Cycle detection: child cannot own parent (directly or indirectly)
        await self._check_ownership_cycle(payload.parent_entity_id, payload.child_entity_id)

        link = await self.repo.create_ownership(**payload.model_dump())
        await self._audit("OwnershipLink", "create_ownership", ctx, entity_id=link.id,
                          changes=payload.model_dump())
        return OwnershipLinkOut.model_validate(link)

    # --- Control ---
    async def create_control(
        self, payload: ControlLinkCreate, ctx: RequestContext
    ) -> ControlLinkOut:
        self._require_write(ctx)

        if payload.controlling_entity_id == payload.controlled_entity_id:
            raise AppError("SELF_CONTROL_NOT_ALLOWED", 422, "Entity cannot control itself")

        link = await self.repo.create_control(**payload.model_dump())
        await self._audit("ControlLink", "create_control", ctx, entity_id=link.id,
                          changes=payload.model_dump())
        return ControlLinkOut.model_validate(link)

    async def _check_ownership_cycle(self, parent_id: int, child_id: int) -> None:
        """Prevent cycles: check if child already owns parent (directly or indirectly)."""
        from sqlalchemy import select
        from app.db.models.company_entity import OwnershipLink

        visited = set()
        stack = [child_id]

        while stack:
            current = stack.pop()
            if current == parent_id:
                raise AppError(
                    "OWNERSHIP_CYCLE_DETECTED", 422,
                    "Adding this ownership link would create a cycle"
                )
            if current in visited:
                continue
            visited.add(current)

            # Find entities that current entity owns
            q = select(OwnershipLink.child_entity_id).where(
                OwnershipLink.parent_entity_id == current
            )
            result = await self.repo.session.execute(q)
            for row in result.all():
                stack.append(row[0])

    # -- Organization Settings ------------------------------------------------

    async def get_org_settings(self, ctx: RequestContext) -> dict:
        if ctx.role not in ("admin", "esg_manager", "platform_admin"):
            raise AppError("FORBIDDEN", 403, "Only admin/esg_manager can view org settings")
        org = await self.repo.get_organization(ctx.organization_id)
        if not org:
            raise AppError("NOT_FOUND", 404, "Organization not found")
        return {
            "id": org.id,
            "name": org.name,
            "legal_name": org.legal_name,
            "registration_number": org.registration_number,
            "country": org.country,
            "jurisdiction": org.jurisdiction,
            "industry": org.industry,
            "default_currency": org.default_currency,
            "default_reporting_year": org.default_reporting_year,
            "default_consolidation_approach": org.default_consolidation_approach,
            "default_ghg_scope_approach": org.default_ghg_scope_approach,
            "status": org.status,
        }

    async def update_org_settings(self, changes: dict, ctx: RequestContext) -> dict:
        if ctx.role not in ("admin", "platform_admin"):
            raise AppError("FORBIDDEN", 403, "Only admin can update org settings")
        org = await self.repo.get_organization(ctx.organization_id)
        if not org:
            raise AppError("NOT_FOUND", 404, "Organization not found")
        for key, value in changes.items():
            if hasattr(org, key):
                setattr(org, key, value)
        await self._audit("Organization", "org_settings_updated", ctx, entity_id=org.id, changes=changes)
        return await self.get_org_settings(ctx)
