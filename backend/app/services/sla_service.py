"""SLA breach detection and escalation service."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.assignment_sla import assignment_completed, assignment_matches_data_point, resolve_assignment_sla
from app.db.models.data_point import DataPoint
from app.db.models.project import MetricAssignment, ReportingProject
from app.db.models.role_binding import RoleBinding
from app.repositories.notification_repo import NotificationRepository
from app.services.notification_service import NotificationService


class SLAService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.notification_service = NotificationService(NotificationRepository(session))

    async def _notify_users(
        self,
        *,
        user_ids: list[int],
        org_id: int,
        type: str,
        title: str,
        message: str,
        entity_id: int,
        entity_type: str = "MetricAssignment",
        severity: str,
    ) -> None:
        for user_id in sorted({uid for uid in user_ids if uid}):
            await self.notification_service.notify(
                user_id=user_id,
                org_id=org_id,
                type=type,
                title=title,
                message=message,
                entity_type=entity_type,
                entity_id=entity_id,
                severity=severity,
            )

    async def _org_role_user_ids(self, org_id: int, roles: set[str]) -> list[int]:
        result = await self.session.execute(
            select(RoleBinding.user_id).where(
                RoleBinding.scope_type == "organization",
                RoleBinding.scope_id == org_id,
                RoleBinding.role.in_(roles),
            )
        )
        return sorted({row[0] for row in result.all()})

    async def _project_assigned_user_ids(self, project_id: int) -> list[int]:
        result = await self.session.execute(
            select(
                MetricAssignment.collector_id,
                MetricAssignment.reviewer_id,
                MetricAssignment.backup_collector_id,
            ).where(MetricAssignment.reporting_project_id == project_id)
        )
        return sorted(
            {
                user_id
                for row in result.all()
                for user_id in row
                if user_id
            }
        )

    async def check_sla_breaches(self) -> dict:
        """Check all assignments for SLA breaches. Run via cron/scheduled task."""
        today = datetime.now(timezone.utc).date()

        result = await self.session.execute(
            select(MetricAssignment).where(MetricAssignment.deadline.isnot(None))
        )
        assignments = list(result.scalars().all())
        project_ids = sorted({assignment.reporting_project_id for assignment in assignments})

        projects_by_id: dict[int, ReportingProject] = {}
        if project_ids:
            projects_result = await self.session.execute(
                select(ReportingProject).where(ReportingProject.id.in_(project_ids))
            )
            projects_by_id = {project.id: project for project in projects_result.scalars().all()}

        data_points_by_project: dict[int, list[DataPoint]] = {}
        if project_ids:
            points_result = await self.session.execute(
                select(DataPoint).where(DataPoint.reporting_project_id.in_(project_ids))
            )
            for point in points_result.scalars().all():
                data_points_by_project.setdefault(point.reporting_project_id, []).append(point)

        warnings = 0
        overdue = 0
        breach_l1 = 0
        breach_l2 = 0

        for assignment in assignments:
            project = projects_by_id.get(assignment.reporting_project_id)
            if not project:
                continue

            matching_points = [
                point
                for point in data_points_by_project.get(assignment.reporting_project_id, [])
                if assignment_matches_data_point(assignment, point)
            ]
            sla_state = resolve_assignment_sla(
                deadline=assignment.deadline,
                escalation_after_days=assignment.escalation_after_days,
                completed=assignment_completed(assignment, matching_points),
                today=today,
            )

            if sla_state.status in {"completed", "no_deadline", "on_track"}:
                continue

            if sla_state.status in {"warning", "due_today"}:
                warnings += 1
                if assignment.collector_id:
                    title = "Assignment deadline approaching" if sla_state.status == "warning" else "Assignment due today"
                    message = (
                        f"Assignment #{assignment.id} is due in {sla_state.days_until_deadline} days."
                        if sla_state.status == "warning"
                        else f"Assignment #{assignment.id} is due today."
                    )
                    await self._notify_users(
                        user_ids=[assignment.collector_id],
                        org_id=project.organization_id,
                        type="deadline_approaching",
                        title=title,
                        message=message,
                        entity_id=assignment.id,
                        severity="important",
                    )
                continue

            if sla_state.status == "overdue":
                overdue += 1
                await self._notify_users(
                    user_ids=[
                        assignment.collector_id,
                        *await self._org_role_user_ids(project.organization_id, {"esg_manager"}),
                    ],
                    org_id=project.organization_id,
                    type="assignment_overdue",
                    title="Assignment overdue",
                    message=f"Assignment #{assignment.id} is overdue by {sla_state.days_overdue} days.",
                    entity_id=assignment.id,
                    severity="critical",
                )
                continue

            if sla_state.status == "breach_level_1":
                breach_l1 += 1
                await self._notify_users(
                    user_ids=[
                        assignment.backup_collector_id,
                        *await self._org_role_user_ids(project.organization_id, {"esg_manager"}),
                    ],
                    org_id=project.organization_id,
                    type="sla_breach_level_1",
                    title="SLA breach level 1",
                    message=(
                        f"Assignment #{assignment.id} is overdue by {sla_state.days_overdue} days "
                        f"and requires escalation."
                    ),
                    entity_id=assignment.id,
                    severity="critical",
                )
                await self._notify_users(
                    user_ids=[assignment.backup_collector_id],
                    org_id=project.organization_id,
                    type="assignment_escalated",
                    title="Assignment escalated to backup owner",
                    message=(
                        f"Assignment #{assignment.id} was escalated to you after "
                        f"{sla_state.days_overdue} days overdue."
                    ),
                    entity_id=assignment.id,
                    severity="critical",
                )
                continue

            breach_l2 += 1
            await self._notify_users(
                user_ids=await self._org_role_user_ids(project.organization_id, {"admin"}),
                org_id=project.organization_id,
                type="sla_breach_level_2",
                title="SLA breach level 2",
                message=(
                    f"Assignment #{assignment.id} is overdue by {sla_state.days_overdue} days "
                    "and needs admin intervention."
                ),
                entity_id=assignment.id,
                severity="critical",
            )

        await self.session.flush()

        return {
            "checked": len(assignments),
            "warnings": warnings,
            "overdue": overdue,
            "breach_level_1": breach_l1,
            "breach_level_2": breach_l2,
        }

    async def check_project_deadlines(self) -> dict:
        today = datetime.now(timezone.utc).date()
        result = await self.session.execute(
            select(ReportingProject).where(
                ReportingProject.deadline.isnot(None),
                ReportingProject.status.in_(("active", "review")),
            )
        )
        projects = list(result.scalars().all())
        notifications_sent = 0

        for project in projects:
            if not project.deadline:
                continue
            days_until_deadline = (project.deadline - today).days
            if days_until_deadline not in {7, 3, 1}:
                continue

            user_ids = await self._project_assigned_user_ids(project.id)
            if not user_ids:
                continue

            await self._notify_users(
                user_ids=user_ids,
                org_id=project.organization_id,
                type="project_deadline_approaching",
                title="Project deadline approaching",
                message=(
                    f"Project '{project.name}' is due in {days_until_deadline} days."
                    if days_until_deadline > 1
                    else f"Project '{project.name}' is due tomorrow."
                ),
                entity_id=project.id,
                entity_type="ReportingProject",
                severity="important",
            )
            notifications_sent += 1

        await self.session.flush()
        return {"checked": len(projects), "notifications_sent": notifications_sent}
