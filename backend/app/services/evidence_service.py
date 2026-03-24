from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select

from app.core.access import get_data_point_for_ctx
from app.core.dashboard_cache import invalidate_dashboard_project
from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.db.models.data_point import DataPoint
from app.db.models.evidence import DataPointEvidence, EvidenceFile, EvidenceLink
from app.db.models.project import ReportingProject, ReportingProjectStandard
from app.db.models.requirement_item import RequirementItem
from app.db.models.requirement_item_evidence import RequirementItemEvidence
from app.db.models.shared_element import SharedElement
from app.db.models.standard import DisclosureRequirement, Standard
from app.db.models.user import User
from app.events.bus import EvidenceCreated, get_event_bus
from app.infrastructure.storage import BaseStorage, generate_storage_key, get_storage
from app.policies.evidence_policy import EvidencePolicy
from app.repositories.audit_repo import AuditRepository
from app.repositories.data_point_repo import DataPointRepository
from app.repositories.evidence_repo import EvidenceRepository
from app.repositories.project_repo import ProjectRepository
from app.schemas.evidence import EvidenceCreate, EvidenceListOut, EvidenceOut


class EvidenceService:
    def __init__(
        self,
        repo: EvidenceRepository,
        dp_repo: DataPointRepository,
        project_repo: ProjectRepository,
        audit_repo: AuditRepository | None = None,
        storage: BaseStorage | None = None,
    ):
        self.repo = repo
        self.dp_repo = dp_repo
        self.project_repo = project_repo
        self.audit_repo = audit_repo
        self.storage = storage or get_storage()

    async def _audit(self, action: str, entity_id: int, ctx: RequestContext, changes: dict | None = None):
        if self.audit_repo:
            await self.audit_repo.log(
                entity_type="Evidence",
                entity_id=entity_id,
                action=action,
                user_id=ctx.user_id,
                organization_id=ctx.organization_id,
                changes=changes,
                performed_by_platform_admin=ctx.is_platform_admin,
            )

    async def create(self, payload: EvidenceCreate, ctx: RequestContext) -> EvidenceOut:
        EvidencePolicy().can_create(ctx)
        if not ctx.organization_id:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required")

        ev = await self.repo.create(
            org_id=ctx.organization_id,
            type=payload.type,
            title=payload.title,
            description=payload.description,
            source_type=payload.source_type,
            created_by=ctx.user_id,
        )

        if payload.type == "file" and payload.file_name:
            await self.repo.create_file(
                evidence_id=ev.id,
                file_name=payload.file_name,
                file_uri=payload.file_uri or "",
                mime_type=payload.mime_type,
                file_size=payload.file_size,
            )
        elif payload.type == "link" and payload.url:
            await self.repo.create_link(
                evidence_id=ev.id,
                url=payload.url,
                label=payload.label,
            )

        await self._audit("evidence_created", ev.id, ctx, {"type": payload.type})
        await get_event_bus().publish(
            EvidenceCreated(
                evidence_id=ev.id,
                organization_id=ctx.organization_id,
                created_by=ctx.user_id,
                type=payload.type,
            )
        )
        return EvidenceOut.model_validate(
            {
                "id": ev.id,
                "organization_id": ev.organization_id,
                "type": ev.type,
                "title": ev.title,
                "description": ev.description,
                "source_type": ev.source_type,
                "created_by": ev.created_by,
                "created_at": ev.created_at,
                "upload_date": ev.created_at,
                "binding_status": "unbound",
                "linked_data_points": [],
                "linked_requirement_items": [],
            }
        )

    async def create_with_file(
        self, file_data: bytes, file_name: str, mime_type: str, title: str,
        description: str | None, ctx: RequestContext,
    ) -> EvidenceOut:
        EvidencePolicy().can_create(ctx)
        if not ctx.organization_id:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required")

        key = generate_storage_key(ctx.organization_id, file_name)
        result = await self.storage.upload(key, file_data, mime_type)

        ev = await self.repo.create(
            org_id=ctx.organization_id,
            type="file",
            title=title,
            description=description,
            source_type="manual",
            created_by=ctx.user_id,
        )
        await self.repo.create_file(
            evidence_id=ev.id,
            file_name=file_name,
            file_uri=key,
            mime_type=mime_type,
            file_size=result.size,
        )

        await self._audit("evidence_uploaded", ev.id, ctx, {"file_name": file_name, "size": result.size})
        await get_event_bus().publish(
            EvidenceCreated(
                evidence_id=ev.id,
                organization_id=ctx.organization_id,
                created_by=ctx.user_id,
                type="file",
            )
        )
        return EvidenceOut.model_validate({
            "id": ev.id,
            "organization_id": ev.organization_id,
            "type": "file",
            "title": ev.title,
            "description": ev.description,
            "source_type": ev.source_type,
            "created_by": ev.created_by,
            "created_at": ev.created_at,
            "upload_date": ev.created_at,
            "file_name": file_name,
            "file_size": result.size,
            "mime_type": mime_type,
            "binding_status": "unbound",
            "linked_data_points": [],
            "linked_requirement_items": [],
        })

    async def get_download_url(self, evidence_id: int, ctx: RequestContext) -> str:
        ev = await self.repo.get_or_raise(evidence_id)
        if ev.organization_id != ctx.organization_id and not ctx.is_platform_admin:
            raise AppError("FORBIDDEN", 403, "Evidence belongs to another organization")
        file_row = await self.repo.session.execute(
            select(EvidenceFile.file_uri).where(EvidenceFile.evidence_id == evidence_id)
        )
        file_uri = file_row.scalar_one_or_none()
        if not file_uri:
            raise AppError("NOT_FOUND", 404, "No file associated with this evidence")
        return await self.storage.get_url(file_uri)

    async def list_evidences(
        self, ctx: RequestContext, page: int = 1, page_size: int = 50
    ) -> EvidenceListOut:
        if not ctx.organization_id:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required")
        created_by = ctx.user_id if ctx.role == "collector" else None
        items, total = await self.repo.list_by_org(
            ctx.organization_id,
            page,
            page_size,
            created_by=created_by,
        )
        context = await self._load_context(items)
        return EvidenceListOut(
            items=[self._serialize(item, context) for item in items],
            total=total,
        )

    async def link_to_data_point(
        self, dp_id: int, evidence_id: int, ctx: RequestContext
    ) -> dict:
        EvidencePolicy().can_create(ctx)
        evidence = await self.repo.get_or_raise(evidence_id)
        if evidence.organization_id != ctx.organization_id and not ctx.is_platform_admin:
            raise AppError("FORBIDDEN", 403, "Evidence belongs to another organization")

        data_point, _project, _assignment = await get_data_point_for_ctx(self.repo.session, dp_id, ctx)
        await self.repo.link_to_data_point(dp_id, evidence_id, ctx.user_id)
        await self._audit("evidence_linked", evidence_id, ctx, {"data_point_id": dp_id})
        await invalidate_dashboard_project(data_point.reporting_project_id)
        return {"data_point_id": dp_id, "evidence_id": evidence_id, "linked": True}

    async def _require_bindable_requirement_item(
        self,
        requirement_item_id: int,
        ctx: RequestContext,
    ) -> RequirementItem:
        if not ctx.organization_id:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required")

        result = await self.repo.session.execute(
            select(RequirementItem)
            .join(
                DisclosureRequirement,
                DisclosureRequirement.id == RequirementItem.disclosure_requirement_id,
            )
            .join(Standard, Standard.id == DisclosureRequirement.standard_id)
            .join(
                ReportingProjectStandard,
                ReportingProjectStandard.standard_id == Standard.id,
            )
            .join(
                ReportingProject,
                ReportingProject.id == ReportingProjectStandard.reporting_project_id,
            )
            .where(
                RequirementItem.id == requirement_item_id,
                RequirementItem.is_current == True,  # noqa: E712
                Standard.is_active == True,  # noqa: E712
                ReportingProject.organization_id == ctx.organization_id,
            )
        )
        requirement_item = result.scalar_one_or_none()
        if not requirement_item:
            raise AppError(
                "INVALID_REQUIREMENT_ITEM_CONTEXT",
                422,
                "Requirement item is not active in the current organization reporting context",
            )
        return requirement_item

    async def bind_to_requirement(
        self,
        evidence_id: int,
        requirement_item_id: int,
        ctx: RequestContext,
    ) -> dict:
        EvidencePolicy().can_create(ctx)
        evidence = await self.repo.get_or_raise(evidence_id)
        if evidence.organization_id != ctx.organization_id and not ctx.is_platform_admin:
            raise AppError("FORBIDDEN", 403, "Evidence belongs to another organization")

        requirement_item = await self._require_bindable_requirement_item(requirement_item_id, ctx)
        existing = await self.repo.session.execute(
            select(RequirementItemEvidence).where(
                RequirementItemEvidence.requirement_item_id == requirement_item.id,
                RequirementItemEvidence.evidence_id == evidence_id,
            )
        )
        if existing.scalar_one_or_none():
            raise AppError("ALREADY_LINKED", 409, "Evidence already linked to this requirement item")

        binding = RequirementItemEvidence(
            requirement_item_id=requirement_item.id,
            evidence_id=evidence_id,
            linked_by=ctx.user_id,
        )
        self.repo.session.add(binding)
        await self.repo.session.flush()
        await self._audit(
            "evidence_linked_requirement",
            evidence_id,
            ctx,
            {"requirement_item_id": requirement_item.id},
        )
        return {
            "evidence_id": evidence_id,
            "requirement_item_id": requirement_item.id,
            "linked": True,
        }

    async def _load_context(self, items: list) -> dict:
        evidence_ids = [item.id for item in items]
        if not evidence_ids:
            return {
                "files": {},
                "links": {},
                "user_names": {},
                "linked_data_points": defaultdict(list),
                "linked_requirements": defaultdict(list),
            }

        result = await self.repo.session.execute(
            select(
                EvidenceFile.evidence_id,
                EvidenceFile.file_name,
                EvidenceFile.file_uri,
                EvidenceFile.mime_type,
                EvidenceFile.file_size,
            ).where(EvidenceFile.evidence_id.in_(evidence_ids))
        )
        files = {
            evidence_id: {
                "file_name": file_name,
                "url": file_uri,
                "mime_type": mime_type,
                "file_size": file_size,
            }
            for evidence_id, file_name, file_uri, mime_type, file_size in result.all()
        }

        result = await self.repo.session.execute(
            select(
                EvidenceLink.evidence_id,
                EvidenceLink.url,
                EvidenceLink.label,
            ).where(EvidenceLink.evidence_id.in_(evidence_ids))
        )
        links = {
            evidence_id: {
                "url": url,
                "label": label,
            }
            for evidence_id, url, label in result.all()
        }

        result = await self.repo.session.execute(
            select(User.id, User.full_name).where(
                User.id.in_([item.created_by for item in items if item.created_by is not None])
            )
        )
        user_names = {user_id: full_name for user_id, full_name in result.all()}

        result = await self.repo.session.execute(
            select(
                DataPointEvidence.evidence_id,
                DataPointEvidence.data_point_id,
                SharedElement.code,
                SharedElement.name,
            )
            .join(DataPoint, DataPoint.id == DataPointEvidence.data_point_id)
            .join(SharedElement, SharedElement.id == DataPoint.shared_element_id)
            .where(DataPointEvidence.evidence_id.in_(evidence_ids))
        )
        linked_data_points: dict[int, list[dict]] = defaultdict(list)
        for evidence_id, data_point_id, code, name in result.all():
            linked_data_points[evidence_id].append(
                {
                    "data_point_id": data_point_id,
                    "code": code or f"DP-{data_point_id}",
                    "label": name or f"Data point {data_point_id}",
                }
            )

        result = await self.repo.session.execute(
            select(
                RequirementItemEvidence.evidence_id,
                RequirementItem.id,
                RequirementItem.item_code,
                RequirementItem.name,
            )
            .join(
                RequirementItem,
                RequirementItem.id == RequirementItemEvidence.requirement_item_id,
            )
            .where(RequirementItemEvidence.evidence_id.in_(evidence_ids))
        )
        linked_requirements: dict[int, list[dict]] = defaultdict(list)
        for evidence_id, requirement_item_id, code, name in result.all():
            linked_requirements[evidence_id].append(
                {
                    "requirement_item_id": requirement_item_id,
                    "code": code or f"ITEM-{requirement_item_id}",
                    "description": name,
                }
            )

        return {
            "files": files,
            "links": links,
            "user_names": user_names,
            "linked_data_points": linked_data_points,
            "linked_requirements": linked_requirements,
        }

    def _serialize(self, evidence, context: dict) -> EvidenceOut:
        file_meta = context["files"].get(evidence.id, {})
        link_meta = context["links"].get(evidence.id, {})
        linked_data_points = context["linked_data_points"].get(evidence.id, [])
        linked_requirements = context["linked_requirements"].get(evidence.id, [])
        return EvidenceOut.model_validate(
            {
                "id": evidence.id,
                "organization_id": evidence.organization_id,
                "type": evidence.type,
                "title": evidence.title,
                "description": evidence.description,
                "source_type": evidence.source_type,
                "created_by": evidence.created_by,
                "created_by_name": context["user_names"].get(evidence.created_by),
                "created_at": evidence.created_at,
                "upload_date": evidence.created_at,
                "url": file_meta.get("url") or link_meta.get("url"),
                "file_name": file_meta.get("file_name"),
                "file_size": file_meta.get("file_size"),
                "mime_type": file_meta.get("mime_type"),
                "binding_status": "bound" if linked_data_points or linked_requirements else "unbound",
                "linked_data_points": linked_data_points,
                "linked_requirement_items": linked_requirements,
            }
        )
