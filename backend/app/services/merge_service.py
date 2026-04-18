from collections import defaultdict

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import get_project_for_ctx
from app.core.dependencies import RequestContext
from app.db.models.boundary import BoundaryMembership
from app.db.models.company_entity import CompanyEntity
from app.db.models.completeness import RequirementItemStatus
from app.db.models.data_point import DataPoint
from app.db.models.evidence import DataPointEvidence
from app.db.models.mapping import RequirementItemSharedElement
from app.db.models.project import ReportingProject, ReportingProjectStandard
from app.db.models.requirement_item import RequirementItem
from app.db.models.shared_element import SharedElement
from app.db.models.standard import DisclosureRequirement, Standard
from app.policies.auth_policy import AuthPolicy


class MergeService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_merged_view(self, project_id: int, ctx: RequestContext | None = None) -> dict:
        if ctx:
            AuthPolicy.require_role(
                ctx, ["admin", "esg_manager", "auditor", "platform_admin"]
            )
            await get_project_for_ctx(
                self.session,
                project_id,
                ctx,
                allow_collectors=False,
                allow_reviewers=False,
            )

        project = await self._get_project(project_id)
        standards = await self._get_project_standards(project_id)
        if not standards:
            return {
                "standards": [],
                "elements": [],
                "summary": {
                    "common_elements": 0,
                    "unique_elements": 0,
                    "delta_count": 0,
                    "total": 0,
                    "common": 0,
                    "unique": 0,
                    "orphans": 0,
                    "standards": [],
                },
                "orphans": [],
            }

        matrix_rows = await self._get_matrix_rows(project_id, [std["standard_id"] for std in standards])
        latest_points = await self._get_latest_data_points(project_id)
        all_dps = [dp for dps in latest_points.values() for dp in dps]
        evidence_counts = await self._get_evidence_counts(all_dps)
        boundary_scope = await self._get_boundary_scope(project)
        orphans = await self._get_orphans(project_id, [std["standard_id"] for std in standards])

        elements: list[dict] = []
        common_count = 0
        unique_count = 0

        for shared_element_id, element_rows in matrix_rows.items():
            first_row = element_rows[0]
            element_dps = latest_points.get(shared_element_id, [])
            cells = [
                self._build_cell(row, element_dps, evidence_counts)
                for row in element_rows
            ]
            reuse_count = len(cells)
            if reuse_count > 1:
                common_count += 1
            else:
                unique_count += 1
            required_by = [row["standard_code"] for row in element_rows]

            elements.append(
                {
                    "element_id": shared_element_id,
                    "code": first_row["element_code"],
                    "name": first_row["element_name"],
                    "domain": first_row["domain"] or "general",
                    "reuse_count": reuse_count,
                    "is_common": reuse_count > 1,
                    "required_by": required_by,
                    "is_orphan": False,
                    "has_delta": False,
                    "delta_description": None,
                    "cells": cells,
                    "boundary_scope": boundary_scope,
                }
            )

        elements.sort(key=lambda element: (element["code"], element["name"]))
        summary = {
            "common_elements": common_count,
            "unique_elements": unique_count,
            "delta_count": 0,
            "total": len(elements),
            "common": common_count,
            "unique": unique_count,
            "orphans": len(orphans),
            "standards": [standard["code"] for standard in standards],
        }
        return {
            "standards": standards,
            "elements": elements,
            "summary": summary,
            "orphans": orphans,
        }

    async def _get_project(self, project_id: int) -> ReportingProject:
        result = await self.session.execute(
            select(ReportingProject).where(ReportingProject.id == project_id)
        )
        return result.scalar_one()

    async def _get_project_standards(self, project_id: int) -> list[dict]:
        coverage = await self.get_coverage(project_id)
        coverage_map = coverage["coverage"]

        rows = (
            await self.session.execute(
                select(Standard.id, Standard.code, Standard.name)
                .select_from(ReportingProjectStandard)
                .join(Standard, Standard.id == ReportingProjectStandard.standard_id)
                .where(ReportingProjectStandard.reporting_project_id == project_id)
                .order_by(Standard.code)
            )
        ).all()

        return [
            {
                "standard_id": standard_id,
                "code": code,
                "name": name,
                "coverage_pct": coverage_map.get(code, {}).get("completion_percent", 0.0),
            }
            for standard_id, code, name in rows
        ]

    async def _get_matrix_rows(self, project_id: int, standard_ids: list[int]) -> dict[int, list[dict]]:
        rows = (
            await self.session.execute(
                select(
                    Standard.id,
                    Standard.code,
                    Standard.name,
                    RequirementItem.id,
                    RequirementItem.item_code,
                    RequirementItem.name,
                    RequirementItemSharedElement.shared_element_id,
                    SharedElement.code,
                    SharedElement.name,
                    SharedElement.concept_domain,
                    RequirementItemStatus.status,
                )
                .select_from(ReportingProjectStandard)
                .join(Standard, Standard.id == ReportingProjectStandard.standard_id)
                .join(DisclosureRequirement, DisclosureRequirement.standard_id == Standard.id)
                .join(RequirementItem, RequirementItem.disclosure_requirement_id == DisclosureRequirement.id)
                .join(
                    RequirementItemSharedElement,
                    RequirementItemSharedElement.requirement_item_id == RequirementItem.id,
                )
                .join(SharedElement, SharedElement.id == RequirementItemSharedElement.shared_element_id)
                .outerjoin(
                    RequirementItemStatus,
                    and_(
                        RequirementItemStatus.reporting_project_id == project_id,
                        RequirementItemStatus.requirement_item_id == RequirementItem.id,
                    ),
                )
                .where(
                    ReportingProjectStandard.reporting_project_id == project_id,
                    Standard.id.in_(standard_ids),
                )
                .order_by(SharedElement.code, Standard.code, RequirementItem.id)
            )
        ).all()

        grouped: dict[tuple[int, int], dict] = {}
        element_rows: dict[int, list[dict]] = defaultdict(list)

        for (
            standard_id,
            standard_code,
            standard_name,
            requirement_item_id,
            item_code,
            item_name,
            shared_element_id,
            element_code,
            element_name,
            domain,
            item_status,
        ) in rows:
            key = (shared_element_id, standard_id)
            if key not in grouped:
                grouped[key] = {
                    "standard_id": standard_id,
                    "standard_code": standard_code,
                    "standard_name": standard_name,
                    "shared_element_id": shared_element_id,
                    "element_code": element_code,
                    "element_name": element_name,
                    "domain": domain,
                    "statuses": [],
                    "requirements": [],
                }
                element_rows[shared_element_id].append(grouped[key])

            grouped[key]["statuses"].append(item_status or "missing")
            grouped[key]["requirements"].append(
                f"{item_code or f'ITEM-{requirement_item_id}'} — {item_name}"
            )

        return element_rows

    async def _get_latest_data_points(
        self, project_id: int
    ) -> dict[int, list[DataPoint]]:
        """Return ALL data points per shared_element_id, grouped and sorted.

        Returns a dict of ``{shared_element_id: [dp1, dp2, ...]}`` where each
        list is sorted by entity_id then updated_at descending.  This preserves
        the multi-entity picture so the merge view can show aggregated state
        (e.g. "3 data points / 2 entities") instead of a single arbitrary DP.
        """
        rows = (
            await self.session.execute(
                select(DataPoint)
                .where(DataPoint.reporting_project_id == project_id)
                .order_by(
                    DataPoint.shared_element_id,
                    DataPoint.entity_id,
                    DataPoint.updated_at.desc(),
                    DataPoint.id.desc(),
                )
            )
        ).scalars().all()

        grouped: dict[int, list[DataPoint]] = defaultdict(list)
        for data_point in rows:
            grouped[data_point.shared_element_id].append(data_point)
        return dict(grouped)

    async def _get_evidence_counts(self, data_points: list[DataPoint]) -> dict[int, int]:
        if not data_points:
            return {}
        rows = (
            await self.session.execute(
                select(DataPointEvidence.data_point_id).where(
                    DataPointEvidence.data_point_id.in_([data_point.id for data_point in data_points])
                )
            )
        ).all()
        counts: dict[int, int] = defaultdict(int)
        for (data_point_id,) in rows:
            counts[data_point_id] += 1
        return counts

    async def _get_orphans(self, project_id: int, standard_ids: list[int]) -> list[dict]:
        rows = (
            await self.session.execute(
                select(
                    RequirementItem.id,
                    RequirementItem.item_code,
                    RequirementItem.name,
                    Standard.code,
                    Standard.name,
                    DisclosureRequirement.code,
                    DisclosureRequirement.title,
                )
                .select_from(ReportingProjectStandard)
                .join(Standard, Standard.id == ReportingProjectStandard.standard_id)
                .join(DisclosureRequirement, DisclosureRequirement.standard_id == Standard.id)
                .join(RequirementItem, RequirementItem.disclosure_requirement_id == DisclosureRequirement.id)
                .outerjoin(
                    RequirementItemSharedElement,
                    RequirementItemSharedElement.requirement_item_id == RequirementItem.id,
                )
                .where(
                    ReportingProjectStandard.reporting_project_id == project_id,
                    Standard.id.in_(standard_ids),
                    RequirementItemSharedElement.shared_element_id.is_(None),
                )
                .order_by(Standard.code, DisclosureRequirement.code, RequirementItem.id)
            )
        ).all()

        return [
            {
                "requirement_item_id": item_id,
                "item_code": item_code or f"ITEM-{item_id}",
                "name": item_name,
                "standard_code": standard_code,
                "standard_name": standard_name,
                "disclosure_code": disclosure_code,
                "disclosure_title": disclosure_title,
            }
            for (
                item_id,
                item_code,
                item_name,
                standard_code,
                standard_name,
                disclosure_code,
                disclosure_title,
            ) in rows
        ]

    async def _get_boundary_scope(self, project: ReportingProject) -> dict | None:
        if not project.boundary_definition_id:
            return None

        rows = (
            await self.session.execute(
                select(
                    BoundaryMembership.entity_id,
                    CompanyEntity.name,
                    BoundaryMembership.included,
                    BoundaryMembership.consolidation_method,
                )
                .join(CompanyEntity, CompanyEntity.id == BoundaryMembership.entity_id)
                .where(BoundaryMembership.boundary_definition_id == project.boundary_definition_id)
                .order_by(CompanyEntity.name)
            )
        ).all()

        methods = {method for *_rest, method in rows if method}
        consolidation_method = methods.pop() if len(methods) == 1 else "mixed"
        return {
            "entities": [
                {
                    "entity_id": entity_id,
                    "name": name,
                    "included": included,
                }
                for entity_id, name, included, _method in rows
            ],
            "consolidation_method": consolidation_method,
        }

    def _build_cell(
        self,
        row: dict,
        data_points: list[DataPoint],
        evidence_counts: dict[int, int],
    ) -> dict:
        statuses = row["statuses"]
        status = self._collapse_status(statuses)
        evidence_status = "none"
        current_value = None
        entity_scope = None
        data_point_count = len(data_points)
        entity_ids: set[int] = set()

        if data_points:
            # Show the first (latest) DP's value as primary
            primary_dp = data_points[0]
            if primary_dp.numeric_value is not None:
                current_value = f"{float(primary_dp.numeric_value):g} {primary_dp.unit_code or ''}".strip()
            elif primary_dp.text_value:
                current_value = primary_dp.text_value

            # Aggregate evidence status across all DPs
            total_with_evidence = sum(
                1 for dp in data_points if evidence_counts.get(dp.id, 0) > 0
            )
            if total_with_evidence == data_point_count:
                evidence_status = "attached"
            elif total_with_evidence > 0:
                evidence_status = "partial"
            else:
                evidence_status = "pending"

            # Collect distinct entity IDs
            entity_ids = {dp.entity_id for dp in data_points if dp.entity_id}

            if len(entity_ids) > 1:
                entity_scope = f"{len(entity_ids)} entities"
            elif len(entity_ids) == 1:
                entity_scope = f"Entity #{entity_ids.pop()}"

        if len(set(statuses)) == 1:
            binding_type = "full"
        elif status == "partial":
            binding_type = "partial"
        else:
            binding_type = "derived"

        return {
            "standard_id": row["standard_id"],
            "status": status,
            "binding_type": binding_type,
            "requirement_details": "\n".join(row["requirements"]),
            "current_value": current_value,
            "evidence_status": evidence_status,
            "entity_scope": entity_scope,
            "data_point_count": data_point_count,
        }

    @staticmethod
    def _collapse_status(statuses: list[str]) -> str:
        normalized = [status for status in statuses if status != "not_applicable"]
        if not normalized:
            return "missing"
        if all(status == "complete" for status in normalized):
            return "complete"
        if all(status == "missing" for status in normalized):
            return "missing"
        return "partial"

    async def get_coverage(self, project_id: int, ctx: RequestContext | None = None) -> dict:
        """Coverage per standard."""
        if ctx:
            AuthPolicy.require_role(
                ctx, ["admin", "esg_manager", "auditor", "platform_admin"]
            )
            await get_project_for_ctx(
                self.session,
                project_id,
                ctx,
                allow_collectors=False,
                allow_reviewers=False,
            )

        rows = (
            await self.session.execute(
                select(
                    Standard.id,
                    Standard.code,
                    RequirementItem.id,
                    RequirementItemStatus.status,
                )
                .select_from(ReportingProjectStandard)
                .join(Standard, Standard.id == ReportingProjectStandard.standard_id)
                .join(DisclosureRequirement, DisclosureRequirement.standard_id == Standard.id)
                .join(RequirementItem, RequirementItem.disclosure_requirement_id == DisclosureRequirement.id)
                .outerjoin(
                    RequirementItemStatus,
                    and_(
                        RequirementItemStatus.reporting_project_id == project_id,
                        RequirementItemStatus.requirement_item_id == RequirementItem.id,
                    ),
                )
                .where(
                    ReportingProjectStandard.reporting_project_id == project_id,
                    RequirementItem.is_required == True,
                )
                .order_by(Standard.id, RequirementItem.id)
            )
        ).all()

        coverage: dict[str, dict] = {}
        for standard_id, standard_code, _item_id, item_status in rows:
            bucket = coverage.setdefault(
                standard_code,
                {
                    "standard_id": standard_id,
                    "total_items": 0,
                    "complete_items": 0,
                    "partial_items": 0,
                    "missing_items": 0,
                    "completion_percent": 0.0,
                },
            )
            status = item_status or "missing"
            if status == "not_applicable":
                continue
            bucket["total_items"] += 1
            if status == "complete":
                bucket["complete_items"] += 1
            elif status == "partial":
                bucket["partial_items"] += 1
            else:
                bucket["missing_items"] += 1

        for bucket in coverage.values():
            total_items = bucket["total_items"]
            bucket["completion_percent"] = round(
                (bucket["complete_items"] / total_items) * 100, 1
            ) if total_items else 0.0

        return {"project_id": project_id, "coverage": coverage}
