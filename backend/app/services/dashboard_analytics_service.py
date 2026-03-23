from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import assignment_matches_data_point, get_project_for_ctx
from app.core.assignment_sla import assignment_completed, resolve_assignment_sla
from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.db.models.audit_log import AuditLog
from app.db.models.completeness import RequirementItemStatus
from app.db.models.data_point import DataPoint
from app.db.models.project import MetricAssignment
from app.db.models.role_binding import RoleBinding
from app.db.models.user import User


class DashboardAnalyticsService:
    DATA_POINT_ACTIONS = {
        "data_point_created": "created_data_points",
        "data_point_submitted": "submitted_data_points",
        "data_point_approved": "approved_data_points",
        "data_point_rejected": "rejected_data_points",
        "data_point_revision_requested": "revision_requests",
    }
    PROJECT_ACTIONS = {
        "project_started": "project_started",
        "project_in_review": "project_in_review",
        "project_published": "project_published",
    }

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _require_analytics_access(ctx: RequestContext) -> None:
        if ctx.role not in ("admin", "esg_manager", "auditor", "platform_admin"):
            raise AppError("FORBIDDEN", 403, "Only admin, ESG manager, auditor, or platform admin can view analytics")

    @staticmethod
    def _aware(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    async def _get_project(self, project_id: int, ctx: RequestContext):
        self._require_analytics_access(ctx)
        return await get_project_for_ctx(
            self.session,
            project_id,
            ctx,
            allow_collectors=False,
            allow_reviewers=False,
        )

    async def get_project_trends(self, project_id: int, ctx: RequestContext, days: int = 30) -> dict:
        await self._get_project(project_id, ctx)
        effective_days = min(max(days, 1), 365)
        end_date = date.today()
        start_date = end_date - timedelta(days=effective_days - 1)
        start_dt = datetime.combine(start_date, time.min, tzinfo=timezone.utc)

        buckets = {}
        cursor = start_date
        while cursor <= end_date:
            key = cursor.isoformat()
            buckets[key] = {
                "date": key,
                "created_data_points": 0,
                "submitted_data_points": 0,
                "approved_data_points": 0,
                "rejected_data_points": 0,
                "revision_requests": 0,
                "complete_item_updates": 0,
                "partial_item_updates": 0,
                "missing_item_updates": 0,
                "project_started": 0,
                "project_in_review": 0,
                "project_published": 0,
            }
            cursor += timedelta(days=1)

        data_point_rows = (
            await self.session.execute(
                select(AuditLog.created_at, AuditLog.action)
                .join(DataPoint, DataPoint.id == AuditLog.entity_id)
                .where(
                    AuditLog.entity_type == "DataPoint",
                    DataPoint.reporting_project_id == project_id,
                    AuditLog.action.in_(tuple(self.DATA_POINT_ACTIONS.keys())),
                    AuditLog.created_at >= start_dt,
                )
            )
        ).all()
        for created_at, action in data_point_rows:
            key = self._aware(created_at).date().isoformat()
            if key in buckets:
                buckets[key][self.DATA_POINT_ACTIONS[action]] += 1

        project_rows = (
            await self.session.execute(
                select(AuditLog.created_at, AuditLog.action).where(
                    AuditLog.entity_type == "ReportingProject",
                    AuditLog.entity_id == project_id,
                    AuditLog.action.in_(tuple(self.PROJECT_ACTIONS.keys())),
                    AuditLog.created_at >= start_dt,
                )
            )
        ).all()
        for created_at, action in project_rows:
            key = self._aware(created_at).date().isoformat()
            if key in buckets:
                buckets[key][self.PROJECT_ACTIONS[action]] += 1

        status_rows = (
            await self.session.execute(
                select(RequirementItemStatus.updated_at, RequirementItemStatus.status).where(
                    RequirementItemStatus.reporting_project_id == project_id,
                    RequirementItemStatus.updated_at >= start_dt,
                )
            )
        ).all()
        for updated_at, status in status_rows:
            key = self._aware(updated_at).date().isoformat()
            if key not in buckets:
                continue
            if status == "complete":
                buckets[key]["complete_item_updates"] += 1
            elif status == "partial":
                buckets[key]["partial_item_updates"] += 1
            elif status == "missing":
                buckets[key]["missing_item_updates"] += 1

        series = [buckets[key] for key in sorted(buckets)]
        totals = {
            field: sum(item[field] for item in series)
            for field in (
                "created_data_points",
                "submitted_data_points",
                "approved_data_points",
                "rejected_data_points",
                "revision_requests",
                "complete_item_updates",
                "partial_item_updates",
                "missing_item_updates",
                "project_started",
                "project_in_review",
                "project_published",
            )
        }
        return {
            "project_id": project_id,
            "window": {
                "from": start_date.isoformat(),
                "to": end_date.isoformat(),
                "days": effective_days,
            },
            "series": series,
            "totals": totals,
        }

    async def get_project_activity(self, project_id: int, ctx: RequestContext) -> dict:
        project = await self._get_project(project_id, ctx)
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

        audit_rows = (
            await self.session.execute(
                select(AuditLog.user_id, AuditLog.action)
                .join(DataPoint, DataPoint.id == AuditLog.entity_id)
                .where(
                    AuditLog.entity_type == "DataPoint",
                    DataPoint.reporting_project_id == project_id,
                    AuditLog.user_id.is_not(None),
                    AuditLog.action.in_(tuple(self.DATA_POINT_ACTIONS.keys())),
                )
            )
        ).all()

        user_ids = {
            user_id
            for assignment in assignments
            for user_id in (
                assignment.collector_id,
                assignment.backup_collector_id,
                assignment.reviewer_id,
            )
            if user_id is not None
        }
        user_ids.update(user_id for user_id, _action in audit_rows if user_id is not None)

        users = {}
        if user_ids:
            users = {
                user.id: user
                for user in (
                    await self.session.execute(select(User).where(User.id.in_(sorted(user_ids))))
                ).scalars().all()
            }

        role_rows = []
        if user_ids:
            role_rows = (
                await self.session.execute(
                    select(RoleBinding.user_id, RoleBinding.role).where(
                        RoleBinding.scope_type == "organization",
                        RoleBinding.scope_id == project.organization_id,
                        RoleBinding.user_id.in_(sorted(user_ids)),
                    )
                )
            ).all()
        roles_by_user: dict[int, set[str]] = {}
        for user_id, role in role_rows:
            roles_by_user.setdefault(user_id, set()).add(role)

        activity = {}

        def ensure_bucket(user_id: int) -> dict:
            user = users.get(user_id)
            bucket = activity.setdefault(
                user_id,
                {
                    "user_id": user_id,
                    "name": user.full_name if user else f"User {user_id}",
                    "roles": sorted(roles_by_user.get(user_id, set())),
                    "created_data_points": 0,
                    "submitted_data_points": 0,
                    "approved_data_points": 0,
                    "rejected_data_points": 0,
                    "revision_requests": 0,
                    "assignments_owned": 0,
                    "backup_assignments": 0,
                    "reviews_assigned": 0,
                    "completed_assignments": 0,
                    "overdue_assignments": 0,
                    "warning_assignments": 0,
                    "due_today_assignments": 0,
                    "sla_tracked_assignments": 0,
                    "sla_compliant_assignments": 0,
                    "sla_compliance_percent": 0.0,
                },
            )
            return bucket

        for user_id, action in audit_rows:
            if user_id is None:
                continue
            ensure_bucket(user_id)[self.DATA_POINT_ACTIONS[action]] += 1

        overall_sla = {
            "total_assignments": len(assignments),
            "assignments_with_deadline": 0,
            "completed_assignments": 0,
            "on_track_assignments": 0,
            "warning_assignments": 0,
            "due_today_assignments": 0,
            "overdue_assignments": 0,
            "breach_level_1_assignments": 0,
            "breach_level_2_assignments": 0,
            "sla_compliance_percent": 0.0,
            "completion_percent": 0.0,
        }

        today = date.today()
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

            if assignment.collector_id is not None:
                collector = ensure_bucket(assignment.collector_id)
                collector["assignments_owned"] += 1
                if completed:
                    collector["completed_assignments"] += 1
                if assignment.deadline is not None:
                    collector["sla_tracked_assignments"] += 1
                    if sla_state.status in {"completed", "on_track", "warning", "due_today"}:
                        collector["sla_compliant_assignments"] += 1
                if sla_state.status in {"overdue", "breach_level_1", "breach_level_2"}:
                    collector["overdue_assignments"] += 1
                elif sla_state.status == "warning":
                    collector["warning_assignments"] += 1
                elif sla_state.status == "due_today":
                    collector["due_today_assignments"] += 1

            if assignment.backup_collector_id is not None:
                ensure_bucket(assignment.backup_collector_id)["backup_assignments"] += 1

            if assignment.reviewer_id is not None:
                ensure_bucket(assignment.reviewer_id)["reviews_assigned"] += 1

            if assignment.deadline is not None:
                overall_sla["assignments_with_deadline"] += 1
            if completed:
                overall_sla["completed_assignments"] += 1
            if sla_state.status == "on_track":
                overall_sla["on_track_assignments"] += 1
            elif sla_state.status == "warning":
                overall_sla["warning_assignments"] += 1
            elif sla_state.status == "due_today":
                overall_sla["due_today_assignments"] += 1
            elif sla_state.status == "overdue":
                overall_sla["overdue_assignments"] += 1
            elif sla_state.status == "breach_level_1":
                overall_sla["breach_level_1_assignments"] += 1
            elif sla_state.status == "breach_level_2":
                overall_sla["breach_level_2_assignments"] += 1

        for bucket in activity.values():
            tracked = bucket["sla_tracked_assignments"]
            bucket["sla_compliance_percent"] = round(
                (bucket["sla_compliant_assignments"] / tracked) * 100, 1
            ) if tracked else 0.0

        tracked_assignments = overall_sla["assignments_with_deadline"]
        compliant_assignments = (
            overall_sla["completed_assignments"]
            + overall_sla["on_track_assignments"]
            + overall_sla["warning_assignments"]
            + overall_sla["due_today_assignments"]
        )
        overall_sla["sla_compliance_percent"] = round(
            (compliant_assignments / tracked_assignments) * 100, 1
        ) if tracked_assignments else 0.0
        overall_sla["completion_percent"] = round(
            (overall_sla["completed_assignments"] / overall_sla["total_assignments"]) * 100, 1
        ) if overall_sla["total_assignments"] else 0.0

        return {
            "project_id": project_id,
            "project_status": project.status,
            "users": sorted(activity.values(), key=lambda item: (item["name"], item["user_id"])),
            "sla_summary": overall_sla,
        }
