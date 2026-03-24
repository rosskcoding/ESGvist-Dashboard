from collections import defaultdict

from sqlalchemy import delete, select

from app.core.access import (
    assignment_matches_data_point,
    get_data_point_for_ctx,
    get_project_for_ctx,
    get_user_assignments,
)
from app.core.dashboard_cache import invalidate_dashboard_project
from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.db.models.boundary import BoundaryMembership
from app.db.models.company_entity import CompanyEntity
from app.db.models.data_point import DataPoint, DataPointDimension
from app.db.models.data_point_version import DataPointVersion
from app.db.models.mapping import RequirementItemSharedElement
from app.db.models.project import ReportingProjectStandard
from app.db.models.shared_element import SharedElement, SharedElementDimension
from app.db.models.standard import DisclosureRequirement, Standard
from app.db.models.requirement_item import RequirementItem
from app.db.models.unit_reference import Methodology, UnitReference
from app.domain.workflow_state import EDITABLE_STATUSES
from app.policies.auth_policy import AuthPolicy
from app.repositories.audit_repo import AuditRepository
from app.repositories.data_point_repo import DataPointRepository
from app.repositories.project_repo import ProjectRepository
from app.schemas.data_points import (
    DataPointCreate,
    DataPointListOut,
    DataPointOut,
    DataPointUpdate,
)


async def create_data_point_version(
    session,
    dp: DataPoint,
    *,
    changed_by: int | None = None,
    change_reason: str | None = None,
) -> DataPointVersion:
    """Snapshot the current data point state as an immutable version row.

    Automatically increments the version number based on existing versions.
    Called from both DataPointService (on value update) and WorkflowService
    (on status transitions).
    """
    from sqlalchemy import func as sa_func

    max_version_result = await session.execute(
        select(sa_func.coalesce(sa_func.max(DataPointVersion.version), 0)).where(
            DataPointVersion.data_point_id == dp.id
        )
    )
    next_version = int(max_version_result.scalar_one()) + 1

    version = DataPointVersion(
        data_point_id=dp.id,
        version=next_version,
        numeric_value=float(dp.numeric_value) if dp.numeric_value is not None else None,
        text_value=dp.text_value,
        unit_code=dp.unit_code,
        status=dp.status,
        changed_by=changed_by,
        change_reason=change_reason,
    )
    session.add(version)
    await session.flush()
    return version


def _collection_status(status: str) -> str:
    if status == "approved":
        return "complete"
    if status in {"draft", "submitted", "in_review", "needs_revision", "rejected"}:
        return "partial"
    return "missing"


def _element_type(value_type: str | None, fallback: str | None) -> str:
    resolved = (value_type or fallback or "").lower()
    if resolved in {"number", "numeric", "decimal", "float", "integer"}:
        return "numeric"
    if resolved == "boolean":
        return "boolean"
    return "text"


class DataPointService:
    def __init__(
        self,
        repo: DataPointRepository,
        project_repo: ProjectRepository,
        audit_repo: AuditRepository | None = None,
    ):
        self.repo = repo
        self.project_repo = project_repo
        self.audit_repo = audit_repo

    async def create(
        self, project_id: int, payload: DataPointCreate, ctx: RequestContext
    ) -> DataPointOut:
        AuthPolicy.require_collector_or_manager(ctx)
        project = await get_project_for_ctx(self.repo.session, project_id, ctx)
        if ctx.role == "collector":
            assignments = await get_user_assignments(
                self.repo.session, project_id, ctx.user_id, "collector"
            )
            if not any(
                assignment.shared_element_id == payload.shared_element_id
                and (assignment.entity_id is None or assignment.entity_id == payload.entity_id)
                and (assignment.facility_id is None or assignment.facility_id == payload.facility_id)
                for assignment in assignments
            ):
                raise AppError("FORBIDDEN", 403, "Collectors can only create assigned data points")

        dp = await self.repo.create(
            project_id=project_id,
            shared_element_id=payload.shared_element_id,
            entity_id=payload.entity_id,
            facility_id=getattr(payload, "facility_id", None),
            numeric_value=payload.numeric_value,
            text_value=payload.text_value,
            unit_code=payload.unit_code,
            created_by=ctx.user_id,
            status="draft",
        )

        for dim in payload.dimensions:
            await self.repo.add_dimension(dp.id, dim.dimension_type, dim.dimension_value)

        if self.audit_repo:
            await self.audit_repo.log(
                entity_type="DataPoint",
                entity_id=dp.id,
                action="data_point_created",
                user_id=ctx.user_id,
                organization_id=ctx.organization_id,
                changes={"project_id": project_id, "shared_element_id": payload.shared_element_id},
                performed_by_platform_admin=ctx.is_platform_admin,
            )

        await invalidate_dashboard_project(project_id)
        return await self._serialize_data_point(dp, project, detail=True)

    async def update(
        self,
        dp_id: int,
        payload: DataPointUpdate,
        ctx: RequestContext,
    ) -> DataPointOut:
        AuthPolicy.require_collector_or_manager(ctx)
        dp, project, _ = await get_data_point_for_ctx(self.repo.session, dp_id, ctx)

        if dp.status not in EDITABLE_STATUSES:
            raise AppError(
                "DATA_POINT_NOT_EDITABLE",
                409,
                f"Data point in status '{dp.status}' cannot be edited",
            )

        methodology_id = dp.methodology_id
        if payload.methodology:
            methodology = await self._resolve_methodology(payload.methodology)
            if methodology is None:
                raise AppError("METHODOLOGY_NOT_FOUND", 422, "Selected methodology was not found")
            methodology_id = methodology.id

        update_fields: dict[str, object | None] = {
            "unit_code": payload.unit_code,
            "methodology_id": methodology_id,
        }
        if payload.numeric_value is not None:
            update_fields["numeric_value"] = payload.numeric_value
            update_fields["text_value"] = None
        elif payload.text_value is not None:
            update_fields["text_value"] = payload.text_value
            update_fields["numeric_value"] = None

        dp = await self.repo.update(dp_id, **update_fields)

        # Snapshot version after value change
        await create_data_point_version(
            self.repo.session, dp,
            changed_by=ctx.user_id,
            change_reason="value_updated",
        )

        if payload.dimensions is not None:
            await self.repo.session.execute(
                delete(DataPointDimension).where(DataPointDimension.data_point_id == dp_id)
            )
            for dim in payload.dimensions:
                await self.repo.add_dimension(dp_id, dim.dimension_type, dim.dimension_value)

        if self.audit_repo:
            await self.audit_repo.log(
                entity_type="DataPoint",
                entity_id=dp_id,
                action="data_point_updated",
                user_id=ctx.user_id,
                organization_id=ctx.organization_id,
                changes={
                    "unit_code": payload.unit_code,
                    "methodology": payload.methodology,
                    "numeric_value": payload.numeric_value,
                    "text_value": payload.text_value,
                },
                performed_by_platform_admin=ctx.is_platform_admin,
            )

        await invalidate_dashboard_project(dp.reporting_project_id)
        return await self._serialize_data_point(dp, project, detail=True)

    async def list_by_project(
        self, project_id: int, ctx: RequestContext, page: int = 1, page_size: int = 50
    ) -> DataPointListOut:
        AuthPolicy.require_collector_or_manager(ctx)
        project = await get_project_for_ctx(self.repo.session, project_id, ctx)

        if ctx.role == "collector":
            assignments = await get_user_assignments(
                self.repo.session, project_id, ctx.user_id, "collector"
            )
            shared_element_ids = list({assignment.shared_element_id for assignment in assignments})
            data_points = await self.repo.list_all_by_project(project_id, shared_element_ids)
            items = [
                data_point
                for data_point in data_points
                if data_point.created_by == ctx.user_id
                or any(
                    assignment_matches_data_point(assignment, data_point)
                    for assignment in assignments
                )
            ]
            total = len(items)
            start = (page - 1) * page_size
            items = items[start:start + page_size]
        else:
            items, total = await self.repo.list_by_project(project_id, page, page_size)

        return DataPointListOut(
            items=[await self._serialize_data_point(dp, project, detail=False) for dp in items],
            total=total,
        )

    async def get(self, dp_id: int, ctx: RequestContext) -> DataPointOut:
        dp, project, _ = await get_data_point_for_ctx(self.repo.session, dp_id, ctx)
        return await self._serialize_data_point(dp, project, detail=True)

    async def _resolve_methodology(self, selected: str) -> Methodology | None:
        result = await self.repo.session.execute(
            select(Methodology).where(
                (Methodology.code == selected) | (Methodology.name == selected)
            )
        )
        return result.scalar_one_or_none()

    async def _serialize_data_point(
        self,
        dp: DataPoint,
        project,
        *,
        detail: bool,
    ) -> DataPointOut:
        context = await self._load_context(
            project_id=project.id,
            boundary_definition_id=project.boundary_definition_id,
            shared_element_ids=[dp.shared_element_id],
            entity_ids=[entity_id for entity_id in (dp.entity_id, dp.facility_id) if entity_id is not None],
            methodology_ids=[dp.methodology_id] if detail and dp.methodology_id else [],
            include_detail=detail,
        )
        evidence_count = await self.repo.count_evidence_links(dp.id)
        return self._serialize_with_context(
            dp,
            project.boundary_definition_id,
            context,
            detail=detail,
            evidence_count=evidence_count,
        )

    async def _load_context(
        self,
        *,
        project_id: int,
        boundary_definition_id: int | None,
        shared_element_ids: list[int],
        entity_ids: list[int],
        methodology_ids: list[int],
        include_detail: bool,
    ) -> dict:
        shared_element_ids = list({sid for sid in shared_element_ids if sid is not None})
        entity_ids = list({eid for eid in entity_ids if eid is not None})
        methodology_ids = list({mid for mid in methodology_ids if mid is not None})

        shared_elements: dict[int, SharedElement] = {}
        if shared_element_ids:
            result = await self.repo.session.execute(
                select(SharedElement).where(SharedElement.id.in_(shared_element_ids))
            )
            shared_elements = {item.id: item for item in result.scalars().all()}

        entities: dict[int, str] = {}
        if entity_ids:
            result = await self.repo.session.execute(
                select(CompanyEntity.id, CompanyEntity.name).where(CompanyEntity.id.in_(entity_ids))
            )
            entities = {entity_id: name for entity_id, name in result.all()}

        memberships: dict[int, tuple[bool, str | None]] = {}
        if boundary_definition_id and entity_ids:
            result = await self.repo.session.execute(
                select(
                    BoundaryMembership.entity_id,
                    BoundaryMembership.included,
                    BoundaryMembership.consolidation_method,
                ).where(
                    BoundaryMembership.boundary_definition_id == boundary_definition_id,
                    BoundaryMembership.entity_id.in_(entity_ids),
                )
            )
            memberships = {
                entity_id: (included, consolidation_method)
                for entity_id, included, consolidation_method in result.all()
            }

        standard_rows = []
        if shared_element_ids:
            result = await self.repo.session.execute(
                select(
                    RequirementItemSharedElement.shared_element_id,
                    Standard.code,
                    Standard.name,
                    RequirementItem.value_type,
                    RequirementItem.requires_evidence,
                    RequirementItem.unit_code,
                )
                .join(
                    RequirementItem,
                    RequirementItem.id == RequirementItemSharedElement.requirement_item_id,
                )
                .join(
                    DisclosureRequirement,
                    DisclosureRequirement.id == RequirementItem.disclosure_requirement_id,
                )
                .join(Standard, Standard.id == DisclosureRequirement.standard_id)
                .join(
                    ReportingProjectStandard,
                    (ReportingProjectStandard.standard_id == Standard.id)
                    & (ReportingProjectStandard.reporting_project_id == project_id),
                )
                .where(RequirementItemSharedElement.shared_element_id.in_(shared_element_ids))
                .order_by(Standard.code, RequirementItem.id)
            )
            standard_rows = list(result.all())

        standards_by_element: dict[int, list[dict[str, str]]] = defaultdict(list)
        element_meta: dict[int, dict[str, object]] = defaultdict(
            lambda: {
                "value_type": None,
                "evidence_required": False,
                "unit_codes": [],
            }
        )
        seen_standard_pairs: set[tuple[int, str]] = set()
        for shared_element_id, code, name, value_type, requires_evidence, unit_code in standard_rows:
            if (shared_element_id, code) not in seen_standard_pairs:
                standards_by_element[shared_element_id].append({"code": code, "name": name})
                seen_standard_pairs.add((shared_element_id, code))
            meta = element_meta[shared_element_id]
            if meta["value_type"] is None and value_type:
                meta["value_type"] = value_type
            if requires_evidence:
                meta["evidence_required"] = True
            if unit_code and unit_code not in meta["unit_codes"]:
                meta["unit_codes"].append(unit_code)

        dimension_flags: dict[int, dict[str, bool]] = defaultdict(
            lambda: {"scope": False, "gas_type": False, "category": False}
        )
        unit_options: list[str] = []
        methodology_options: list[str] = []
        methodology_names: dict[int, str] = {}
        if include_detail:
            if shared_element_ids:
                result = await self.repo.session.execute(
                    select(
                        SharedElementDimension.shared_element_id,
                        SharedElementDimension.dimension_type,
                    ).where(SharedElementDimension.shared_element_id.in_(shared_element_ids))
                )
                for shared_element_id, dimension_type in result.all():
                    if dimension_type == "scope":
                        dimension_flags[shared_element_id]["scope"] = True
                    elif dimension_type in {"gas", "gas_type"}:
                        dimension_flags[shared_element_id]["gas_type"] = True
                    elif dimension_type == "category":
                        dimension_flags[shared_element_id]["category"] = True

            result = await self.repo.session.execute(select(UnitReference.code).order_by(UnitReference.code))
            unit_options = [code for (code,) in result.all()]

            result = await self.repo.session.execute(select(Methodology.id, Methodology.name).order_by(Methodology.code))
            methodology_names = {methodology_id: name for methodology_id, name in result.all()}
            methodology_options = list(methodology_names.values())

            if methodology_ids:
                result = await self.repo.session.execute(
                    select(Methodology.id, Methodology.name).where(Methodology.id.in_(methodology_ids))
                )
                methodology_names.update({methodology_id: name for methodology_id, name in result.all()})

        return {
            "shared_elements": shared_elements,
            "entities": entities,
            "memberships": memberships,
            "standards_by_element": standards_by_element,
            "element_meta": element_meta,
            "dimension_flags": dimension_flags,
            "unit_options": unit_options,
            "methodology_options": methodology_options,
            "methodology_names": methodology_names,
        }

    def _serialize_with_context(
        self,
        dp: DataPoint,
        boundary_definition_id: int | None,
        context: dict,
        *,
        detail: bool,
        evidence_count: int,
    ) -> DataPointOut:
        shared_element: SharedElement | None = context["shared_elements"].get(dp.shared_element_id)
        standards = context["standards_by_element"].get(dp.shared_element_id, [])
        meta = context["element_meta"].get(dp.shared_element_id, {})

        scope_entity_id = dp.facility_id or dp.entity_id
        membership = context["memberships"].get(scope_entity_id) if scope_entity_id is not None else None
        if membership is not None:
            boundary_status = "included" if membership[0] else "excluded"
            consolidation_method = membership[1] or "full"
        elif scope_entity_id is None:
            boundary_status = "excluded" if boundary_definition_id else "included"
            consolidation_method = "full"
        else:
            boundary_status = "partial" if boundary_definition_id else "included"
            consolidation_method = "full"

        unit_options = list(context["unit_options"]) if detail else []
        for preferred_unit in meta.get("unit_codes", []):
            if preferred_unit in unit_options:
                unit_options.remove(preferred_unit)
            unit_options.insert(0, preferred_unit)
        if shared_element and shared_element.default_unit_code:
            default_unit = shared_element.default_unit_code
            if default_unit in unit_options:
                unit_options.remove(default_unit)
            unit_options.insert(0, default_unit)

        payload = {
            "id": dp.id,
            "reporting_project_id": dp.reporting_project_id,
            "shared_element_id": dp.shared_element_id,
            "entity_id": dp.entity_id,
            "facility_id": dp.facility_id,
            "status": dp.status,
            "numeric_value": float(dp.numeric_value) if dp.numeric_value is not None else None,
            "text_value": dp.text_value,
            "unit_code": dp.unit_code,
            "methodology": context["methodology_names"].get(dp.methodology_id),
            "created_by": dp.created_by,
            "element_code": shared_element.code if shared_element else None,
            "element_name": shared_element.name if shared_element else None,
            "entity_name": context["entities"].get(dp.entity_id),
            "facility_name": context["entities"].get(dp.facility_id),
            "boundary_status": boundary_status,
            "consolidation_method": consolidation_method,
            "standards": [item["code"] for item in standards],
            "related_standards": standards,
            "reused_across_standards": len(standards) > 1,
            "collection_status": _collection_status(dp.status),
            "element_type": _element_type(meta.get("value_type"), shared_element.default_value_type if shared_element else None),
            "evidence_required": bool(meta.get("evidence_required", False)),
            "evidence_count": evidence_count,
            "dimensions": context["dimension_flags"].get(
                dp.shared_element_id,
                {"scope": False, "gas_type": False, "category": False},
            ),
            "unit_options": unit_options,
            "methodology_options": list(context["methodology_options"]) if detail else [],
        }
        return DataPointOut.model_validate(payload)
