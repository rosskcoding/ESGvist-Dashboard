from dataclasses import dataclass
from datetime import date
from typing import Any


DEFAULT_ASSIGNMENT_ESCALATION_AFTER_DAYS = 3
ASSIGNMENT_WARNING_WINDOW_DAYS = 3
ASSIGNMENT_LEVEL_TWO_DAYS = 7


@dataclass(frozen=True)
class AssignmentSLAState:
    status: str
    days_until_deadline: int | None
    days_overdue: int
    escalation_after_days: int


def normalize_escalation_after_days(value: int | None) -> int:
    if value is None or value < 1:
        return DEFAULT_ASSIGNMENT_ESCALATION_AFTER_DAYS
    return value


def assignment_matches_data_point(assignment: Any, data_point: Any) -> bool:
    return (
        data_point.shared_element_id == assignment.shared_element_id
        and (assignment.entity_id is None or data_point.entity_id == assignment.entity_id)
        and (assignment.facility_id is None or data_point.facility_id == assignment.facility_id)
    )


def assignment_completed(assignment: Any, matching_points: list[Any]) -> bool:
    if getattr(assignment, "status", None) == "completed":
        return True
    if not matching_points:
        return False
    return all(getattr(point, "status", None) == "approved" for point in matching_points)


def resolve_assignment_sla(
    *,
    deadline: date | None,
    escalation_after_days: int | None,
    completed: bool,
    today: date | None = None,
) -> AssignmentSLAState:
    effective_today = today or date.today()
    effective_escalation_after_days = normalize_escalation_after_days(escalation_after_days)

    if completed:
        return AssignmentSLAState(
            status="completed",
            days_until_deadline=None,
            days_overdue=0,
            escalation_after_days=effective_escalation_after_days,
        )

    if deadline is None:
        return AssignmentSLAState(
            status="no_deadline",
            days_until_deadline=None,
            days_overdue=0,
            escalation_after_days=effective_escalation_after_days,
        )

    days_until_deadline = (deadline - effective_today).days
    if days_until_deadline < 0:
        days_overdue = abs(days_until_deadline)
        if days_overdue >= ASSIGNMENT_LEVEL_TWO_DAYS:
            status = "breach_level_2"
        elif days_overdue >= effective_escalation_after_days:
            status = "breach_level_1"
        else:
            status = "overdue"
        return AssignmentSLAState(
            status=status,
            days_until_deadline=days_until_deadline,
            days_overdue=days_overdue,
            escalation_after_days=effective_escalation_after_days,
        )

    status = "on_track"
    if days_until_deadline == 0:
        status = "due_today"
    elif days_until_deadline <= ASSIGNMENT_WARNING_WINDOW_DAYS:
        status = "warning"

    return AssignmentSLAState(
        status=status,
        days_until_deadline=days_until_deadline,
        days_overdue=0,
        escalation_after_days=effective_escalation_after_days,
    )
