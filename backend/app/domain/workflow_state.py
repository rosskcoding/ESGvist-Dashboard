"""Data point workflow state machine — pure domain logic, no framework imports."""

TRANSITIONS: dict[str, list[dict]] = {
    "draft": [
        {"to": "submitted", "roles": ["collector", "esg_manager", "admin", "platform_admin"]},
    ],
    "submitted": [
        {"to": "in_review", "roles": ["system"]},
    ],
    "in_review": [
        {"to": "approved", "roles": ["reviewer", "esg_manager", "admin"]},
        {"to": "rejected", "roles": ["reviewer", "esg_manager", "admin"], "require_comment": True},
        {"to": "needs_revision", "roles": ["reviewer", "esg_manager", "admin"], "require_comment": True},
    ],
    "approved": [
        {"to": "draft", "roles": ["esg_manager", "admin"], "require_comment": True},
    ],
    "rejected": [
        {"to": "submitted", "roles": ["collector", "esg_manager", "admin"]},
    ],
    "needs_revision": [
        {"to": "submitted", "roles": ["collector", "esg_manager", "admin"]},
    ],
}

EDITABLE_STATUSES = {"draft", "rejected", "needs_revision"}


def can_transition(current: str, target: str, role: str) -> bool:
    transitions = TRANSITIONS.get(current, [])
    return any(t["to"] == target and role in t["roles"] for t in transitions)


def requires_comment(current: str, target: str) -> bool:
    transitions = TRANSITIONS.get(current, [])
    for t in transitions:
        if t["to"] == target:
            return t.get("require_comment", False)
    return False


def is_editable(status: str) -> bool:
    return status in EDITABLE_STATUSES
