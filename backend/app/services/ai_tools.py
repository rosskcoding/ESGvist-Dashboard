"""AI tool definitions and execution layer.

Each tool is a read-only query that fetches structured context from the
database.  Tools are exposed to the LLM via function-calling; the
ToolAccessGate validates that the requesting user is allowed to invoke a
particular tool and that the returned data stays within their object-level
scope.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import get_user_assignments
from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.db.models.boundary import BoundaryMembership
from app.db.models.completeness import RequirementItemDataPoint, RequirementItemStatus
from app.db.models.data_point import DataPoint
from app.db.models.evidence import DataPointEvidence
from app.db.models.mapping import RequirementItemSharedElement
from app.db.models.project import MetricAssignment
from app.db.models.requirement_item import RequirementItem
from app.db.models.shared_element import SharedElement
from app.db.models.standard import DisclosureRequirement, Standard

# ---------------------------------------------------------------------------
# Tool definitions (metadata consumed by the LLM and by ToolAccessGate)
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, dict[str, Any]]
    allowed_roles: frozenset[str]


TOOL_REGISTRY: dict[str, ToolDefinition] = {}


def _register(
    name: str,
    description: str,
    parameters: dict[str, dict[str, Any]],
    allowed_roles: tuple[str, ...],
) -> ToolDefinition:
    defn = ToolDefinition(
        name=name,
        description=description,
        parameters=parameters,
        allowed_roles=frozenset(allowed_roles),
    )
    TOOL_REGISTRY[name] = defn
    return defn


TOOL_GET_REQUIREMENT_DETAILS = _register(
    name="get_requirement_details",
    description="Get details about a requirement item including standard, type, rules",
    parameters={"requirement_item_id": {"type": "integer"}},
    allowed_roles=("collector", "reviewer", "esg_manager", "auditor", "admin", "platform_admin"),
)

TOOL_GET_STANDARD_INFO = _register(
    name="get_standard_info",
    description="Get standard description, sections, requirements overview",
    parameters={"standard_id": {"type": "integer"}},
    allowed_roles=("collector", "reviewer", "esg_manager", "auditor", "admin", "platform_admin"),
)

TOOL_GET_BOUNDARY_DECISION = _register(
    name="get_boundary_decision",
    description="Get boundary inclusion decision for an entity",
    parameters={"entity_id": {"type": "integer"}, "boundary_id": {"type": "integer"}},
    allowed_roles=("reviewer", "esg_manager", "admin", "platform_admin"),
)

TOOL_GET_PROJECT_COMPLETENESS = _register(
    name="get_project_completeness",
    description="Get completeness status for a project or disclosure",
    parameters={
        "project_id": {"type": "integer"},
        "disclosure_id": {"type": "integer", "optional": True},
    },
    allowed_roles=("esg_manager", "admin", "platform_admin"),
)

TOOL_GET_DATA_POINT_DETAILS = _register(
    name="get_data_point_details",
    description="Get data point value, history, evidence, reuse info",
    parameters={"data_point_id": {"type": "integer"}},
    allowed_roles=("reviewer", "esg_manager", "admin", "platform_admin"),
)

TOOL_GET_EVIDENCE_REQUIREMENTS = _register(
    name="get_evidence_requirements",
    description="Get evidence requirements and status for a requirement item",
    parameters={"requirement_item_id": {"type": "integer"}},
    allowed_roles=("collector", "reviewer", "esg_manager", "auditor", "admin", "platform_admin"),
)

TOOL_GET_ANOMALY_FLAGS = _register(
    name="get_anomaly_flags",
    description="Get anomaly flags for a data point (peer deviation, cross-checks)",
    parameters={"data_point_id": {"type": "integer"}},
    allowed_roles=("reviewer", "esg_manager", "admin", "platform_admin"),
)

TOOL_GET_ASSIGNMENT_INFO = _register(
    name="get_assignment_info",
    description="Get assignment details (collector, reviewer, deadline, status)",
    parameters={
        "project_id": {"type": "integer"},
        "shared_element_id": {"type": "integer", "optional": True},
    },
    allowed_roles=("esg_manager", "admin", "platform_admin"),
)


# ---------------------------------------------------------------------------
# ToolAccessGate
# ---------------------------------------------------------------------------

class ToolAccessGate:
    """Validates that a user is allowed to call a tool and that the returned
    data belongs to their object-level scope."""

    def check_tool_allowed(self, tool_name: str, ctx: RequestContext) -> None:
        defn = TOOL_REGISTRY.get(tool_name)
        if defn is None:
            raise AppError("AI_TOOL_NOT_FOUND", 400, f"Unknown AI tool: {tool_name}")
        if ctx.role not in defn.allowed_roles:
            raise AppError(
                "AI_TOOL_FORBIDDEN",
                403,
                f"AI tool '{tool_name}' not available for role '{ctx.role}'",
            )

    def get_tools_for_role(self, role: str) -> list[ToolDefinition]:
        return [d for d in TOOL_REGISTRY.values() if role in d.allowed_roles]

    def get_tool_names_for_role(self, role: str) -> list[str]:
        return [d.name for d in self.get_tools_for_role(role)]

    def get_blocked_tools(self, role: str) -> list[str]:
        return [d.name for d in TOOL_REGISTRY.values() if role not in d.allowed_roles]


# ---------------------------------------------------------------------------
# Tool execution functions
# ---------------------------------------------------------------------------

async def _check_data_point_access(
    dp: DataPoint, session: AsyncSession, ctx: RequestContext
) -> None:
    """Verify the requesting user has object-level access to a data point.

    - admin / esg_manager / platform_admin: unrestricted within their org
    - reviewer: must be assigned to review this shared element in this project
    - collector: must own the data point or be assigned to collect it
    - auditor: read-only access to all data within the project

    Raises ``AI_OBJECT_ACCESS_DENIED`` (403) if denied.
    """
    if ctx.role in ("admin", "esg_manager", "platform_admin", "auditor"):
        return  # unrestricted within org (org isolation is handled elsewhere)

    if ctx.role == "collector":
        # Must own the DP or be assigned to its shared element
        if dp.created_by == ctx.user_id:
            return
        assignments = await get_user_assignments(
            session, dp.reporting_project_id, ctx.user_id, "collector"
        )
        if any(a.shared_element_id == dp.shared_element_id for a in assignments):
            return
        raise AppError(
            "AI_OBJECT_ACCESS_DENIED", 403,
            "Collector cannot access this data point through AI tools",
        )

    if ctx.role == "reviewer":
        assignments = await get_user_assignments(
            session, dp.reporting_project_id, ctx.user_id, "reviewer"
        )
        if any(a.shared_element_id == dp.shared_element_id for a in assignments):
            return
        raise AppError(
            "AI_OBJECT_ACCESS_DENIED", 403,
            "Reviewer cannot access this data point through AI tools",
        )


async def execute_tool(
    tool_name: str,
    params: dict[str, Any],
    session: AsyncSession,
    ctx: RequestContext,
) -> dict[str, Any]:
    """Dispatch a tool call, enforcing object-level scope."""
    executor = _TOOL_EXECUTORS.get(tool_name)
    if executor is None:
        raise AppError("AI_TOOL_NOT_FOUND", 400, f"Unknown AI tool: {tool_name}")
    return await executor(params, session, ctx)


# -- get_requirement_details -------------------------------------------------

async def _exec_get_requirement_details(
    params: dict, session: AsyncSession, ctx: RequestContext
) -> dict:
    item_id = params["requirement_item_id"]
    result = await session.execute(
        select(RequirementItem).where(RequirementItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        return {"error": f"Requirement item {item_id} not found"}

    disclosure = None
    standard = None
    if item.disclosure_requirement_id:
        disclosure = (
            await session.execute(
                select(DisclosureRequirement).where(
                    DisclosureRequirement.id == item.disclosure_requirement_id
                )
            )
        ).scalar_one_or_none()
    if disclosure:
        standard = (
            await session.execute(
                select(Standard).where(Standard.id == disclosure.standard_id)
            )
        ).scalar_one_or_none()

    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "item_type": item.item_type,
        "value_type": item.value_type,
        "unit_code": item.unit_code,
        "is_required": item.is_required,
        "requires_evidence": item.requires_evidence,
        "cardinality_min": item.cardinality_min,
        "cardinality_max": item.cardinality_max,
        "granularity_rule": item.granularity_rule,
        "validation_rule": item.validation_rule,
        "standard_code": standard.code if standard else None,
        "standard_name": standard.name if standard else None,
        "disclosure_code": disclosure.code if disclosure else None,
        "disclosure_title": disclosure.title if disclosure else None,
        "mandatory_level": disclosure.mandatory_level if disclosure else None,
    }


# -- get_standard_info -------------------------------------------------------

async def _exec_get_standard_info(
    params: dict, session: AsyncSession, ctx: RequestContext
) -> dict:
    std_id = params["standard_id"]
    result = await session.execute(select(Standard).where(Standard.id == std_id))
    standard = result.scalar_one_or_none()
    if not standard:
        return {"error": f"Standard {std_id} not found"}

    disc_rows = (
        await session.execute(
            select(DisclosureRequirement.code, DisclosureRequirement.title, DisclosureRequirement.mandatory_level)
            .where(DisclosureRequirement.standard_id == std_id)
            .order_by(DisclosureRequirement.sort_order)
        )
    ).all()

    return {
        "id": standard.id,
        "code": standard.code,
        "name": standard.name,
        "version": standard.version,
        "jurisdiction": standard.jurisdiction,
        "is_active": standard.is_active,
        "disclosures": [
            {"code": code, "title": title, "mandatory_level": ml}
            for code, title, ml in disc_rows
        ],
    }


# -- get_boundary_decision ---------------------------------------------------

async def _exec_get_boundary_decision(
    params: dict, session: AsyncSession, ctx: RequestContext
) -> dict:
    entity_id = params["entity_id"]
    boundary_id = params["boundary_id"]
    result = await session.execute(
        select(BoundaryMembership).where(
            BoundaryMembership.boundary_definition_id == boundary_id,
            BoundaryMembership.entity_id == entity_id,
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        return {
            "entity_id": entity_id,
            "boundary_id": boundary_id,
            "included": False,
            "reason": "No boundary membership found for this entity",
        }
    return {
        "entity_id": entity_id,
        "boundary_id": boundary_id,
        "included": membership.included,
        "inclusion_reason": membership.inclusion_reason,
        "inclusion_source": membership.inclusion_source,
        "consolidation_method": membership.consolidation_method,
    }


# -- get_project_completeness ------------------------------------------------

async def _exec_get_project_completeness(
    params: dict, session: AsyncSession, ctx: RequestContext
) -> dict:
    project_id = params["project_id"]
    disclosure_id = params.get("disclosure_id")

    query = (
        select(RequirementItemStatus.status, func.count())
        .where(RequirementItemStatus.reporting_project_id == project_id)
    )
    if disclosure_id:
        query = query.join(
            RequirementItem,
            RequirementItem.id == RequirementItemStatus.requirement_item_id,
        ).where(RequirementItem.disclosure_requirement_id == disclosure_id)
    query = query.group_by(RequirementItemStatus.status)

    status_rows = (await session.execute(query)).all()
    status_counts = {status: count for status, count in status_rows}
    total = sum(status_counts.values())
    completion_percent = round((status_counts.get("complete", 0) / total) * 100, 1) if total else 0

    detail_query = (
        select(RequirementItem.name, RequirementItemStatus.status)
        .join(RequirementItem, RequirementItem.id == RequirementItemStatus.requirement_item_id)
        .where(RequirementItemStatus.reporting_project_id == project_id)
    )
    if disclosure_id:
        detail_query = detail_query.where(RequirementItem.disclosure_requirement_id == disclosure_id)
    detail_rows = (await session.execute(detail_query.order_by(RequirementItem.id))).all()

    return {
        "project_id": project_id,
        "disclosure_id": disclosure_id,
        "status_counts": status_counts,
        "completion_percent": completion_percent,
        "missing_items": [name for name, status in detail_rows if status == "missing"],
        "partial_items": [name for name, status in detail_rows if status == "partial"],
        "complete_items": [name for name, status in detail_rows if status == "complete"],
    }


# -- get_data_point_details --------------------------------------------------

async def _exec_get_data_point_details(
    params: dict, session: AsyncSession, ctx: RequestContext
) -> dict:
    dp_id = params["data_point_id"]
    result = await session.execute(select(DataPoint).where(DataPoint.id == dp_id))
    dp = result.scalar_one_or_none()
    if not dp:
        return {"error": f"Data point {dp_id} not found"}
    await _check_data_point_access(dp, session, ctx)

    shared_element = (
        await session.execute(
            select(SharedElement).where(SharedElement.id == dp.shared_element_id)
        )
    ).scalar_one_or_none()

    evidence_count = (
        await session.execute(
            select(func.count()).select_from(DataPointEvidence).where(
                DataPointEvidence.data_point_id == dp.id
            )
        )
    ).scalar_one()

    binding_count = (
        await session.execute(
            select(func.count()).select_from(RequirementItemDataPoint).where(
                RequirementItemDataPoint.data_point_id == dp.id
            )
        )
    ).scalar_one()

    return {
        "id": dp.id,
        "status": dp.status,
        "numeric_value": float(dp.numeric_value) if dp.numeric_value is not None else None,
        "text_value": dp.text_value,
        "unit_code": dp.unit_code,
        "entity_id": dp.entity_id,
        "shared_element_name": shared_element.name if shared_element else None,
        "shared_element_code": shared_element.code if shared_element else None,
        "concept_domain": shared_element.concept_domain if shared_element else None,
        "evidence_count": evidence_count,
        "binding_count": binding_count,
        "is_derived": dp.is_derived,
    }


# -- get_evidence_requirements -----------------------------------------------

async def _exec_get_evidence_requirements(
    params: dict, session: AsyncSession, ctx: RequestContext
) -> dict:
    item_id = params["requirement_item_id"]
    result = await session.execute(
        select(RequirementItem).where(RequirementItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        return {"error": f"Requirement item {item_id} not found"}

    # Count data points that have evidence linked via bindings
    bound_dp_ids_q = (
        select(RequirementItemDataPoint.data_point_id)
        .where(RequirementItemDataPoint.requirement_item_id == item_id)
    )
    evidence_linked_count = (
        await session.execute(
            select(func.count(func.distinct(DataPointEvidence.data_point_id)))
            .where(DataPointEvidence.data_point_id.in_(bound_dp_ids_q))
        )
    ).scalar_one()

    total_bound_dps = (
        await session.execute(
            select(func.count()).select_from(RequirementItemDataPoint)
            .where(RequirementItemDataPoint.requirement_item_id == item_id)
        )
    ).scalar_one()

    return {
        "requirement_item_id": item.id,
        "name": item.name,
        "requires_evidence": item.requires_evidence,
        "item_type": item.item_type,
        "value_type": item.value_type,
        "total_bound_data_points": total_bound_dps,
        "data_points_with_evidence": evidence_linked_count,
        "evidence_gap": max(0, total_bound_dps - evidence_linked_count) if item.requires_evidence else 0,
        "evidence_sufficient": (not item.requires_evidence) or (evidence_linked_count >= total_bound_dps),
    }


# -- get_anomaly_flags -------------------------------------------------------

async def _exec_get_anomaly_flags(
    params: dict, session: AsyncSession, ctx: RequestContext
) -> dict:
    dp_id = params["data_point_id"]
    result = await session.execute(select(DataPoint).where(DataPoint.id == dp_id))
    dp = result.scalar_one_or_none()
    if not dp:
        return {"error": f"Data point {dp_id} not found"}
    await _check_data_point_access(dp, session, ctx)

    anomalies: list[str] = []
    value_delta_percent: float | None = None

    if dp.numeric_value is not None:
        peer_values = (
            await session.execute(
                select(DataPoint.numeric_value).where(
                    DataPoint.reporting_project_id == dp.reporting_project_id,
                    DataPoint.shared_element_id == dp.shared_element_id,
                    DataPoint.id != dp.id,
                    DataPoint.numeric_value.is_not(None),
                )
            )
        ).scalars().all()

        if peer_values:
            peer_avg = sum(float(v) for v in peer_values) / len(peer_values)
            if peer_avg:
                value_delta_percent = round(((float(dp.numeric_value) - peer_avg) / peer_avg) * 100, 1)
                if abs(value_delta_percent) >= 50:
                    anomalies.append(
                        f"Value differs materially from peer entries ({value_delta_percent:+.1f}%)"
                    )

    if dp.status not in ("in_review", "approved"):
        anomalies.append(f"Data point status is '{dp.status}', expected 'in_review' or 'approved'")

    if dp.numeric_value is None and not dp.text_value:
        anomalies.append("Data point has no reported value")

    evidence_count = (
        await session.execute(
            select(func.count()).select_from(DataPointEvidence).where(
                DataPointEvidence.data_point_id == dp.id
            )
        )
    ).scalar_one()
    if evidence_count == 0:
        anomalies.append("No evidence linked to this data point")

    return {
        "data_point_id": dp.id,
        "anomalies": anomalies,
        "value_delta_percent": value_delta_percent,
        "evidence_count": evidence_count,
    }


# -- get_assignment_info -----------------------------------------------------

async def _exec_get_assignment_info(
    params: dict, session: AsyncSession, ctx: RequestContext
) -> dict:
    project_id = params["project_id"]
    shared_element_id = params.get("shared_element_id")

    query = select(MetricAssignment).where(
        MetricAssignment.reporting_project_id == project_id
    )
    if shared_element_id:
        query = query.where(MetricAssignment.shared_element_id == shared_element_id)
    query = query.order_by(MetricAssignment.id)

    rows = (await session.execute(query)).scalars().all()
    return {
        "project_id": project_id,
        "assignments": [
            {
                "id": a.id,
                "shared_element_id": a.shared_element_id,
                "entity_id": a.entity_id,
                "facility_id": a.facility_id,
                "collector_id": a.collector_id,
                "reviewer_id": a.reviewer_id,
                "backup_collector_id": a.backup_collector_id,
            }
            for a in rows
        ],
    }


# -- Scope-filtered completeness for collectors / reviewers ------------------

async def get_scoped_completeness(
    session: AsyncSession,
    project_id: int,
    ctx: RequestContext,
    *,
    disclosure_id: int | None = None,
) -> dict:
    """Return completeness data filtered to the user's assignment scope.

    For collector / reviewer: only requirement items that are bound to
    shared elements from their assignments are visible.
    For esg_manager / admin / platform_admin: full project scope.

    When *disclosure_id* is provided the result is narrowed to that single
    disclosure — this is what powers "Why partial?" per-disclosure row.
    """
    if ctx.role in ("esg_manager", "admin", "platform_admin"):
        return await _exec_get_project_completeness(
            {"project_id": project_id, "disclosure_id": disclosure_id},
            session,
            ctx,
        )

    assignments = await get_user_assignments(session, project_id, ctx.user_id, ctx.role or "collector")
    assigned_se_ids = [a.shared_element_id for a in assignments]
    if not assigned_se_ids:
        return {
            "project_id": project_id,
            "disclosure_id": disclosure_id,
            "status_counts": {},
            "completion_percent": 0,
            "missing_items": [],
            "partial_items": [],
            "complete_items": [],
            "scope_note": "No assignments found for your role",
        }

    mapping_scope_rows = (
        await session.execute(
            select(
                RequirementItemSharedElement.requirement_item_id,
                RequirementItem.disclosure_requirement_id,
            )
            .join(
                RequirementItem,
                RequirementItem.id == RequirementItemSharedElement.requirement_item_id,
            )
            .where(
                RequirementItemSharedElement.shared_element_id.in_(assigned_se_ids),
                RequirementItemSharedElement.is_current == True,  # noqa: E712
            )
        )
    ).all()
    assigned_item_ids = sorted({item_id for item_id, _disclosure_id in mapping_scope_rows})
    allowed_disclosure_ids = sorted(
        {
            disclosure_id
            for _item_id, disclosure_id in mapping_scope_rows
            if disclosure_id is not None
        }
    )
    if not assigned_item_ids:
        return {
            "project_id": project_id,
            "disclosure_id": disclosure_id,
            "status_counts": {},
            "completion_percent": 0,
            "missing_items": [],
            "partial_items": [],
            "complete_items": [],
            "scope_note": "No mapped requirement items found for your assignments",
        }

    # Requirement items directly related to the user's assigned shared elements
    bound_item_ids_q = (
        select(RequirementItemStatus.requirement_item_id)
        .where(
            RequirementItemStatus.reporting_project_id == project_id,
            RequirementItemStatus.requirement_item_id.in_(assigned_item_ids),
        )
    )

    # Missing items can have no binding yet, so widen only to disclosures
    # that are reachable from the user's assigned shared elements.
    scope_filter = or_(
        RequirementItemStatus.requirement_item_id.in_(bound_item_ids_q),
        and_(
            RequirementItemStatus.status == "missing",
            RequirementItemStatus.requirement_item_id.in_(
                select(RequirementItem.id).where(
                    RequirementItem.disclosure_requirement_id.in_(allowed_disclosure_ids)
                )
            ),
        ),
    )

    status_query = (
        select(RequirementItemStatus.status, func.count())
        .where(RequirementItemStatus.reporting_project_id == project_id)
    )
    detail_query = (
        select(RequirementItem.name, RequirementItemStatus.status)
        .join(RequirementItem, RequirementItem.id == RequirementItemStatus.requirement_item_id)
        .where(RequirementItemStatus.reporting_project_id == project_id)
    )

    # Apply disclosure filter if provided
    if disclosure_id:
        disc_filter = RequirementItemStatus.requirement_item_id.in_(
            select(RequirementItem.id).where(
                RequirementItem.disclosure_requirement_id == disclosure_id
            )
        )
        status_query = status_query.where(disc_filter)
        detail_query = detail_query.where(disc_filter)

    # Apply scope filter for non-admin roles
    status_query = status_query.where(scope_filter)
    detail_query = detail_query.where(scope_filter)

    status_query = status_query.group_by(RequirementItemStatus.status)
    status_rows = (await session.execute(status_query)).all()

    status_counts = {status: count for status, count in status_rows}
    total = sum(status_counts.values())
    completion_percent = round((status_counts.get("complete", 0) / total) * 100, 1) if total else 0

    detail_rows = (await session.execute(detail_query.order_by(RequirementItem.id))).all()

    return {
        "project_id": project_id,
        "disclosure_id": disclosure_id,
        "status_counts": status_counts,
        "completion_percent": completion_percent,
        "missing_items": [name for name, status in detail_rows if status == "missing"],
        "partial_items": [name for name, status in detail_rows if status == "partial"],
        "complete_items": [name for name, status in detail_rows if status == "complete"],
        "scope_note": f"{ctx.role} scope ({len(assigned_se_ids)} assigned element(s))",
    }


# ---------------------------------------------------------------------------
# Executor registry
# ---------------------------------------------------------------------------

_TOOL_EXECUTORS: dict[str, Any] = {
    "get_requirement_details": _exec_get_requirement_details,
    "get_standard_info": _exec_get_standard_info,
    "get_boundary_decision": _exec_get_boundary_decision,
    "get_project_completeness": _exec_get_project_completeness,
    "get_data_point_details": _exec_get_data_point_details,
    "get_evidence_requirements": _exec_get_evidence_requirements,
    "get_anomaly_flags": _exec_get_anomaly_flags,
    "get_assignment_info": _exec_get_assignment_info,
}
