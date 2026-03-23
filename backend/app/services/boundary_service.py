from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.db.models.boundary import BoundaryDefinition, BoundaryMembership
from app.db.models.boundary_snapshot import BoundarySnapshot
from app.db.models.company_entity import CompanyEntity
from app.db.models.project import ReportingProject
from app.core.access import get_project_for_ctx
from app.policies.auth_policy import AuthPolicy
from app.policies.boundary_policy import BoundaryPolicy
from app.repositories.audit_repo import AuditRepository
from app.repositories.completeness_repo import CompletenessRepository
from app.schemas.projects import (
    BoundaryDefOut,
    BoundaryDefUpdate,
    BoundaryMembershipListOut,
    BoundaryMembershipReplaceRequest,
    BoundaryMembershipRowOut,
    ProjectBoundaryOut,
)
from app.services.completeness_service import CompletenessService


class BoundaryService:
    def __init__(self, session: AsyncSession, audit_repo: AuditRepository | None = None):
        self.session = session
        self.audit_repo = audit_repo

    async def _get_boundary_or_raise(self, boundary_id: int, ctx: RequestContext) -> BoundaryDefinition:
        result = await self.session.execute(
            select(BoundaryDefinition).where(BoundaryDefinition.id == boundary_id)
        )
        boundary = result.scalar_one_or_none()
        if not boundary:
            raise AppError("BOUNDARY_NOT_FOUND", 404, f"Boundary {boundary_id} not found")
        AuthPolicy.check_tenant_isolation(ctx, boundary.organization_id)
        return boundary

    async def _require_read(self, ctx: RequestContext) -> None:
        AuthPolicy.require_role(
            ctx,
            ["admin", "esg_manager", "reviewer", "auditor", "platform_admin"],
        )

    async def _assert_editable(self, boundary: BoundaryDefinition) -> None:
        locked_project = (
            await self.session.execute(
                select(ReportingProject.id).where(
                    ReportingProject.boundary_definition_id == boundary.id,
                    ReportingProject.status.in_(("review", "published")),
                )
            )
        ).scalar_one_or_none()
        if locked_project:
            raise AppError(
                "BOUNDARY_LOCKED_FOR_PROJECT",
                422,
                "Boundary is locked for a project in review or published state",
            )

    async def _audit(
        self,
        *,
        entity_id: int | None,
        action: str,
        ctx: RequestContext,
        changes: dict | None = None,
    ) -> None:
        if not self.audit_repo:
            return
        await self.audit_repo.log(
            entity_type="BoundaryMembership",
            entity_id=entity_id,
            action=action,
            user_id=ctx.user_id,
            organization_id=ctx.organization_id,
            changes=changes,
            performed_by_platform_admin=ctx.is_platform_admin,
        )

    async def _project_ids_using_boundary(self, boundary_id: int) -> list[int]:
        result = await self.session.execute(
            select(ReportingProject.id).where(ReportingProject.boundary_definition_id == boundary_id)
        )
        return [row[0] for row in result.all()]

    async def _invalidate_snapshots(self, boundary_id: int) -> int:
        project_ids = await self._project_ids_using_boundary(boundary_id)
        if not project_ids:
            return 0
        deleted = await self.session.execute(
            delete(BoundarySnapshot).where(BoundarySnapshot.reporting_project_id.in_(project_ids))
        )
        return deleted.rowcount or 0

    async def _recalculate_completeness(self, project_ids: list[int]) -> None:
        if not project_ids:
            return
        service = CompletenessService(CompletenessRepository(self.session))
        for project_id in project_ids:
            items_with_disclosures = await service.repo.list_project_items(project_id)
            item_ids = [item.id for item, _disclosure in items_with_disclosures]
            disclosure_ids = sorted({disclosure.id for _item, disclosure in items_with_disclosures})
            for item_id in item_ids:
                await service.calculate_item_status(project_id, item_id)
            for disclosure_id in disclosure_ids:
                await service.aggregate_disclosure_status(project_id, disclosure_id)

    async def _list_entities(self, organization_id: int) -> list[CompanyEntity]:
        result = await self.session.execute(
            select(CompanyEntity)
            .where(CompanyEntity.organization_id == organization_id)
            .order_by(CompanyEntity.id)
        )
        return list(result.scalars().all())

    async def list_memberships(self, boundary_id: int, ctx: RequestContext) -> BoundaryMembershipListOut:
        await self._require_read(ctx)
        boundary = await self._get_boundary_or_raise(boundary_id, ctx)
        memberships_result = await self.session.execute(
            select(BoundaryMembership).where(BoundaryMembership.boundary_definition_id == boundary_id)
        )
        memberships = {membership.entity_id: membership for membership in memberships_result.scalars().all()}
        entities = await self._list_entities(boundary.organization_id)
        rows = [
            BoundaryMembershipRowOut(
                id=memberships.get(entity.id).id if memberships.get(entity.id) else None,
                entity_id=entity.id,
                entity_name=entity.name,
                entity_type=entity.entity_type,
                included=memberships.get(entity.id).included if memberships.get(entity.id) else False,
                inclusion_source=(
                    memberships.get(entity.id).inclusion_source if memberships.get(entity.id) else None
                ),
                consolidation_method=(
                    memberships.get(entity.id).consolidation_method if memberships.get(entity.id) else None
                ),
                inclusion_reason=(
                    memberships.get(entity.id).inclusion_reason if memberships.get(entity.id) else None
                ),
                explicit=entity.id in memberships,
            )
            for entity in entities
        ]
        return BoundaryMembershipListOut(
            boundary_id=boundary.id,
            boundary_name=boundary.name,
            memberships=rows,
        )

    async def get_boundary(self, boundary_id: int, ctx: RequestContext) -> BoundaryDefOut:
        await self._require_read(ctx)
        boundary = await self._get_boundary_or_raise(boundary_id, ctx)
        return BoundaryDefOut.model_validate(boundary)

    async def update_boundary(
        self,
        boundary_id: int,
        payload: BoundaryDefUpdate,
        ctx: RequestContext,
    ) -> BoundaryDefOut:
        BoundaryPolicy.can_create(ctx)
        boundary = await self._get_boundary_or_raise(boundary_id, ctx)
        await self._assert_editable(boundary)
        changes = payload.model_dump(exclude_unset=True)
        for key, value in changes.items():
            setattr(boundary, key, value)
        await self.session.flush()
        if self.audit_repo:
            await self.audit_repo.log(
                entity_type="BoundaryDefinition",
                entity_id=boundary.id,
                action="update_boundary",
                user_id=ctx.user_id,
                organization_id=ctx.organization_id,
                changes=changes,
                performed_by_platform_admin=ctx.is_platform_admin,
            )
        return BoundaryDefOut.model_validate(boundary)

    async def get_project_boundary(self, project_id: int, ctx: RequestContext) -> ProjectBoundaryOut:
        project = await get_project_for_ctx(self.session, project_id, ctx)
        if not project.boundary_definition_id:
            return ProjectBoundaryOut()

        boundary = await self._get_boundary_or_raise(project.boundary_definition_id, ctx)
        snapshot = (
            await self.session.execute(
                select(BoundarySnapshot).where(BoundarySnapshot.reporting_project_id == project_id)
            )
        ).scalar_one_or_none()
        snapshot_locked = (
            snapshot is not None
            and snapshot.boundary_definition_id == project.boundary_definition_id
        )
        return ProjectBoundaryOut(
            boundary_id=boundary.id,
            boundary_name=boundary.name,
            boundary_type=boundary.boundary_type,
            snapshot_id=snapshot.id if snapshot else None,
            snapshot_locked=snapshot_locked,
            snapshot_date=snapshot.created_at.isoformat() if snapshot and snapshot.created_at else None,
        )

    async def replace_memberships(
        self,
        boundary_id: int,
        payload: BoundaryMembershipReplaceRequest,
        ctx: RequestContext,
    ) -> BoundaryMembershipListOut:
        BoundaryPolicy.can_modify_membership(ctx)
        boundary = await self._get_boundary_or_raise(boundary_id, ctx)
        await self._assert_editable(boundary)

        seen_entity_ids: set[int] = set()
        entities = {entity.id: entity for entity in await self._list_entities(boundary.organization_id)}
        for item in payload.memberships:
            if item.entity_id in seen_entity_ids:
                raise AppError("DUPLICATE_ENTITY", 422, f"Entity {item.entity_id} appears multiple times")
            seen_entity_ids.add(item.entity_id)
            if item.entity_id not in entities:
                raise AppError("NOT_FOUND", 404, f"Entity {item.entity_id} not found in boundary organization")

        existing_result = await self.session.execute(
            select(BoundaryMembership).where(BoundaryMembership.boundary_definition_id == boundary_id)
        )
        existing_by_entity = {membership.entity_id: membership for membership in existing_result.scalars().all()}

        for item in payload.memberships:
            existing = existing_by_entity.pop(item.entity_id, None)
            if existing:
                changed = (
                    existing.included != item.included
                    or existing.inclusion_source != item.inclusion_source
                    or existing.consolidation_method != item.consolidation_method
                    or existing.inclusion_reason != item.inclusion_reason
                )
                if changed:
                    existing.included = item.included
                    existing.inclusion_source = item.inclusion_source
                    existing.consolidation_method = item.consolidation_method
                    existing.inclusion_reason = item.inclusion_reason
                    await self._audit(
                        entity_id=existing.id,
                        action="manual_boundary_override",
                        ctx=ctx,
                        changes={
                            "boundary_id": boundary_id,
                            "entity_id": item.entity_id,
                            "included": item.included,
                            "inclusion_source": item.inclusion_source,
                            "consolidation_method": item.consolidation_method,
                        },
                    )
            else:
                membership = BoundaryMembership(
                    boundary_definition_id=boundary_id,
                    entity_id=item.entity_id,
                    included=item.included,
                    inclusion_source=item.inclusion_source,
                    consolidation_method=item.consolidation_method,
                    inclusion_reason=item.inclusion_reason,
                )
                self.session.add(membership)
                await self.session.flush()
                await self._audit(
                    entity_id=membership.id,
                    action="manual_boundary_override",
                    ctx=ctx,
                    changes={
                        "boundary_id": boundary_id,
                        "entity_id": item.entity_id,
                        "included": item.included,
                        "inclusion_source": item.inclusion_source,
                        "consolidation_method": item.consolidation_method,
                    },
                )

        for membership in existing_by_entity.values():
            await self._audit(
                entity_id=membership.id,
                action="delete_boundary_membership",
                ctx=ctx,
                changes={"boundary_id": boundary_id, "entity_id": membership.entity_id},
            )
            await self.session.delete(membership)

        await self.session.flush()
        snapshots_invalidated = await self._invalidate_snapshots(boundary_id)
        await self._recalculate_completeness(await self._project_ids_using_boundary(boundary_id))
        if self.audit_repo:
            await self.audit_repo.log(
                entity_type="BoundaryDefinition",
                entity_id=boundary_id,
                action="boundary_memberships_replaced",
                user_id=ctx.user_id,
                organization_id=ctx.organization_id,
                changes={
                    "memberships_count": len(payload.memberships),
                    "snapshots_invalidated": snapshots_invalidated,
                },
                performed_by_platform_admin=ctx.is_platform_admin,
            )
        return await self.list_memberships(boundary_id, ctx)

    async def recalculate_memberships(self, boundary_id: int, ctx: RequestContext) -> dict:
        BoundaryPolicy.can_modify_membership(ctx)
        boundary = await self._get_boundary_or_raise(boundary_id, ctx)
        await self._assert_editable(boundary)

        entities = await self._list_entities(boundary.organization_id)
        root_entity = next((entity for entity in entities if entity.entity_type == "parent_company"), None)
        memberships_result = await self.session.execute(
            select(BoundaryMembership).where(BoundaryMembership.boundary_definition_id == boundary_id)
        )
        memberships = list(memberships_result.scalars().all())

        updated = 0
        created = 0
        for membership in memberships:
            if membership.inclusion_source == "manual":
                continue
            desired_method = (
                "equity_share"
                if boundary.boundary_type == "equity_share"
                else membership.consolidation_method or "full"
            )
            if (
                membership.inclusion_source != "automatic"
                or membership.consolidation_method != desired_method
            ):
                membership.inclusion_source = "automatic"
                membership.consolidation_method = desired_method
                updated += 1

        if boundary.is_default and root_entity is not None:
            root_membership = next(
                (membership for membership in memberships if membership.entity_id == root_entity.id),
                None,
            )
            if root_membership is None:
                self.session.add(
                    BoundaryMembership(
                        boundary_definition_id=boundary_id,
                        entity_id=root_entity.id,
                        included=True,
                        inclusion_source="automatic",
                        consolidation_method="full",
                        inclusion_reason="Default root entity inclusion",
                    )
                )
                created += 1
            else:
                if (
                    root_membership.included is not True
                    or root_membership.inclusion_source != "automatic"
                    or root_membership.consolidation_method != "full"
                ):
                    root_membership.included = True
                    root_membership.inclusion_source = "automatic"
                    root_membership.consolidation_method = "full"
                    updated += 1

        await self.session.flush()
        snapshots_invalidated = await self._invalidate_snapshots(boundary_id)
        await self._recalculate_completeness(await self._project_ids_using_boundary(boundary_id))
        if self.audit_repo:
            await self.audit_repo.log(
                entity_type="BoundaryDefinition",
                entity_id=boundary_id,
                action="boundary_recalculated",
                user_id=ctx.user_id,
                organization_id=ctx.organization_id,
                changes={
                    "created": created,
                    "updated": updated,
                    "snapshots_invalidated": snapshots_invalidated,
                },
                performed_by_platform_admin=ctx.is_platform_admin,
            )
        return {
            "boundary_id": boundary_id,
            "recalculated": True,
            "created": created,
            "updated": updated,
            "snapshots_invalidated": snapshots_invalidated,
        }
