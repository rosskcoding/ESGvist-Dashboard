"""SLA breach detection and escalation service."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.notification import Notification
from app.db.models.project import MetricAssignment


class SLAService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def check_sla_breaches(self) -> dict:
        """Check all assignments for SLA breaches. Run via cron/scheduled task."""
        now = datetime.now(timezone.utc).date()

        q = select(MetricAssignment).where(
            MetricAssignment.status != "completed",
            MetricAssignment.deadline.isnot(None),
        )
        result = await self.session.execute(q)
        assignments = list(result.scalars().all())

        warnings = 0
        breach_l1 = 0
        breach_l2 = 0

        for a in assignments:
            deadline = a.deadline if isinstance(a.deadline, datetime) else datetime.combine(
                a.deadline, datetime.min.time()
            ) if a.deadline else None

            if not deadline:
                continue

            deadline_date = deadline.date() if isinstance(deadline, datetime) else deadline
            days_overdue = (now - deadline_date).days

            if days_overdue >= 7:
                # Level 2: critical
                breach_l2 += 1
                await self._create_sla_notification(
                    a, "sla_breach_level_2",
                    f"Critical: assignment overdue by {days_overdue} days",
                    "critical",
                )
            elif days_overdue >= 3:
                # Level 1: escalation
                breach_l1 += 1
                await self._create_sla_notification(
                    a, "sla_breach_level_1",
                    f"Warning: assignment overdue by {days_overdue} days",
                    "important",
                )
            elif days_overdue >= -3 and days_overdue < 0:
                # Warning: approaching deadline
                warnings += 1
                await self._create_sla_notification(
                    a, "deadline_approaching",
                    f"Deadline in {abs(days_overdue)} days",
                    "info",
                )

        await self.session.flush()

        return {
            "checked": len(assignments),
            "warnings": warnings,
            "breach_level_1": breach_l1,
            "breach_level_2": breach_l2,
        }

    async def _create_sla_notification(
        self, assignment: MetricAssignment, type: str, message: str, severity: str
    ):
        if not assignment.collector_id:
            return

        n = Notification(
            organization_id=0,  # would resolve from project
            user_id=assignment.collector_id,
            type=type,
            title=f"SLA: {type.replace('_', ' ').title()}",
            message=message,
            entity_type="assignment",
            entity_id=assignment.id,
            severity=severity,
        )
        self.session.add(n)
