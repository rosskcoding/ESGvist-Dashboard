from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.completeness import RequirementItemStatus
from app.db.models.mapping import RequirementItemSharedElement
from app.db.models.project import ReportingProjectStandard
from app.db.models.requirement_item import RequirementItem
from app.db.models.shared_element import SharedElement
from app.db.models.standard import DisclosureRequirement, Standard


class MergeService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_merged_view(self, project_id: int) -> dict:
        """
        5-step merge algorithm:
        1. Collect all requirement_items from standards linked to project
        2. Group by shared_element_id
        3. Classify: common (2+ standards), unique, orphans
        4. Attach statuses
        5. Build response
        """
        # Step 1: Get project standards
        ps_q = select(ReportingProjectStandard).where(
            ReportingProjectStandard.reporting_project_id == project_id
        )
        ps_result = await self.session.execute(ps_q)
        project_standards = list(ps_result.scalars().all())
        standard_ids = [ps.standard_id for ps in project_standards]

        if not standard_ids:
            return {"elements": [], "summary": {"total": 0, "common": 0, "unique": 0, "orphans": 0}}

        # Get standard names
        std_q = select(Standard).where(Standard.id.in_(standard_ids))
        std_result = await self.session.execute(std_q)
        standards_map = {s.id: s.code for s in std_result.scalars().all()}

        # Step 1: Collect requirement items
        items_q = (
            select(RequirementItem, DisclosureRequirement.standard_id)
            .join(DisclosureRequirement)
            .where(DisclosureRequirement.standard_id.in_(standard_ids))
        )
        items_result = await self.session.execute(items_q)
        items_with_std = [(row[0], row[1]) for row in items_result.all()]

        # Step 2: Get mappings to shared elements
        item_ids = [item.id for item, _ in items_with_std]
        if not item_ids:
            return {"elements": [], "summary": {"total": 0, "common": 0, "unique": 0, "orphans": 0}}

        mappings_q = select(RequirementItemSharedElement).where(
            RequirementItemSharedElement.requirement_item_id.in_(item_ids)
        )
        mappings_result = await self.session.execute(mappings_q)
        mappings = list(mappings_result.scalars().all())

        # Build item→standard and item→shared_element maps
        item_to_std: dict[int, int] = {item.id: std_id for item, std_id in items_with_std}
        se_to_items: dict[int, list[int]] = {}
        mapped_items = set()

        for m in mappings:
            se_to_items.setdefault(m.shared_element_id, []).append(m.requirement_item_id)
            mapped_items.add(m.requirement_item_id)

        # Get shared element details
        se_ids = list(se_to_items.keys())
        if se_ids:
            se_q = select(SharedElement).where(SharedElement.id.in_(se_ids))
            se_result = await self.session.execute(se_q)
            se_map = {se.id: se for se in se_result.scalars().all()}
        else:
            se_map = {}

        # Step 3: Classify
        elements = []
        common_count = 0
        unique_count = 0

        for se_id, item_ids_list in se_to_items.items():
            se = se_map.get(se_id)
            if not se:
                continue

            required_by = list(set(
                standards_map.get(item_to_std.get(iid, 0), "")
                for iid in item_ids_list
                if item_to_std.get(iid)
            ))
            is_common = len(required_by) > 1

            if is_common:
                common_count += 1
            else:
                unique_count += 1

            elements.append({
                "shared_element_id": se.id,
                "code": se.code,
                "name": se.name,
                "concept_domain": se.concept_domain,
                "required_by": required_by,
                "is_common": is_common,
                "requirement_item_ids": item_ids_list,
            })

        # Step 4: Orphans (items without shared element mapping)
        orphan_ids = [item.id for item, _ in items_with_std if item.id not in mapped_items]
        orphans = []
        for item, std_id in items_with_std:
            if item.id in mapped_items:
                continue
            orphans.append({
                "requirement_item_id": item.id,
                "name": item.name,
                "standard": standards_map.get(std_id, ""),
            })

        return {
            "elements": elements,
            "orphans": orphans,
            "summary": {
                "total": len(elements) + len(orphans),
                "common": common_count,
                "unique": unique_count,
                "orphans": len(orphans),
                "standards": list(standards_map.values()),
            },
        }

    async def get_coverage(self, project_id: int) -> dict:
        """Coverage per standard."""
        merged = await self.get_merged_view(project_id)
        standards = merged["summary"].get("standards", [])

        coverage = {}
        for std in standards:
            total = sum(1 for e in merged["elements"] if std in e["required_by"])
            # Simplified: count elements assigned to this standard
            coverage[std] = {"total_elements": total}

        return {"project_id": project_id, "coverage": coverage}
