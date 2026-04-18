from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import get_project_for_ctx
from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.db.models.boundary import BoundaryMembership
from app.db.models.company_entity import CompanyEntity
from app.db.models.custom_datasheet import CustomDatasheet, CustomDatasheetItem
from app.db.models.mapping import RequirementItemSharedElement
from app.db.models.project import MetricAssignment, ReportingProject, ReportingProjectStandard
from app.db.models.requirement_item import RequirementItem
from app.db.models.shared_element import SharedElement
from app.db.models.standard import DisclosureRequirement, Standard
from app.policies.auth_policy import AuthPolicy
from app.repositories.custom_datasheet_repo import CustomDatasheetRepository
from app.repositories.project_repo import ProjectRepository
from app.repositories.shared_element_repo import SharedElementRepository
from app.schemas.custom_datasheets import (
    CustomDatasheetCreate,
    CustomDatasheetCreateCustomMetric,
    CustomDatasheetDetailOut,
    CustomDatasheetItemCreate,
    CustomDatasheetItemOut,
    CustomDatasheetItemUpdate,
    CustomDatasheetListOut,
    CustomDatasheetOptionSearchListOut,
    CustomDatasheetOptionSearchOut,
    CustomDatasheetOut,
    CustomDatasheetUpdate,
)


class CustomDatasheetService:
    def __init__(self, repo: CustomDatasheetRepository, session: AsyncSession):
        self.repo = repo
        self.session = session
        self.project_repo = ProjectRepository(session)
        self.shared_element_repo = SharedElementRepository(session)

    @staticmethod
    def _suggest_category(concept_domain: str | None) -> str:
        token = (concept_domain or "").strip().lower()
        if token in {"emissions", "energy", "water", "waste", "climate", "pollution", "biodiversity"}:
            return "environmental"
        if token in {"workforce", "human_rights", "community", "diversity", "health_safety"}:
            return "social"
        if token in {"governance", "ethics", "compliance", "board"}:
            return "governance"
        if token in {"operations", "business", "supply_chain", "procurement"}:
            return "business_operations"
        return "other"

    def _require_manager(self, ctx: RequestContext) -> None:
        if ctx.role not in ("admin", "esg_manager", "platform_admin"):
            raise AppError("FORBIDDEN", 403, "Only admin/esg_manager can manage custom datasheets")

    async def _get_project_or_raise(self, project_id: int, ctx: RequestContext) -> ReportingProject:
        return await get_project_for_ctx(self.session, project_id, ctx, allow_collectors=False, allow_reviewers=False)

    async def _get_datasheet_or_raise(
        self,
        project_id: int,
        datasheet_id: int,
        ctx: RequestContext,
    ) -> tuple[ReportingProject, CustomDatasheet]:
        project = await self._get_project_or_raise(project_id, ctx)
        datasheet = await self.repo.get_datasheet_or_raise(datasheet_id)
        if datasheet.reporting_project_id != project.id:
            raise AppError("FORBIDDEN", 403, "Custom datasheet belongs to another project")
        return project, datasheet

    async def _get_shared_element_or_raise(self, shared_element_id: int) -> SharedElement:
        result = await self.session.execute(
            select(SharedElement).where(SharedElement.id == shared_element_id)
        )
        shared_element = result.scalar_one_or_none()
        if not shared_element:
            raise AppError("NOT_FOUND", 404, f"Shared element {shared_element_id} not found")
        return shared_element

    async def _validate_scope_entity(
        self,
        entity_id: int | None,
        organization_id: int | None,
        *,
        label: str,
    ) -> CompanyEntity | None:
        if entity_id is None:
            return None
        result = await self.session.execute(
            select(CompanyEntity).where(CompanyEntity.id == entity_id)
        )
        entity = result.scalar_one_or_none()
        if not entity:
            raise AppError("NOT_FOUND", 404, f"{label} {entity_id} not found")
        if organization_id is not None and entity.organization_id != organization_id:
            raise AppError("FORBIDDEN", 403, f"{label} {entity_id} does not belong to this organization")
        return entity

    async def _validate_item_scope(
        self,
        project: ReportingProject,
        *,
        collection_scope: str,
        entity_id: int | None,
        facility_id: int | None,
    ) -> None:
        if collection_scope == "project":
            if entity_id is not None or facility_id is not None:
                raise AppError(
                    "INVALID_COLLECTION_SCOPE",
                    422,
                    "Project-level datasheet items cannot include entity_id or facility_id",
                )
            return
        if collection_scope == "entity":
            if entity_id is None or facility_id is not None:
                raise AppError(
                    "INVALID_COLLECTION_SCOPE",
                    422,
                    "Entity-level datasheet items require entity_id and no facility_id",
                )
        if collection_scope == "facility":
            if facility_id is None:
                raise AppError(
                    "INVALID_COLLECTION_SCOPE",
                    422,
                    "Facility-level datasheet items require facility_id",
                )

        await self._validate_scope_entity(entity_id, project.organization_id, label="Entity")
        await self._validate_scope_entity(facility_id, project.organization_id, label="Facility")

    async def _validate_assignment_scope_in_boundary(
        self,
        project: ReportingProject,
        *,
        entity_id: int | None,
        facility_id: int | None,
    ) -> None:
        scope_entity_id = facility_id or entity_id
        if project.boundary_definition_id is None or scope_entity_id is None:
            return
        membership_result = await self.session.execute(
            select(BoundaryMembership.id).where(
                BoundaryMembership.boundary_definition_id == project.boundary_definition_id,
                BoundaryMembership.entity_id == scope_entity_id,
                BoundaryMembership.included == True,  # noqa: E712
            )
        )
        if membership_result.scalar_one_or_none() is None:
            raise AppError(
                "ASSIGNMENT_ENTITY_MISMATCH",
                422,
                "Datasheet item scope entity is outside the project's active boundary",
            )

    async def _resolve_assignment_for_item(
        self,
        project: ReportingProject,
        *,
        shared_element_id: int,
        assignment_id: int | None,
        collection_scope: str,
        entity_id: int | None,
        facility_id: int | None,
    ) -> MetricAssignment | None:
        await self._validate_item_scope(
            project,
            collection_scope=collection_scope,
            entity_id=entity_id,
            facility_id=facility_id,
        )
        await self._validate_assignment_scope_in_boundary(
            project,
            entity_id=entity_id,
            facility_id=facility_id,
        )

        if assignment_id is not None:
            assignment = await self.project_repo.get_assignment_or_raise(assignment_id)
            if assignment.reporting_project_id != project.id:
                raise AppError("FORBIDDEN", 403, "Assignment belongs to another project")
            if assignment.shared_element_id != shared_element_id:
                raise AppError("ASSIGNMENT_MISMATCH", 422, "Assignment uses a different metric")
            if assignment.entity_id != entity_id or assignment.facility_id != facility_id:
                raise AppError(
                    "ASSIGNMENT_MISMATCH",
                    422,
                    "Assignment context does not match the datasheet item scope",
                )
            return assignment

        result = await self.session.execute(
            select(MetricAssignment).where(
                MetricAssignment.reporting_project_id == project.id,
                MetricAssignment.shared_element_id == shared_element_id,
                MetricAssignment.entity_id == entity_id,
                MetricAssignment.facility_id == facility_id,
            )
            .order_by(MetricAssignment.id)
            .limit(1)
        )
        assignment = result.scalar_one_or_none()
        if assignment is not None:
            return assignment

        return await self.project_repo.create_assignment(
            project.id,
            shared_element_id=shared_element_id,
            entity_id=entity_id,
            facility_id=facility_id,
        )

    async def _validate_source_type(
        self,
        shared_element: SharedElement,
        *,
        source_type: str,
        organization_id: int | None,
    ) -> None:
        if source_type == "framework":
            if shared_element.owner_layer != "internal_catalog":
                raise AppError("INVALID_SOURCE_TYPE", 422, "Framework items must use internal catalog metrics")
            return
        if source_type == "existing_custom":
            if shared_element.owner_layer != "tenant_catalog":
                raise AppError("INVALID_SOURCE_TYPE", 422, "Existing custom items must use tenant custom metrics")
            if organization_id is not None and shared_element.organization_id != organization_id:
                raise AppError("FORBIDDEN", 403, "Custom metric belongs to another organization")
            return
        raise AppError("INVALID_SOURCE_TYPE", 422, f"Unsupported source_type '{source_type}'")

    async def _create_custom_metric(
        self,
        project: ReportingProject,
        payload: CustomDatasheetCreateCustomMetric,
    ) -> SharedElement:
        existing = await self.shared_element_repo.get_by_code(payload.code)
        if existing is not None:
            raise AppError("CONFLICT", 409, f"Shared element '{payload.code}' already exists")

        concept_domain = (payload.concept_domain or "").strip().lower() or None
        return await self.shared_element_repo.create(
            code=payload.code.strip(),
            name=payload.name.strip(),
            description=payload.description,
            concept_domain=concept_domain,
            default_value_type=payload.default_value_type,
            default_unit_code=payload.default_unit_code,
            owner_layer="tenant_catalog",
            organization_id=project.organization_id,
            lifecycle_status="active",
            is_custom=True,
        )

    async def _build_counts(self, datasheet_ids: list[int]) -> dict[int, dict[str, int]]:
        if not datasheet_ids:
            return {}
        result = await self.session.execute(
            select(
                CustomDatasheetItem.custom_datasheet_id,
                func.count(CustomDatasheetItem.id),
                func.sum(
                    case((CustomDatasheetItem.source_type == "framework", 1), else_=0)
                ),
                func.sum(
                    case(
                        (
                            CustomDatasheetItem.source_type.in_(("existing_custom", "new_custom")),
                            1,
                        ),
                        else_=0,
                    )
                ),
            )
            .where(
                CustomDatasheetItem.custom_datasheet_id.in_(datasheet_ids),
                CustomDatasheetItem.status == "active",
            )
            .group_by(CustomDatasheetItem.custom_datasheet_id)
        )
        return {
            datasheet_id: {
                "item_count": int(item_count or 0),
                "framework_item_count": int(framework_count or 0),
                "custom_item_count": int(custom_count or 0),
            }
            for datasheet_id, item_count, framework_count, custom_count in result.all()
        }

    async def _serialize_items(self, items: list[CustomDatasheetItem]) -> list[CustomDatasheetItemOut]:
        if not items:
            return []

        shared_element_ids = sorted({item.shared_element_id for item in items})
        entity_ids = sorted(
            {
                entity_id
                for item in items
                for entity_id in (item.entity_id, item.facility_id)
                if entity_id is not None
            }
        )

        shared_elements_result = await self.session.execute(
            select(SharedElement).where(SharedElement.id.in_(shared_element_ids))
        )
        shared_elements = {
            element.id: element
            for element in shared_elements_result.scalars().all()
        }

        entities: dict[int, CompanyEntity] = {}
        if entity_ids:
            entity_result = await self.session.execute(
                select(CompanyEntity).where(CompanyEntity.id.in_(entity_ids))
            )
            entities = {entity.id: entity for entity in entity_result.scalars().all()}

        serialized: list[CustomDatasheetItemOut] = []
        for item in items:
            shared_element = shared_elements.get(item.shared_element_id)
            entity = entities.get(item.entity_id) if item.entity_id is not None else None
            facility = entities.get(item.facility_id) if item.facility_id is not None else None
            serialized.append(
                CustomDatasheetItemOut.model_validate(
                    {
                        "id": item.id,
                        "shared_element_id": item.shared_element_id,
                        "shared_element_code": shared_element.code if shared_element else None,
                        "shared_element_name": shared_element.name if shared_element else None,
                        "shared_element_key": shared_element.element_key if shared_element else None,
                        "owner_layer": shared_element.owner_layer if shared_element else None,
                        "assignment_id": item.assignment_id,
                        "source_type": item.source_type,
                        "category": item.category,
                        "display_group": item.display_group,
                        "label_override": item.label_override,
                        "help_text": item.help_text,
                        "collection_scope": item.collection_scope,
                        "entity_id": item.entity_id,
                        "entity_name": entity.name if entity else None,
                        "facility_id": item.facility_id,
                        "facility_name": facility.name if facility else None,
                        "is_required": item.is_required,
                        "sort_order": item.sort_order,
                        "status": item.status,
                        "created_at": item.created_at,
                        "updated_at": item.updated_at,
                    }
                )
            )
        return serialized

    def _serialize_datasheet(
        self,
        datasheet: CustomDatasheet,
        *,
        counts: dict[str, int] | None = None,
    ) -> CustomDatasheetOut:
        counts = counts or {}
        return CustomDatasheetOut.model_validate(
            {
                "id": datasheet.id,
                "reporting_project_id": datasheet.reporting_project_id,
                "name": datasheet.name,
                "description": datasheet.description,
                "status": datasheet.status,
                "created_by": datasheet.created_by,
                "created_at": datasheet.created_at,
                "updated_at": datasheet.updated_at,
                "item_count": counts.get("item_count", 0),
                "framework_item_count": counts.get("framework_item_count", 0),
                "custom_item_count": counts.get("custom_item_count", 0),
            }
        )

    async def list_project_datasheets(
        self,
        project_id: int,
        ctx: RequestContext,
        page: int = 1,
        page_size: int = 50,
    ) -> CustomDatasheetListOut:
        await self._get_project_or_raise(project_id, ctx)
        datasheets, total = await self.repo.list_project_datasheets(project_id, page, page_size)
        counts_by_id = await self._build_counts([datasheet.id for datasheet in datasheets])
        return CustomDatasheetListOut(
            items=[
                self._serialize_datasheet(datasheet, counts=counts_by_id.get(datasheet.id))
                for datasheet in datasheets
            ],
            total=total,
        )

    async def create_datasheet(
        self,
        project_id: int,
        payload: CustomDatasheetCreate,
        ctx: RequestContext,
    ) -> CustomDatasheetOut:
        AuthPolicy.auditor_read_only(ctx)
        self._require_manager(ctx)
        project = await self._get_project_or_raise(project_id, ctx)
        datasheet = await self.repo.create_datasheet(
            reporting_project_id=project.id,
            name=payload.name,
            description=payload.description,
            status=payload.status,
            created_by=ctx.user_id,
        )
        return self._serialize_datasheet(datasheet)

    async def get_datasheet_detail(
        self,
        project_id: int,
        datasheet_id: int,
        ctx: RequestContext,
    ) -> CustomDatasheetDetailOut:
        _project, datasheet = await self._get_datasheet_or_raise(project_id, datasheet_id, ctx)
        items = await self.repo.list_datasheet_items(datasheet.id)
        counts = await self._build_counts([datasheet.id])
        base = self._serialize_datasheet(datasheet, counts=counts.get(datasheet.id))
        return CustomDatasheetDetailOut(
            **base.model_dump(),
            items=await self._serialize_items(items),
        )

    async def update_datasheet(
        self,
        project_id: int,
        datasheet_id: int,
        payload: CustomDatasheetUpdate,
        ctx: RequestContext,
    ) -> CustomDatasheetOut:
        AuthPolicy.auditor_read_only(ctx)
        self._require_manager(ctx)
        _project, datasheet = await self._get_datasheet_or_raise(project_id, datasheet_id, ctx)
        updated = await self.repo.update_datasheet(
            datasheet.id,
            **payload.model_dump(exclude_unset=True),
        )
        counts = await self._build_counts([updated.id])
        return self._serialize_datasheet(updated, counts=counts.get(updated.id))

    async def archive_datasheet(
        self,
        project_id: int,
        datasheet_id: int,
        ctx: RequestContext,
    ) -> CustomDatasheetOut:
        AuthPolicy.auditor_read_only(ctx)
        self._require_manager(ctx)
        _project, datasheet = await self._get_datasheet_or_raise(project_id, datasheet_id, ctx)
        updated = await self.repo.update_datasheet(datasheet.id, status="archived")
        counts = await self._build_counts([updated.id])
        return self._serialize_datasheet(updated, counts=counts.get(updated.id))

    async def search_add_item_options(
        self,
        project_id: int,
        datasheet_id: int,
        *,
        source: str,
        q: str | None,
        limit: int,
        ctx: RequestContext,
    ) -> CustomDatasheetOptionSearchListOut:
        project, _datasheet = await self._get_datasheet_or_raise(project_id, datasheet_id, ctx)
        term = (q or "").strip()

        if source == "framework":
            query = (
                select(
                    SharedElement.id,
                    SharedElement.code,
                    SharedElement.name,
                    SharedElement.element_key,
                    SharedElement.owner_layer,
                    SharedElement.concept_domain,
                    SharedElement.default_value_type,
                    SharedElement.default_unit_code,
                    Standard.id,
                    Standard.code,
                    Standard.name,
                    DisclosureRequirement.id,
                    DisclosureRequirement.code,
                    DisclosureRequirement.title,
                    RequirementItem.id,
                    RequirementItem.item_code,
                    RequirementItem.name,
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
                .where(
                    ReportingProjectStandard.reporting_project_id == project.id,
                    RequirementItemSharedElement.is_current == True,  # noqa: E712
                    SharedElement.is_current == True,  # noqa: E712
                    SharedElement.owner_layer == "internal_catalog",
                )
                .order_by(Standard.code, DisclosureRequirement.code, RequirementItem.id, SharedElement.id)
            )
            if term:
                like_term = f"%{term.lower()}%"
                query = query.where(
                    or_(
                        func.lower(SharedElement.code).like(like_term),
                        func.lower(SharedElement.name).like(like_term),
                        func.lower(Standard.code).like(like_term),
                        func.lower(Standard.name).like(like_term),
                        func.lower(DisclosureRequirement.code).like(like_term),
                        func.lower(DisclosureRequirement.title).like(like_term),
                        func.lower(func.coalesce(RequirementItem.item_code, "")).like(like_term),
                        func.lower(RequirementItem.name).like(like_term),
                    )
                )
            rows = (await self.session.execute(query.limit(max(limit * 4, 20)))).all()

            deduped: dict[int, CustomDatasheetOptionSearchOut] = {}
            for row in rows:
                shared_element_id = row[0]
                if shared_element_id in deduped:
                    continue
                deduped[shared_element_id] = CustomDatasheetOptionSearchOut(
                    shared_element_id=shared_element_id,
                    shared_element_code=row[1],
                    shared_element_name=row[2],
                    shared_element_key=row[3],
                    owner_layer=row[4],
                    source_type="framework",
                    concept_domain=row[5],
                    default_value_type=row[6],
                    default_unit_code=row[7],
                    suggested_category=self._suggest_category(row[5]),
                    standard_id=row[8],
                    standard_code=row[9],
                    standard_name=row[10],
                    disclosure_id=row[11],
                    disclosure_code=row[12],
                    disclosure_title=row[13],
                    requirement_item_id=row[14],
                    requirement_item_code=row[15],
                    requirement_item_name=row[16],
                )
                if len(deduped) >= limit:
                    break

            return CustomDatasheetOptionSearchListOut(items=list(deduped.values()), total=len(deduped))

        if source == "existing_custom":
            query = (
                select(SharedElement)
                .where(
                    SharedElement.owner_layer == "tenant_catalog",
                    SharedElement.organization_id == project.organization_id,
                    SharedElement.lifecycle_status == "active",
                )
                .order_by(SharedElement.code, SharedElement.id)
            )
            if term:
                like_term = f"%{term.lower()}%"
                query = query.where(
                    or_(
                        func.lower(SharedElement.code).like(like_term),
                        func.lower(SharedElement.name).like(like_term),
                        func.lower(func.coalesce(SharedElement.concept_domain, "")).like(like_term),
                    )
                )
            elements = list((await self.session.execute(query.limit(limit))).scalars().all())
            return CustomDatasheetOptionSearchListOut(
                items=[
                    CustomDatasheetOptionSearchOut(
                        shared_element_id=element.id,
                        shared_element_code=element.code,
                        shared_element_name=element.name,
                        shared_element_key=element.element_key,
                        owner_layer=element.owner_layer,
                        source_type="existing_custom",
                        concept_domain=element.concept_domain,
                        default_value_type=element.default_value_type,
                        default_unit_code=element.default_unit_code,
                        suggested_category=self._suggest_category(element.concept_domain),
                    )
                    for element in elements
                ],
                total=len(elements),
            )

        raise AppError("INVALID_SOURCE_TYPE", 422, f"Unsupported source '{source}'")

    async def add_item(
        self,
        project_id: int,
        datasheet_id: int,
        payload: CustomDatasheetItemCreate,
        ctx: RequestContext,
    ) -> CustomDatasheetItemOut:
        AuthPolicy.auditor_read_only(ctx)
        self._require_manager(ctx)
        project, datasheet = await self._get_datasheet_or_raise(project_id, datasheet_id, ctx)
        shared_element = await self._get_shared_element_or_raise(payload.shared_element_id)
        await self._validate_source_type(
            shared_element,
            source_type=payload.source_type,
            organization_id=project.organization_id,
        )
        duplicate = await self.repo.find_item_duplicate(
            datasheet_id=datasheet.id,
            shared_element_id=shared_element.id,
            collection_scope=payload.collection_scope,
            entity_id=payload.entity_id,
            facility_id=payload.facility_id,
        )
        if duplicate:
            raise AppError("CONFLICT", 409, "This metric context is already in the datasheet")

        assignment = await self._resolve_assignment_for_item(
            project,
            shared_element_id=shared_element.id,
            assignment_id=payload.assignment_id,
            collection_scope=payload.collection_scope,
            entity_id=payload.entity_id,
            facility_id=payload.facility_id,
        )
        item = await self.repo.create_datasheet_item(
            custom_datasheet_id=datasheet.id,
            reporting_project_id=project.id,
            shared_element_id=shared_element.id,
            assignment_id=assignment.id if assignment else None,
            source_type=payload.source_type,
            category=payload.category,
            display_group=payload.display_group,
            label_override=payload.label_override,
            help_text=payload.help_text,
            collection_scope=payload.collection_scope,
            entity_id=payload.entity_id,
            facility_id=payload.facility_id,
            is_required=payload.is_required,
            sort_order=payload.sort_order,
            status="active",
            created_by=ctx.user_id,
        )
        serialized = await self._serialize_items([item])
        return serialized[0]

    async def create_custom_metric_and_add_item(
        self,
        project_id: int,
        datasheet_id: int,
        payload: CustomDatasheetCreateCustomMetric,
        ctx: RequestContext,
    ) -> CustomDatasheetItemOut:
        AuthPolicy.auditor_read_only(ctx)
        self._require_manager(ctx)
        project, datasheet = await self._get_datasheet_or_raise(project_id, datasheet_id, ctx)
        shared_element = await self._create_custom_metric(project, payload)

        duplicate = await self.repo.find_item_duplicate(
            datasheet_id=datasheet.id,
            shared_element_id=shared_element.id,
            collection_scope=payload.collection_scope,
            entity_id=payload.entity_id,
            facility_id=payload.facility_id,
        )
        if duplicate:
            raise AppError("CONFLICT", 409, "This metric context is already in the datasheet")

        assignment = await self._resolve_assignment_for_item(
            project,
            shared_element_id=shared_element.id,
            assignment_id=None,
            collection_scope=payload.collection_scope,
            entity_id=payload.entity_id,
            facility_id=payload.facility_id,
        )
        item = await self.repo.create_datasheet_item(
            custom_datasheet_id=datasheet.id,
            reporting_project_id=project.id,
            shared_element_id=shared_element.id,
            assignment_id=assignment.id if assignment else None,
            source_type="new_custom",
            category=payload.category,
            display_group=payload.display_group,
            label_override=payload.label_override,
            help_text=payload.help_text,
            collection_scope=payload.collection_scope,
            entity_id=payload.entity_id,
            facility_id=payload.facility_id,
            is_required=payload.is_required,
            sort_order=payload.sort_order,
            status="active",
            created_by=ctx.user_id,
        )
        serialized = await self._serialize_items([item])
        return serialized[0]

    async def update_item(
        self,
        project_id: int,
        datasheet_id: int,
        item_id: int,
        payload: CustomDatasheetItemUpdate,
        ctx: RequestContext,
    ) -> CustomDatasheetItemOut:
        AuthPolicy.auditor_read_only(ctx)
        self._require_manager(ctx)
        project, datasheet = await self._get_datasheet_or_raise(project_id, datasheet_id, ctx)
        item = await self.repo.get_datasheet_item_or_raise(item_id)
        if item.custom_datasheet_id != datasheet.id:
            raise AppError("FORBIDDEN", 403, "Custom datasheet item belongs to another datasheet")

        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            serialized = await self._serialize_items([item])
            return serialized[0]

        assignment_related = {"assignment_id", "collection_scope", "entity_id", "facility_id"}
        if assignment_related.intersection(updates):
            collection_scope = updates.get("collection_scope", item.collection_scope)
            entity_id = updates.get("entity_id", item.entity_id)
            facility_id = updates.get("facility_id", item.facility_id)
            duplicate = await self.repo.find_item_duplicate(
                datasheet_id=datasheet.id,
                shared_element_id=item.shared_element_id,
                collection_scope=collection_scope,
                entity_id=entity_id,
                facility_id=facility_id,
            )
            if duplicate and duplicate.id != item.id:
                raise AppError("CONFLICT", 409, "This metric context is already in the datasheet")
            assignment = await self._resolve_assignment_for_item(
                project,
                shared_element_id=item.shared_element_id,
                assignment_id=updates.get("assignment_id"),
                collection_scope=collection_scope,
                entity_id=entity_id,
                facility_id=facility_id,
            )
            updates["assignment_id"] = assignment.id if assignment else None
            updates["collection_scope"] = collection_scope
            updates["entity_id"] = entity_id
            updates["facility_id"] = facility_id

        updated = await self.repo.update_datasheet_item(item.id, **updates)
        serialized = await self._serialize_items([updated])
        return serialized[0]

    async def archive_item(
        self,
        project_id: int,
        datasheet_id: int,
        item_id: int,
        ctx: RequestContext,
    ) -> CustomDatasheetItemOut:
        AuthPolicy.auditor_read_only(ctx)
        self._require_manager(ctx)
        _project, datasheet = await self._get_datasheet_or_raise(project_id, datasheet_id, ctx)
        item = await self.repo.get_datasheet_item_or_raise(item_id)
        if item.custom_datasheet_id != datasheet.id:
            raise AppError("FORBIDDEN", 403, "Custom datasheet item belongs to another datasheet")
        updated = await self.repo.archive_datasheet_item(item.id)
        serialized = await self._serialize_items([updated])
        return serialized[0]
