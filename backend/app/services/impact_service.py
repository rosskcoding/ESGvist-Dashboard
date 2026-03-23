"""Impact analysis: preview effects of changing requirement items, mappings, or boundary."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import get_project_for_ctx
from app.core.dependencies import RequestContext
from app.db.models.boundary import BoundaryDefinition
from app.db.models.company_entity import CompanyEntity
from app.db.models.completeness import RequirementItemDataPoint
from app.db.models.data_point import DataPoint
from app.db.models.mapping import RequirementItemSharedElement
from app.db.models.project import MetricAssignment, ReportingProject, ReportingProjectStandard
from app.db.models.requirement_item import RequirementItem
from app.db.models.shared_element import SharedElement
from app.db.models.standard import DisclosureRequirement
from app.policies.auth_policy import AuthPolicy


class ImpactService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def preview_requirement_change(
        self, item_id: int, ctx: RequestContext | None = None
    ) -> dict:
        """Preview impact of changing a requirement item."""
        if ctx:
            AuthPolicy.require_manager_or_admin(ctx)

        # Find standards affected
        item_q = select(RequirementItem).where(RequirementItem.id == item_id)
        item_result = await self.session.execute(item_q)
        item = item_result.scalar_one_or_none()
        if not item:
            return {"affected_items": 0, "affected_standards": 0, "affected_projects": 0, "affected_data_points": 0}

        # Get standard
        disc_q = select(DisclosureRequirement).where(DisclosureRequirement.id == item.disclosure_requirement_id)
        disc_result = await self.session.execute(disc_q)
        disc = disc_result.scalar_one_or_none()

        # Count affected projects
        proj_q = select(func.count()).select_from(ReportingProjectStandard).where(
            ReportingProjectStandard.standard_id == disc.standard_id if disc else 0
        )
        proj_count = (await self.session.execute(proj_q)).scalar_one()

        # Count affected data points
        dp_q = select(func.count()).select_from(RequirementItemDataPoint).where(
            RequirementItemDataPoint.requirement_item_id == item_id
        )
        dp_count = (await self.session.execute(dp_q)).scalar_one()

        return {
            "requirement_item_id": item_id,
            "affected_items": 1,
            "affected_standards": 1 if disc else 0,
            "affected_projects": proj_count,
            "affected_data_points": dp_count,
        }

    async def preview_mapping_change(
        self, mapping_id: int, ctx: RequestContext | None = None
    ) -> dict:
        """Preview impact of changing a mapping."""
        if ctx:
            AuthPolicy.require_manager_or_admin(ctx)

        mapping_q = select(RequirementItemSharedElement).where(
            RequirementItemSharedElement.id == mapping_id
        )
        result = await self.session.execute(mapping_q)
        mapping = result.scalar_one_or_none()
        if not mapping:
            return {"affected_items": 0, "affected_standards": 0}

        # Find all items mapped to same shared element
        items_q = select(func.count()).select_from(RequirementItemSharedElement).where(
            RequirementItemSharedElement.shared_element_id == mapping.shared_element_id
        )
        items_count = (await self.session.execute(items_q)).scalar_one()

        # Find distinct standards
        standards_q = (
            select(func.count(func.distinct(DisclosureRequirement.standard_id)))
            .select_from(RequirementItemSharedElement)
            .join(RequirementItem, RequirementItem.id == RequirementItemSharedElement.requirement_item_id)
            .join(DisclosureRequirement, DisclosureRequirement.id == RequirementItem.disclosure_requirement_id)
            .where(RequirementItemSharedElement.shared_element_id == mapping.shared_element_id)
        )
        std_count = (await self.session.execute(standards_q)).scalar_one()

        return {
            "mapping_id": mapping_id,
            "affected_items": items_count,
            "affected_standards": std_count,
        }

    async def preview_boundary_change(
        self,
        project_id: int,
        new_boundary_id: int,
        ctx: RequestContext | None = None,
    ) -> dict:
        """Preview impact of changing boundary on a project."""
        from app.db.models.boundary import BoundaryMembership

        if ctx:
            AuthPolicy.require_manager_or_admin(ctx)
            await get_project_for_ctx(
                self.session,
                project_id,
                ctx,
                allow_collectors=False,
                allow_reviewers=False,
            )

        # Get current boundary memberships
        proj_q = select(ReportingProject).where(ReportingProject.id == project_id)
        proj = (await self.session.execute(proj_q)).scalar_one_or_none()
        if not proj:
            return {"added": [], "removed": [], "changed": []}

        current_boundary_id = proj.boundary_definition_id
        boundary_names = {}
        boundary_rows = await self.session.execute(
            select(BoundaryDefinition).where(BoundaryDefinition.id.in_([bid for bid in (current_boundary_id, new_boundary_id) if bid]))
        )
        boundary_names = {boundary.id: boundary.name for boundary in boundary_rows.scalars().all()}

        # Get current entities
        current_entities = set()
        if current_boundary_id:
            q = select(BoundaryMembership.entity_id).where(
                BoundaryMembership.boundary_definition_id == current_boundary_id,
                BoundaryMembership.included == True,
            )
            result = await self.session.execute(q)
            current_entities = {r[0] for r in result.all()}

        # Get new entities
        q = select(BoundaryMembership.entity_id).where(
            BoundaryMembership.boundary_definition_id == new_boundary_id,
            BoundaryMembership.included == True,
        )
        result = await self.session.execute(q)
        new_entities = {r[0] for r in result.all()}

        added = list(new_entities - current_entities)
        removed = list(current_entities - new_entities)

        assignments_result = await self.session.execute(
            select(MetricAssignment).where(MetricAssignment.reporting_project_id == project_id)
        )
        assignments = list(assignments_result.scalars().all())
        entity_ids = sorted(
            {
                entity_id
                for entity_id in [*current_entities, *new_entities]
                if entity_id is not None
            }
        )
        entity_names = {}
        if entity_ids:
            entity_result = await self.session.execute(
                select(CompanyEntity).where(CompanyEntity.id.in_(entity_ids))
            )
            entity_names = {entity.id: entity.name for entity in entity_result.scalars().all()}

        shared_element_ids = sorted({assignment.shared_element_id for assignment in assignments})
        shared_elements = {}
        if shared_element_ids:
            shared_result = await self.session.execute(
                select(SharedElement).where(SharedElement.id.in_(shared_element_ids))
            )
            shared_elements = {element.id: element for element in shared_result.scalars().all()}

        removed_assignments = []
        existing_entity_level_pairs = {
            (assignment.shared_element_id, assignment.entity_id)
            for assignment in assignments
            if assignment.entity_id is not None and assignment.facility_id is None
        }
        template_shared_elements = sorted(
            {
                assignment.shared_element_id
                for assignment in assignments
                if assignment.entity_id in current_entities and assignment.facility_id is None
            }
        )

        for assignment in assignments:
            scope_entity_id = assignment.facility_id or assignment.entity_id
            if scope_entity_id in removed:
                shared_element = shared_elements.get(assignment.shared_element_id)
                removed_assignments.append(
                    {
                        "assignment_id": assignment.id,
                        "shared_element_id": assignment.shared_element_id,
                        "shared_element_code": shared_element.code if shared_element else None,
                        "shared_element_name": shared_element.name if shared_element else None,
                        "entity_id": assignment.entity_id,
                        "entity_name": entity_names.get(assignment.entity_id),
                        "facility_id": assignment.facility_id,
                        "facility_name": entity_names.get(assignment.facility_id),
                    }
                )

        added_assignments = []
        for entity_id in sorted(added):
            for shared_element_id in template_shared_elements:
                if (shared_element_id, entity_id) in existing_entity_level_pairs:
                    continue
                shared_element = shared_elements.get(shared_element_id)
                added_assignments.append(
                    {
                        "shared_element_id": shared_element_id,
                        "shared_element_code": shared_element.code if shared_element else None,
                        "shared_element_name": shared_element.name if shared_element else None,
                        "entity_id": entity_id,
                        "entity_name": entity_names.get(entity_id),
                    }
                )

        return {
            "project_id": project_id,
            "current_boundary_id": current_boundary_id,
            "current_boundary_name": boundary_names.get(current_boundary_id),
            "new_boundary_id": new_boundary_id,
            "new_boundary_name": boundary_names.get(new_boundary_id),
            "added_entity_ids": added,
            "removed_entity_ids": removed,
            "added_count": len(added),
            "removed_count": len(removed),
            "assignment_changes": {
                "added_count": len(added_assignments),
                "removed_count": len(removed_assignments),
                "unchanged_count": max(len(assignments) - len(removed_assignments), 0),
                "added": added_assignments,
                "removed": removed_assignments,
            },
        }
