"""Impact analysis: preview effects of changing requirement items, mappings, or boundary."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.completeness import RequirementItemDataPoint
from app.db.models.data_point import DataPoint
from app.db.models.mapping import RequirementItemSharedElement
from app.db.models.project import ReportingProject, ReportingProjectStandard
from app.db.models.requirement_item import RequirementItem
from app.db.models.standard import DisclosureRequirement


class ImpactService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def preview_requirement_change(self, item_id: int) -> dict:
        """Preview impact of changing a requirement item."""
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

    async def preview_mapping_change(self, mapping_id: int) -> dict:
        """Preview impact of changing a mapping."""
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

    async def preview_boundary_change(self, project_id: int, new_boundary_id: int) -> dict:
        """Preview impact of changing boundary on a project."""
        from app.db.models.boundary import BoundaryMembership

        # Get current boundary memberships
        proj_q = select(ReportingProject).where(ReportingProject.id == project_id)
        proj = (await self.session.execute(proj_q)).scalar_one_or_none()
        if not proj:
            return {"added": [], "removed": [], "changed": []}

        current_boundary_id = proj.boundary_definition_id

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

        return {
            "project_id": project_id,
            "current_boundary_id": current_boundary_id,
            "new_boundary_id": new_boundary_id,
            "added_entity_ids": added,
            "removed_entity_ids": removed,
            "added_count": len(added),
            "removed_count": len(removed),
        }
