from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.assignment_sla import (
    assignment_completed,
    assignment_matches_data_point,
    resolve_assignment_sla,
)
from app.core.access import get_project_for_ctx
from app.core.dependencies import RequestContext
from app.db.models.boundary import BoundaryDefinition, BoundaryMembership
from app.db.models.boundary_snapshot import BoundarySnapshot
from app.db.models.completeness import RequirementItemStatus
from app.db.models.company_entity import CompanyEntity
from app.db.models.data_point import DataPoint
from app.db.models.project import MetricAssignment
from app.db.models.shared_element import SharedElement
from app.db.models.user import User
from app.repositories.completeness_repo import CompletenessRepository
from app.services.impact_service import ImpactService
from app.services.merge_service import MergeService


class DashboardService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.completeness_repo = CompletenessRepository(session)
        self.merge_service = MergeService(session)
        self.impact_service = ImpactService(session)

    async def _get_project(self, project_id: int, ctx: RequestContext):
        return await get_project_for_ctx(self.session, project_id, ctx)

    async def _item_status_counts(self, project_id: int) -> tuple[dict[str, int], int, float]:
        rows = (
            await self.session.execute(
                select(RequirementItemStatus.status, RequirementItemStatus.requirement_item_id)
                .where(RequirementItemStatus.reporting_project_id == project_id)
            )
        ).all()
        counts = {"complete": 0, "partial": 0, "missing": 0, "not_applicable": 0}
        for status, _item_id in rows:
            counts[status] = counts.get(status, 0) + 1
        total = counts["complete"] + counts["partial"] + counts["missing"]
        percent = round((counts["complete"] / total) * 100, 1) if total else 0.0
        return counts, total, percent

    async def _data_point_status_counts(self, project_id: int) -> dict[str, int]:
        rows = (
            await self.session.execute(
                select(DataPoint.status, DataPoint.id).where(DataPoint.reporting_project_id == project_id)
            )
        ).all()
        counts: dict[str, int] = {}
        for status, _point_id in rows:
            counts[status] = counts.get(status, 0) + 1
        return counts

    async def _load_assignments_and_points(
        self, project_id: int
    ) -> tuple[list[MetricAssignment], list[DataPoint]]:
        assignments = list(
            (
                await self.session.execute(
                    select(MetricAssignment).where(MetricAssignment.reporting_project_id == project_id)
                )
            ).scalars().all()
        )
        data_points = list(
            (
                await self.session.execute(
                    select(DataPoint).where(DataPoint.reporting_project_id == project_id)
                )
            ).scalars().all()
        )
        return assignments, data_points

    async def _build_standard_progress(self, project_id: int) -> list[dict]:
        standards = await self.completeness_repo.list_project_standards(project_id)
        progress = []
        for standard_id, standard_code, standard_name in standards:
            items_with_disclosures = await self.completeness_repo.list_project_items(project_id, standard_id)
            item_ids = [item.id for item, _disclosure in items_with_disclosures]
            statuses = await self.completeness_repo.list_project_item_statuses(project_id, item_ids)
            status_by_item = {status.requirement_item_id: status.status for status in statuses}

            complete = partial = missing = 0
            for item_id in item_ids:
                status = status_by_item.get(item_id, "missing")
                if status == "not_applicable":
                    continue
                if status == "complete":
                    complete += 1
                elif status == "partial":
                    partial += 1
                else:
                    missing += 1
            total = complete + partial + missing
            progress.append(
                {
                    "standard_id": standard_id,
                    "standard": standard_code,
                    "standard_name": standard_name,
                    "completion_percent": round((complete / total) * 100, 1) if total else 0.0,
                    "complete_items": complete,
                    "partial_items": partial,
                    "missing_items": missing,
                    "total_items": total,
                }
            )
        return progress

    async def _build_disclosure_progress(self, project_id: int) -> list[dict]:
        items_with_disclosures = await self.completeness_repo.list_project_items(project_id)
        item_ids = [item.id for item, _disclosure in items_with_disclosures]
        statuses = await self.completeness_repo.list_project_item_statuses(project_id, item_ids)
        status_by_item = {status.requirement_item_id: status.status for status in statuses}

        disclosure_groups: dict[int, dict] = {}
        for item, disclosure in items_with_disclosures:
            bucket = disclosure_groups.setdefault(
                disclosure.id,
                {
                    "disclosure_id": disclosure.id,
                    "disclosure_code": disclosure.code,
                    "disclosure_title": disclosure.title,
                    "standard_id": disclosure.standard_id,
                    "complete_items": 0,
                    "partial_items": 0,
                    "missing_items": 0,
                },
            )
            status = status_by_item.get(item.id, "missing")
            if status == "not_applicable":
                continue
            if status == "complete":
                bucket["complete_items"] += 1
            elif status == "partial":
                bucket["partial_items"] += 1
            else:
                bucket["missing_items"] += 1

        disclosures = []
        for bucket in disclosure_groups.values():
            total = bucket["complete_items"] + bucket["partial_items"] + bucket["missing_items"]
            if bucket["missing_items"]:
                status = "missing"
            elif bucket["partial_items"]:
                status = "partial"
            else:
                status = "complete"
            disclosures.append(
                {
                    **bucket,
                    "status": status,
                    "completion_percent": round((bucket["complete_items"] / total) * 100, 1) if total else 0.0,
                    "total_items": total,
                }
            )
        disclosures.sort(key=lambda item: (item["disclosure_code"], item["disclosure_id"]))
        return disclosures

    async def _build_assignment_context(
        self, assignments: list[MetricAssignment]
    ) -> tuple[dict[int, SharedElement], dict[int, CompanyEntity], dict[int, User]]:
        shared_element_ids = sorted({assignment.shared_element_id for assignment in assignments})
        scoped_entity_ids = sorted(
            {
                scoped_id
                for assignment in assignments
                for scoped_id in (assignment.entity_id, assignment.facility_id)
                if scoped_id is not None
            }
        )
        user_ids = sorted(
            {
                user_id
                for assignment in assignments
                for user_id in (
                    assignment.collector_id,
                    assignment.reviewer_id,
                    assignment.backup_collector_id,
                )
                if user_id is not None
            }
        )

        shared_elements = {}
        if shared_element_ids:
            shared_elements = {
                element.id: element
                for element in (
                    await self.session.execute(
                        select(SharedElement).where(SharedElement.id.in_(shared_element_ids))
                    )
                ).scalars().all()
            }

        entities = {}
        if scoped_entity_ids:
            entities = {
                entity.id: entity
                for entity in (
                    await self.session.execute(
                        select(CompanyEntity).where(CompanyEntity.id.in_(scoped_entity_ids))
                    )
                ).scalars().all()
            }

        users = {}
        if user_ids:
            users = {
                user.id: user
                for user in (
                    await self.session.execute(select(User).where(User.id.in_(user_ids)))
                ).scalars().all()
            }
        return shared_elements, entities, users

    async def _build_assignment_analytics(
        self,
        project_id: int,
        assignments: list[MetricAssignment],
        data_points: list[DataPoint],
    ) -> tuple[dict[str, int], list[dict], list[dict]]:
        today = datetime.now(timezone.utc).date()
        sla_counts = {
            "on_track": 0,
            "warning": 0,
            "due_today": 0,
            "overdue": 0,
            "breach_level_1": 0,
            "breach_level_2": 0,
            "completed": 0,
            "no_deadline": 0,
        }
        shared_elements, entities, users = await self._build_assignment_context(assignments)
        priority_tasks = []
        user_progress: dict[tuple[int, str], dict] = {}

        severity_rank = {
            "breach_level_2": 0,
            "breach_level_1": 1,
            "overdue": 2,
            "due_today": 3,
            "warning": 4,
            "on_track": 5,
            "no_deadline": 6,
            "completed": 7,
        }

        for assignment in assignments:
            matching_points = [
                point for point in data_points if assignment_matches_data_point(assignment, point)
            ]
            completed = assignment_completed(assignment, matching_points)
            sla_state = resolve_assignment_sla(
                deadline=assignment.deadline,
                escalation_after_days=assignment.escalation_after_days,
                completed=completed,
                today=today,
            )
            sla_counts[sla_state.status] = sla_counts.get(sla_state.status, 0) + 1

            shared_element = shared_elements.get(assignment.shared_element_id)
            entity = entities.get(assignment.entity_id) if assignment.entity_id is not None else None
            facility = entities.get(assignment.facility_id) if assignment.facility_id is not None else None

            for role, user_id in (("collector", assignment.collector_id), ("reviewer", assignment.reviewer_id)):
                if user_id is None:
                    continue
                user = users.get(user_id)
                bucket = user_progress.setdefault(
                    (user_id, role),
                    {
                        "user_id": user_id,
                        "name": user.full_name if user else f"User {user_id}",
                        "role": role,
                        "total_assignments": 0,
                        "completed_assignments": 0,
                        "overdue_assignments": 0,
                        "warning_assignments": 0,
                        "due_today_assignments": 0,
                    },
                )
                bucket["total_assignments"] += 1
                if sla_state.status == "completed":
                    bucket["completed_assignments"] += 1
                if sla_state.status in {"overdue", "breach_level_1", "breach_level_2"}:
                    bucket["overdue_assignments"] += 1
                if sla_state.status == "warning":
                    bucket["warning_assignments"] += 1
                if sla_state.status == "due_today":
                    bucket["due_today_assignments"] += 1

            if sla_state.status not in {"completed", "on_track", "no_deadline"}:
                priority_tasks.append(
                    {
                        "assignment_id": assignment.id,
                        "shared_element_id": assignment.shared_element_id,
                        "shared_element_code": shared_element.code if shared_element else None,
                        "shared_element_name": shared_element.name if shared_element else None,
                        "collector_id": assignment.collector_id,
                        "collector_name": users.get(assignment.collector_id).full_name
                        if assignment.collector_id in users
                        else None,
                        "reviewer_id": assignment.reviewer_id,
                        "reviewer_name": users.get(assignment.reviewer_id).full_name
                        if assignment.reviewer_id in users
                        else None,
                        "entity_id": assignment.entity_id,
                        "entity_name": entity.name if entity else None,
                        "facility_id": assignment.facility_id,
                        "facility_name": facility.name if facility else None,
                        "deadline": assignment.deadline.isoformat() if assignment.deadline else None,
                        "sla_status": sla_state.status,
                        "days_overdue": sla_state.days_overdue,
                        "days_until_deadline": sla_state.days_until_deadline,
                    }
                )

        for bucket in user_progress.values():
            total_assignments = bucket["total_assignments"]
            bucket["completion_percent"] = round(
                (bucket["completed_assignments"] / total_assignments) * 100, 1
            ) if total_assignments else 0.0

        priority_tasks.sort(
            key=lambda task: (
                severity_rank.get(task["sla_status"], 99),
                -(task["days_overdue"] or 0),
                task["days_until_deadline"] if task["days_until_deadline"] is not None else 9999,
                task["assignment_id"],
            )
        )
        return sla_counts, priority_tasks[:10], list(user_progress.values())

    async def _build_boundary_summary(
        self,
        project,
        assignments: list[MetricAssignment],
        data_points: list[DataPoint],
    ) -> tuple[dict | None, dict | None]:
        if not project.boundary_definition_id:
            return None, None

        boundary = (
            await self.session.execute(
                select(BoundaryDefinition).where(BoundaryDefinition.id == project.boundary_definition_id)
            )
        ).scalar_one_or_none()
        if not boundary:
            return None, None

        memberships = list(
            (
                await self.session.execute(
                    select(BoundaryMembership).where(
                        BoundaryMembership.boundary_definition_id == project.boundary_definition_id
                    )
                )
            ).scalars().all()
        )
        included_entity_ids = {membership.entity_id for membership in memberships if membership.included}
        excluded_entity_ids = {membership.entity_id for membership in memberships if not membership.included}
        snapshot = (
            await self.session.execute(
                select(BoundarySnapshot).where(BoundarySnapshot.reporting_project_id == project.id)
            )
        ).scalar_one_or_none()

        last_updated_by = None
        if snapshot and snapshot.created_by:
            user = (
                await self.session.execute(select(User).where(User.id == snapshot.created_by))
            ).scalar_one_or_none()
            last_updated_by = user.full_name if user else None

        boundary_summary = {
            "selected": boundary.name,
            "boundary_type": boundary.boundary_type,
            "entities_in_scope": len(included_entity_ids),
            "excluded_entities": len(excluded_entity_ids),
            "manual_overrides": sum(1 for membership in memberships if membership.inclusion_source == "manual"),
            "snapshot_status": (
                "locked"
                if snapshot and snapshot.boundary_definition_id == project.boundary_definition_id
                else "missing"
            ),
            "snapshot_date": snapshot.created_at.isoformat() if snapshot and snapshot.created_at else None,
            "last_updated_by": last_updated_by,
        }

        default_boundary_id = (
            await self.session.execute(
                select(BoundaryDefinition.id).where(
                    BoundaryDefinition.organization_id == project.organization_id,
                    BoundaryDefinition.is_default == True,
                )
            )
        ).scalar_one_or_none()

        matching_points_by_assignment = {
            assignment.id: [
                point for point in data_points if assignment_matches_data_point(assignment, point)
            ]
            for assignment in assignments
        }

        metrics_affected_by_boundary_change = 0
        missing_due_to_excluded_entities = 0
        if default_boundary_id and default_boundary_id != project.boundary_definition_id:
            preview = await self.impact_service.preview_boundary_change(project.id, default_boundary_id)
            metrics_affected_by_boundary_change = (
                preview["assignment_changes"]["added_count"] + preview["assignment_changes"]["removed_count"]
            )
            removed_assignment_ids = {
                item["assignment_id"] for item in preview["assignment_changes"]["removed"]
            }
            missing_due_to_excluded_entities = sum(
                1
                for assignment in assignments
                if assignment.id in removed_assignment_ids
                and not assignment_completed(assignment, matching_points_by_assignment.get(assignment.id, []))
            )

        ownerless_entities = 0
        for entity_id in included_entity_ids:
            scoped_assignments = [
                assignment
                for assignment in assignments
                if (assignment.facility_id or assignment.entity_id) == entity_id
            ]
            if not scoped_assignments:
                ownerless_entities += 1
                continue
            if not any(
                assignment.collector_id is not None or assignment.backup_collector_id is not None
                for assignment in scoped_assignments
            ):
                ownerless_entities += 1

        boundary_impact = {
            "missing_due_to_excluded_entities": missing_due_to_excluded_entities,
            "metrics_affected_by_boundary_change": metrics_affected_by_boundary_change,
            "entities_without_assigned_owners": ownerless_entities,
        }
        return boundary_summary, boundary_impact

    async def get_project_progress(self, project_id: int, ctx: RequestContext) -> dict:
        project = await self._get_project(project_id, ctx)
        item_counts, total_items, overall_completion_percent = await self._item_status_counts(project_id)
        data_point_statuses = await self._data_point_status_counts(project_id)
        assignments, data_points = await self._load_assignments_and_points(project_id)
        standard_progress = await self._build_standard_progress(project_id)
        disclosure_progress = await self._build_disclosure_progress(project_id)
        sla_counts, priority_tasks, user_progress = await self._build_assignment_analytics(
            project_id,
            assignments,
            data_points,
        )
        boundary_summary, boundary_impact = await self._build_boundary_summary(
            project,
            assignments,
            data_points,
        )
        merge_summary = (await self.merge_service.get_merged_view(project_id, ctx))["summary"]
        merge_coverage = (await self.merge_service.get_coverage(project_id, ctx))["coverage"]

        overdue_assignments = (
            sla_counts["overdue"] + sla_counts["breach_level_1"] + sla_counts["breach_level_2"]
        )
        issues_count = item_counts["missing"] + item_counts["partial"]

        return {
            "project_id": project_id,
            "project_status": project.status,
            "overall_completion_percent": overall_completion_percent,
            "issues_count": issues_count,
            "overdue_assignments": overdue_assignments,
            "item_statuses": {
                "complete": item_counts["complete"],
                "partial": item_counts["partial"],
                "missing": item_counts["missing"],
                "total": total_items,
            },
            "data_point_statuses": data_point_statuses,
            "standards_progress": standard_progress,
            "coverage_by_standard": standard_progress,
            "coverage_by_disclosure": disclosure_progress,
            "coverage_by_user": user_progress,
            "coverage_heatmap": disclosure_progress,
            "sla_counts": sla_counts,
            "priority_tasks": priority_tasks,
            "breached_assignments": [
                task for task in priority_tasks if task["sla_status"] in {"breach_level_1", "breach_level_2"}
            ],
            "boundary_summary": boundary_summary,
            "boundary_impact": boundary_impact,
            "merge_summary": merge_summary,
            "merge_coverage": merge_coverage,
        }

    async def get_project_priority_tasks(self, project_id: int, ctx: RequestContext) -> dict:
        overview = await self.get_project_progress(project_id, ctx)
        return {"project_id": project_id, "items": overview["priority_tasks"]}
