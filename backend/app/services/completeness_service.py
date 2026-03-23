from sqlalchemy import select

from app.core.access import get_project_for_ctx
from app.core.access import get_project_or_raise
from app.core.dependencies import RequestContext
from app.db.models.boundary import BoundaryDefinition, BoundaryMembership
from app.db.models.boundary_snapshot import BoundarySnapshot
from app.db.models.company_entity import CompanyEntity
from app.db.models.data_point import DataPoint
from app.events.bus import CompletenessUpdated, get_event_bus
from app.repositories.completeness_repo import CompletenessRepository
from app.schemas.completeness import (
    BoundaryContextOut,
    CompletenessOut,
    DisclosureStatusOut,
    ItemStatusOut,
)


class CompletenessService:
    def __init__(self, repo: CompletenessRepository):
        self.repo = repo

    async def _get_project(self, project_id: int, ctx: RequestContext | None = None):
        if ctx:
            return await get_project_for_ctx(self.repo.session, project_id, ctx)
        return await get_project_or_raise(self.repo.session, project_id)

    async def _load_boundary_scope(self, project_id: int) -> dict | None:
        project = await get_project_or_raise(self.repo.session, project_id)
        if not project.boundary_definition_id:
            return None

        boundary = (
            await self.repo.session.execute(
                select(BoundaryDefinition).where(BoundaryDefinition.id == project.boundary_definition_id)
            )
        ).scalar_one_or_none()
        memberships = (
            await self.repo.session.execute(
                select(BoundaryMembership).where(
                    BoundaryMembership.boundary_definition_id == project.boundary_definition_id,
                    BoundaryMembership.included == True,
                )
            )
        ).scalars().all()
        in_scope_ids = [membership.entity_id for membership in memberships]

        entity_result = await self.repo.session.execute(
            select(CompanyEntity).where(
                CompanyEntity.organization_id == project.organization_id,
                CompanyEntity.entity_type != "parent_company",
            )
        )
        org_entities = list(entity_result.scalars().all())
        entity_names = {entity.id: entity.name for entity in org_entities}
        excluded_entity_ids = sorted(
            entity.id for entity in org_entities if entity.id not in set(in_scope_ids)
        )

        snapshot = (
            await self.repo.session.execute(
                select(BoundarySnapshot).where(BoundarySnapshot.reporting_project_id == project_id)
            )
        ).scalar_one_or_none()
        snapshot_locked = (
            snapshot is not None
            and snapshot.boundary_definition_id == project.boundary_definition_id
        )
        return {
            "project": project,
            "boundary_id": project.boundary_definition_id,
            "boundary_name": boundary.name if boundary else None,
            "entity_ids": sorted(set(in_scope_ids)),
            "entity_names": entity_names,
            "excluded_entity_ids": excluded_entity_ids,
            "snapshot_date": snapshot.created_at.isoformat() if snapshot and snapshot.created_at else None,
            "snapshot_locked": snapshot_locked,
        }

    @staticmethod
    def _scope_entity_id(data_point) -> int | None:
        return getattr(data_point, "facility_id", None) or getattr(data_point, "entity_id", None)

    def _filter_data_points_by_boundary(self, data_points: list, boundary_scope: dict | None) -> list:
        if not boundary_scope:
            return data_points

        boundary_entity_ids = set(boundary_scope["entity_ids"])
        filtered = []
        for data_point in data_points:
            scope_entity_id = self._scope_entity_id(data_point)
            if scope_entity_id is None or scope_entity_id in boundary_entity_ids:
                filtered.append(data_point)
        return filtered

    def _missing_boundary_entity_names(self, covered_entity_ids: set[int], boundary_scope: dict | None) -> list[str]:
        if not boundary_scope:
            return []
        entity_names = boundary_scope["entity_names"]
        return [
            entity_names[entity_id]
            for entity_id in boundary_scope["entity_ids"]
            if entity_id not in covered_entity_ids and entity_id in entity_names
        ]

    async def bind_data_point(
        self, project_id: int, item_id: int, dp_id: int, ctx: RequestContext | None = None
    ) -> dict:
        if ctx:
            await get_project_for_ctx(self.repo.session, project_id, ctx)
        b = await self.repo.create_binding(project_id, item_id, dp_id)
        # Recalculate after binding
        await self.calculate_item_status(project_id, item_id)
        return {"binding_id": b.id}

    async def calculate_item_status(
        self, project_id: int, item_id: int, ctx: RequestContext | None = None
    ) -> str:
        """Calculate completeness status for a single requirement item."""
        await self._get_project(project_id, ctx)
        boundary_scope = await self._load_boundary_scope(project_id)
        data_points = self._filter_data_points_by_boundary(
            await self.repo.get_bound_data_points(project_id, item_id),
            boundary_scope,
        )

        if not data_points:
            status = "missing"
            reason = "No data submitted"
            await self.repo.upsert_item_status(project_id, item_id, status, reason)
            return status

        has_approved = any(dp.status == "approved" for dp in data_points)
        if not has_approved:
            status = "partial"
            reason = "Data exists but not approved"
            await self.repo.upsert_item_status(project_id, item_id, status, reason)
            return status

        # Check evidence for approved data points (requires_evidence)
        from app.db.models.requirement_item import RequirementItem as RIModel

        ri = await self.repo.session.execute(
            select(RIModel).where(RIModel.id == item_id)
        )
        requirement_item = ri.scalar_one_or_none()

        approved_entity_ids = {
            scope_entity_id
            for dp in data_points
            if dp.status == "approved"
            for scope_entity_id in [self._scope_entity_id(dp)]
            if scope_entity_id is not None
        }
        boundary_coverage_required = bool(
            requirement_item
            and requirement_item.granularity_rule
            and requirement_item.granularity_rule.get("boundary_coverage_required")
        )
        if boundary_coverage_required and boundary_scope and approved_entity_ids:
            boundary_entity_ids = set(boundary_scope["entity_ids"])
            if boundary_entity_ids and approved_entity_ids != boundary_entity_ids:
                missing_entity_names = self._missing_boundary_entity_names(approved_entity_ids, boundary_scope)
                status = "partial"
                reason = (
                    "Missing approved data for boundary entities: "
                    + ", ".join(missing_entity_names)
                )
                await self.repo.upsert_item_status(project_id, item_id, status, reason)
                return status

        if requirement_item and requirement_item.requires_evidence:
            has_evidence = False
            for dp in data_points:
                if dp.status == "approved":
                    ev_count = await self.repo.count_evidence_for_dp(dp.id)
                    if ev_count > 0:
                        has_evidence = True
                        break
            if not has_evidence:
                status = "partial"
                reason = "Missing required evidence"
                await self.repo.upsert_item_status(project_id, item_id, status, reason)
                return status

        status = "complete"
        reason = None
        await self.repo.upsert_item_status(project_id, item_id, status, reason)
        return status

    async def aggregate_disclosure_status(
        self, project_id: int, disclosure_id: int, ctx: RequestContext | None = None
    ) -> dict:
        """Aggregate item statuses into disclosure status."""
        if ctx:
            await get_project_for_ctx(self.repo.session, project_id, ctx)
        items = await self.repo.get_required_items(disclosure_id)

        if not items:
            await self.repo.upsert_disclosure_status(project_id, disclosure_id, "complete", 100.0)
            return {"status": "complete", "completion_percent": 100.0}

        statuses = []
        for item in items:
            s = await self.repo.get_item_status(project_id, item.id)
            statuses.append(s.status if s else "missing")

        complete_count = sum(1 for s in statuses if s == "complete")
        total = sum(1 for s in statuses if s != "not_applicable")

        if total == 0:
            pct = 100.0
            status = "complete"
        else:
            pct = (complete_count / total) * 100
            if complete_count == total:
                status = "complete"
            elif complete_count > 0:
                status = "partial"
            else:
                status = "missing"

        await self.repo.upsert_disclosure_status(project_id, disclosure_id, status, pct)
        return {"status": status, "completion_percent": round(pct, 1)}

    async def get_project_completeness(
        self,
        project_id: int,
        ctx: RequestContext | None = None,
        standard_id: int | None = None,
        boundary_context: bool = False,
    ) -> CompletenessOut:
        """Get overall completeness for a project or a single standard."""
        project = await self._get_project(project_id, ctx)
        boundary_scope = await self._load_boundary_scope(project_id) if boundary_context else None

        items_with_disclosures = await self.repo.list_project_items(project_id, standard_id)
        current_item_statuses = await self.repo.list_project_item_statuses(
            project_id, [item.id for item, _disclosure in items_with_disclosures]
        )
        previous_item_state = {
            status.requirement_item_id: (status.status, status.status_reason)
            for status in current_item_statuses
        }
        current_disclosure_statuses = await self.repo.list_project_disclosure_statuses(project_id, standard_id)
        previous_disclosure_state = {
            disclosure_status.disclosure_requirement_id: (
                disclosure_status.status,
                round(disclosure_status.completion_percent, 1),
            )
            for disclosure_status, _disclosure in current_disclosure_statuses
        }

        disclosure_ids = []
        seen_disclosure_ids = set()
        for item, disclosure in items_with_disclosures:
            await self.calculate_item_status(project_id, item.id, ctx)
            if disclosure.id not in seen_disclosure_ids:
                seen_disclosure_ids.add(disclosure.id)
                disclosure_ids.append(disclosure.id)
        for disclosure_id in disclosure_ids:
            await self.aggregate_disclosure_status(project_id, disclosure_id, ctx)

        item_ids = [item.id for item, _disclosure in items_with_disclosures]
        item_statuses = await self.repo.list_project_item_statuses(project_id, item_ids)
        status_by_item_id = {
            status.requirement_item_id: status for status in item_statuses
        }
        bound_data_points_by_item_id = (
            await self.repo.get_bound_data_points_for_items(project_id, item_ids)
            if boundary_scope
            else {}
        )

        item_outputs: list[ItemStatusOut] = []
        complete = 0
        partial = 0
        missing = 0

        for item, _disclosure in items_with_disclosures:
            status = status_by_item_id.get(item.id)
            status_value = status.status if status else "missing"
            if status_value == "complete":
                complete += 1
            elif status_value == "partial":
                partial += 1
            elif status_value != "not_applicable":
                missing += 1

            item_outputs.append(
                ItemStatusOut(
                    requirement_item_id=item.id,
                    status=status_value,
                    status_reason=status.status_reason if status else "No data submitted",
                )
            )

        applicable_total = complete + partial + missing
        overall_percent = round((complete / applicable_total) * 100, 1) if applicable_total else 0
        if applicable_total == 0:
            overall_status = "missing"
        elif complete == applicable_total:
            overall_status = "complete"
        elif complete > 0 or partial > 0:
            overall_status = "partial"
        else:
            overall_status = "missing"

        disclosure_outputs: list[DisclosureStatusOut] = []
        disclosure_statuses = await self.repo.list_project_disclosure_statuses(project_id, standard_id)
        status_by_disclosure_id = {
            disclosure_status.disclosure_requirement_id: disclosure_status
            for disclosure_status, _disclosure in disclosure_statuses
        }
        seen_disclosure_ids = set()
        for _item, disclosure in items_with_disclosures:
            if disclosure.id in seen_disclosure_ids:
                continue
            seen_disclosure_ids.add(disclosure.id)
            disclosure_status = status_by_disclosure_id.get(disclosure.id)
            entity_breakdown = None
            if boundary_scope:
                disclosure_item_ids = [
                    item.id
                    for item, item_disclosure in items_with_disclosures
                    if item_disclosure.id == disclosure.id
                ]
                covered_entity_ids = set()
                for disclosure_item_id in disclosure_item_ids:
                    filtered_data_points = self._filter_data_points_by_boundary(
                        bound_data_points_by_item_id.get(disclosure_item_id, []),
                        boundary_scope,
                    )
                    for data_point in filtered_data_points:
                        scope_entity_id = self._scope_entity_id(data_point)
                        if scope_entity_id is not None:
                            covered_entity_ids.add(scope_entity_id)
                missing_entity_names = self._missing_boundary_entity_names(covered_entity_ids, boundary_scope)
                entity_breakdown = {
                    "covered_entities": len(covered_entity_ids),
                    "missing_entities": max(
                        len(boundary_scope["entity_ids"]) - len(covered_entity_ids),
                        0,
                    ),
                    "excluded_entities": len(boundary_scope["excluded_entity_ids"]),
                    "missing_entity_names": missing_entity_names,
                }
            disclosure_outputs.append(
                DisclosureStatusOut(
                    disclosure_requirement_id=disclosure.id,
                    status=disclosure_status.status if disclosure_status else "missing",
                    completion_percent=(
                        round(disclosure_status.completion_percent, 1) if disclosure_status else 0.0
                    ),
                    code=disclosure.code,
                    title=disclosure.title,
                    entity_breakdown=entity_breakdown,
                )
            )

        boundary_context_out = None
        if boundary_scope:
            covered_entity_ids = set()
            data_points = (
                await self.repo.session.execute(
                    select(DataPoint).where(DataPoint.reporting_project_id == project_id)
                )
            ).scalars().all()
            for data_point in self._filter_data_points_by_boundary(list(data_points), boundary_scope):
                scope_entity_id = self._scope_entity_id(data_point)
                if scope_entity_id is not None:
                    covered_entity_ids.add(scope_entity_id)

            boundary_context_out = BoundaryContextOut(
                boundary_id=boundary_scope["boundary_id"],
                boundary_name=boundary_scope["boundary_name"],
                snapshot_date=boundary_scope["snapshot_date"],
                entities_in_scope=len(boundary_scope["entity_ids"]),
                excluded_entities=len(boundary_scope["excluded_entity_ids"]),
                snapshot_locked=boundary_scope["snapshot_locked"],
                entities_without_data=[
                    boundary_scope["entity_names"][entity_id]
                    for entity_id in boundary_scope["entity_ids"]
                    if entity_id not in covered_entity_ids and entity_id in boundary_scope["entity_names"]
                ],
            )

        changed = False
        current_item_state = {
            status.requirement_item_id: (status.status, status.status_reason)
            for status in item_statuses
        }
        current_disclosure_state = {
            disclosure_status.disclosure_requirement_id: (
                disclosure_status.status,
                round(disclosure_status.completion_percent, 1),
            )
            for disclosure_status, _disclosure in disclosure_statuses
        }
        if current_item_state != previous_item_state or current_disclosure_state != previous_disclosure_state:
            changed = True

        if changed and project.organization_id:
            await get_event_bus().publish(
                CompletenessUpdated(
                    project_id=project_id,
                    organization_id=project.organization_id,
                    standard_id=standard_id,
                    overall_status=overall_status,
                    overall_percent=overall_percent,
                    complete_count=complete,
                    partial_count=partial,
                    missing_count=missing,
                    changed=changed,
                    triggered_by=ctx.user_id if ctx else None,
                )
            )

        return CompletenessOut(
            project_id=project_id,
            standard_id=standard_id,
            items=item_outputs,
            disclosures=disclosure_outputs,
            overall_percent=overall_percent,
            overall_status=overall_status,
            boundary_context=boundary_context_out,
        )
