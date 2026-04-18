from __future__ import annotations

from collections import Counter

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.db.models.boundary import BoundaryMembership
from app.db.models.form_config import FormConfiguration
from app.db.models.mapping import RequirementItemSharedElement
from app.db.models.project import MetricAssignment, ReportingProject, ReportingProjectStandard
from app.db.models.requirement_item import RequirementItem
from app.db.models.shared_element import SharedElement
from app.db.models.standard import DisclosureRequirement
from app.policies.auth_policy import AuthPolicy
from app.repositories.form_config_repo import FormConfigRepository
from app.schemas.form_config import (
    FormConfigCreate,
    FormConfigHealthIssueOut,
    FormConfigHealthOut,
    FormFieldSchema,
    FormConfigListOut,
    FormConfigOut,
    FormStepSchema,
    FormConfigUpdate,
)


class FormConfigService:
    def __init__(self, repo: FormConfigRepository, session: AsyncSession):
        self.repo = repo
        self.session = session

    async def _get_project_or_raise(self, project_id: int, ctx: RequestContext) -> ReportingProject:
        result = await self.session.execute(
            select(ReportingProject).where(ReportingProject.id == project_id)
        )
        project = result.scalar_one_or_none()
        if not project:
            raise AppError("NOT_FOUND", 404, f"Project {project_id} not found")
        if ctx.organization_id and project.organization_id != ctx.organization_id and not ctx.is_platform_admin:
            raise AppError("FORBIDDEN", 403, "Project belongs to another organization")
        return project

    async def _get_config_or_raise(self, config_id: int, ctx: RequestContext) -> FormConfiguration:
        fc = await self.repo.get_or_raise(config_id)
        if ctx.organization_id and fc.organization_id != ctx.organization_id and not ctx.is_platform_admin:
            raise AppError("FORBIDDEN", 403, "Form configuration belongs to another organization")
        return fc

    async def _validate_scope_project(self, project_id: int | None, ctx: RequestContext) -> ReportingProject | None:
        if project_id is None:
            return None
        return await self._get_project_or_raise(project_id, ctx)

    def _flatten_fields(self, config: dict) -> list[FormFieldSchema]:
        if not isinstance(config, dict):
            raise ValueError("Form configuration must be a JSON object")

        raw_steps = config.get("steps", [])
        if not isinstance(raw_steps, list):
            raise ValueError("Form configuration must contain a 'steps' array")

        fields: list[FormFieldSchema] = []
        for raw_step in raw_steps:
            step = FormStepSchema.model_validate(raw_step)
            fields.extend(step.fields)
        return fields

    async def _build_health(
        self,
        config: FormConfiguration,
        target_project: ReportingProject | None,
    ) -> FormConfigHealthOut:
        try:
            fields = self._flatten_fields(config.config or {})
        except (ValidationError, ValueError):
            return FormConfigHealthOut(
                status="stale",
                is_stale=True,
                target_project_id=target_project.id if target_project else None,
                issue_count=1,
                issues=[
                    FormConfigHealthIssueOut(
                        code="INVALID_CONFIG",
                        message="Configuration JSON is invalid and cannot be resolved safely.",
                        affected_fields=0,
                    )
                ],
            )

        assignment_scoped_fields = sum(1 for field in fields if field.assignment_id is not None)
        context_scoped_fields = sum(
            1
            for field in fields
            if field.assignment_id is None and (field.entity_id is not None or field.facility_id is not None)
        )

        if target_project is None:
            return FormConfigHealthOut(
                status="not_applicable",
                is_stale=False,
                field_count=len(fields),
                assignment_scoped_fields=assignment_scoped_fields,
                context_scoped_fields=context_scoped_fields,
            )

        assignment_result = await self.session.execute(
            select(
                MetricAssignment.id,
                MetricAssignment.shared_element_id,
                MetricAssignment.entity_id,
                MetricAssignment.facility_id,
                MetricAssignment.updated_at,
            ).where(MetricAssignment.reporting_project_id == target_project.id)
        )
        assignments = assignment_result.all()
        assignments_by_id = {
            assignment_id: {
                "id": assignment_id,
                "shared_element_id": shared_element_id,
                "entity_id": entity_id,
                "facility_id": facility_id,
            }
            for assignment_id, shared_element_id, entity_id, facility_id, _updated_at in assignments
        }
        assignments_by_context: dict[tuple[int, int | None, int | None], list[int]] = {}
        assignments_by_element: dict[int, list[int]] = {}
        latest_assignment_updated_at = None
        for assignment_id, shared_element_id, entity_id, facility_id, updated_at in assignments:
            assignments_by_context.setdefault(
                (shared_element_id, entity_id, facility_id),
                [],
            ).append(assignment_id)
            assignments_by_element.setdefault(shared_element_id, []).append(assignment_id)
            if updated_at and (latest_assignment_updated_at is None or updated_at > latest_assignment_updated_at):
                latest_assignment_updated_at = updated_at

        included_scope_entity_ids: set[int] = set()
        latest_boundary_updated_at = None
        if target_project.boundary_definition_id is not None:
            boundary_result = await self.session.execute(
                select(
                    BoundaryMembership.entity_id,
                    BoundaryMembership.included,
                    BoundaryMembership.updated_at,
                ).where(BoundaryMembership.boundary_definition_id == target_project.boundary_definition_id)
            )
            for entity_id, included, updated_at in boundary_result.all():
                if included:
                    included_scope_entity_ids.add(entity_id)
                if updated_at and (latest_boundary_updated_at is None or updated_at > latest_boundary_updated_at):
                    latest_boundary_updated_at = updated_at

        issue_counts: Counter[str] = Counter()
        covered_assignment_ids: set[int] = set()
        row_aware_element_ids: set[int] = set()

        for field in fields:
            scope_entity_id = field.facility_id or field.entity_id

            if field.assignment_id is not None:
                row_aware_element_ids.add(field.shared_element_id)
                assignment = assignments_by_id.get(field.assignment_id)
                if assignment is None:
                    issue_counts["MISSING_ASSIGNMENT"] += 1
                    continue

                covered_assignment_ids.add(field.assignment_id)
                if assignment["shared_element_id"] != field.shared_element_id:
                    issue_counts["ASSIGNMENT_ELEMENT_CHANGED"] += 1

                if (
                    (field.entity_id is not None and assignment["entity_id"] != field.entity_id)
                    or (field.facility_id is not None and assignment["facility_id"] != field.facility_id)
                ):
                    issue_counts["ASSIGNMENT_CONTEXT_CHANGED"] += 1

                scope_entity_id = assignment["facility_id"] or assignment["entity_id"]
            elif field.entity_id is not None or field.facility_id is not None:
                row_aware_element_ids.add(field.shared_element_id)
                matches = assignments_by_context.get(
                    (field.shared_element_id, field.entity_id, field.facility_id),
                    [],
                )
                if not matches:
                    issue_counts["UNRESOLVED_CONTEXT"] += 1
                else:
                    covered_assignment_ids.update(matches)
                    if len(matches) > 1:
                        issue_counts["AMBIGUOUS_CONTEXT"] += 1

            if (
                target_project.boundary_definition_id is not None
                and scope_entity_id is not None
                and scope_entity_id not in included_scope_entity_ids
            ):
                issue_counts["OUTSIDE_BOUNDARY"] += 1

        for element_id in row_aware_element_ids:
            for assignment_id in assignments_by_element.get(element_id, []):
                if assignment_id not in covered_assignment_ids:
                    issue_counts["UNCONFIGURED_ASSIGNMENT"] += 1

        issue_messages = {
            "MISSING_ASSIGNMENT": "Some row-aware fields reference assignments that no longer exist.",
            "ASSIGNMENT_ELEMENT_CHANGED": "Some row-aware fields point to assignments with a different shared element than expected.",
            "ASSIGNMENT_CONTEXT_CHANGED": "Some row-aware fields point to assignments whose entity or facility scope changed.",
            "UNRESOLVED_CONTEXT": "Some context-aware fields no longer match any live assignment.",
            "AMBIGUOUS_CONTEXT": "Some context-aware fields now match multiple assignments and need regeneration.",
            "OUTSIDE_BOUNDARY": "Some configured fields are now outside the active project boundary.",
            "UNCONFIGURED_ASSIGNMENT": "Some live assignments are not covered by the current row-aware config.",
        }
        issues = [
            FormConfigHealthIssueOut(
                code=code,
                message=issue_messages[code],
                affected_fields=count,
            )
            for code, count in issue_counts.items()
            if count > 0
        ]

        return FormConfigHealthOut(
            status="stale" if issues else "healthy",
            is_stale=bool(issues),
            target_project_id=target_project.id,
            field_count=len(fields),
            assignment_scoped_fields=assignment_scoped_fields,
            context_scoped_fields=context_scoped_fields,
            issue_count=sum(issue_counts.values()),
            issues=issues,
            latest_assignment_updated_at=latest_assignment_updated_at,
            latest_boundary_updated_at=latest_boundary_updated_at,
        )

    async def _serialize_config(
        self,
        config: FormConfiguration,
        *,
        resolved_project: ReportingProject | None = None,
    ) -> FormConfigOut:
        health_project = resolved_project
        if health_project is None and config.project_id is not None:
            health_project = await self._get_project_or_raise(
                config.project_id,
                RequestContext(
                    user_id=0,
                    email="system@local",
                    role="platform_admin",
                    organization_id=config.organization_id,
                    is_platform_admin=True,
                ),
            )

        if resolved_project is not None:
            resolution_scope = "project" if config.project_id == resolved_project.id else "organization_default"
            resolved_for_project_id = resolved_project.id
        elif config.project_id is not None:
            resolution_scope = "project"
            resolved_for_project_id = config.project_id
        elif config.project_id is None:
            resolution_scope = "organization_default"
            resolved_for_project_id = None
        else:
            resolution_scope = None
            resolved_for_project_id = None

        return FormConfigOut(
            id=config.id,
            organization_id=config.organization_id,
            project_id=config.project_id,
            name=config.name,
            description=config.description,
            config=config.config,
            is_active=config.is_active,
            created_by=config.created_by,
            created_at=config.created_at,
            updated_at=config.updated_at,
            resolved_for_project_id=resolved_for_project_id,
            resolution_scope=resolution_scope,
            health=await self._build_health(config, health_project),
        )

    async def _create_generated_config(
        self,
        project: ReportingProject,
        *,
        created_by: int,
        name: str,
        description: str,
    ) -> FormConfigOut:
        # Get standards attached to project
        std_result = await self.session.execute(
            select(ReportingProjectStandard.standard_id).where(
                ReportingProjectStandard.reporting_project_id == project.id
            )
        )
        standard_ids = [row[0] for row in std_result.all()]
        if not standard_ids:
            raise AppError("NO_STANDARDS", 422, "Project has no standards attached")

        items_result = await self.session.execute(
            select(
                RequirementItem.id,
                RequirementItem.item_code,
                RequirementItem.name,
                RequirementItem.item_type,
                RequirementItemSharedElement.shared_element_id,
                SharedElement.code.label("element_code"),
                SharedElement.name.label("element_name"),
            )
            .join(DisclosureRequirement, DisclosureRequirement.id == RequirementItem.disclosure_requirement_id)
            .join(RequirementItemSharedElement, RequirementItemSharedElement.requirement_item_id == RequirementItem.id)
            .join(SharedElement, SharedElement.id == RequirementItemSharedElement.shared_element_id)
            .where(DisclosureRequirement.standard_id.in_(standard_ids))
            .order_by(RequirementItem.id)
        )
        rows = items_result.all()
        shared_element_occurrences = Counter(row.shared_element_id for row in rows)

        assignment_result = await self.session.execute(
            select(
                MetricAssignment.id,
                MetricAssignment.shared_element_id,
                MetricAssignment.entity_id,
                MetricAssignment.facility_id,
            )
            .where(MetricAssignment.reporting_project_id == project.id)
            .order_by(
                MetricAssignment.shared_element_id,
                MetricAssignment.entity_id,
                MetricAssignment.facility_id,
                MetricAssignment.id,
            )
        )
        assignments_by_element: dict[int, list[dict[str, int | None]]] = {}
        for assignment_id, shared_element_id, entity_id, facility_id in assignment_result.all():
            assignments_by_element.setdefault(shared_element_id, []).append(
                {
                    "assignment_id": assignment_id,
                    "entity_id": entity_id,
                    "facility_id": facility_id,
                }
            )

        steps_map: dict[str, list[dict]] = {}
        step_field_by_context: dict[str, dict[str, dict]] = {}
        for item_id, item_code, name_value, item_type, se_id, se_code, se_name in rows:
            assignment_contexts = assignments_by_element.get(se_id)
            if not assignment_contexts:
                if shared_element_occurrences[se_id] < 2:
                    continue
                assignment_contexts = [
                    {
                        "assignment_id": None,
                        "entity_id": None,
                        "facility_id": None,
                    }
                ]

            step_name = item_type or "general"
            if step_name not in steps_map:
                steps_map[step_name] = []
                step_field_by_context[step_name] = {}

            help_text = f"{item_code}: {name_value}" if item_code else name_value
            for assignment_context in assignment_contexts:
                assignment_id = assignment_context["assignment_id"]
                field_key = (
                    f"assignment:{assignment_id}" if assignment_id is not None else f"element:{se_id}"
                )

                existing_field = step_field_by_context[step_name].get(field_key)
                if existing_field is None:
                    field = {
                        "shared_element_id": se_id,
                        "requirement_item_id": item_id,
                        "assignment_id": assignment_context["assignment_id"],
                        "entity_id": assignment_context["entity_id"],
                        "facility_id": assignment_context["facility_id"],
                        "visible": True,
                        "required": True,
                        "help_text": help_text,
                        "tooltip": f"{se_code}: {se_name}",
                        "order": len(steps_map[step_name]) + 1,
                    }
                    steps_map[step_name].append(field)
                    step_field_by_context[step_name][field_key] = field
                    continue

                existing_help = existing_field.get("help_text") or ""
                help_lines = [line for line in existing_help.split("\n") if line]
                if help_text not in help_lines:
                    help_lines.append(help_text)
                    existing_field["help_text"] = "\n".join(help_lines)

        config = {
            "steps": [
                {
                    "id": f"step-{i+1}",
                    "title": step_name.replace("_", " ").title(),
                    "fields": fields,
                }
                for i, (step_name, fields) in enumerate(steps_map.items())
            ]
        }

        await self.repo.deactivate_scope(project.organization_id, project.id)
        fc = await self.repo.create(
            organization_id=project.organization_id,
            project_id=project.id,
            name=name,
            description=description,
            config=config,
            is_active=True,
            created_by=created_by,
        )
        return await self._serialize_config(fc, resolved_project=project)

    async def create(
        self, payload: FormConfigCreate, ctx: RequestContext
    ) -> FormConfigOut:
        AuthPolicy.require_manager_or_admin(ctx)
        if not ctx.organization_id:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required")

        await self._validate_scope_project(payload.project_id, ctx)
        if payload.is_active:
            await self.repo.deactivate_scope(ctx.organization_id, payload.project_id)

        fc = await self.repo.create(
            organization_id=ctx.organization_id,
            project_id=payload.project_id,
            name=payload.name,
            description=payload.description,
            config=payload.config,
            is_active=payload.is_active,
            created_by=ctx.user_id,
        )
        return await self._serialize_config(fc)

    async def list_configs(
        self, ctx: RequestContext, page: int = 1, page_size: int = 50
    ) -> FormConfigListOut:
        if not ctx.organization_id:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required")
        items, total = await self.repo.list_by_org(ctx.organization_id, page, page_size)
        return FormConfigListOut(
            items=[await self._serialize_config(fc) for fc in items],
            total=total,
        )

    async def get_config(self, config_id: int, ctx: RequestContext) -> FormConfigOut:
        fc = await self._get_config_or_raise(config_id, ctx)
        return await self._serialize_config(fc)

    async def update_config(
        self, config_id: int, payload: FormConfigUpdate, ctx: RequestContext
    ) -> FormConfigOut:
        AuthPolicy.require_manager_or_admin(ctx)
        fc = await self._get_config_or_raise(config_id, ctx)
        updates = payload.model_dump(exclude_unset=True)
        next_project_id = updates.get("project_id", fc.project_id)
        await self._validate_scope_project(next_project_id, ctx)
        if updates.get("is_active", fc.is_active):
            await self.repo.deactivate_scope(fc.organization_id, next_project_id, exclude_config_id=fc.id)
        updated = await self.repo.update(config_id, **updates)
        return await self._serialize_config(updated)

    async def get_for_project(self, project_id: int, ctx: RequestContext) -> FormConfigOut | None:
        project = await self._get_project_or_raise(project_id, ctx)
        fc = await self.repo.get_active_for_project(project_id, project.organization_id)
        if not fc:
            return None
        return await self._serialize_config(fc, resolved_project=project)

    async def generate_default(
        self, project_id: int, ctx: RequestContext
    ) -> FormConfigOut:
        AuthPolicy.require_manager_or_admin(ctx)
        if not ctx.organization_id:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required")
        project = await self._get_project_or_raise(project_id, ctx)
        return await self._create_generated_config(
            project,
            created_by=ctx.user_id,
            name=f"Auto-generated config for project #{project_id}",
            description="Generated from the current live project assignments",
        )

    async def resync_project_config(self, project_id: int, ctx: RequestContext) -> FormConfigOut:
        AuthPolicy.require_manager_or_admin(ctx)
        if not ctx.organization_id:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required")
        project = await self._get_project_or_raise(project_id, ctx)
        return await self._create_generated_config(
            project,
            created_by=ctx.user_id,
            name=f"Auto-synced config for project #{project_id}",
            description="Re-synced from the current live project assignments",
        )
