from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.repositories.audit_repo import AuditRepository
from app.repositories.evidence_repo import EvidenceRepository
from app.schemas.evidence import EvidenceCreate, EvidenceListOut, EvidenceOut


class EvidenceService:
    def __init__(self, repo: EvidenceRepository, audit_repo: AuditRepository | None = None):
        self.repo = repo
        self.audit_repo = audit_repo

    async def _audit(self, action: str, entity_id: int, ctx: RequestContext, changes: dict | None = None):
        if self.audit_repo:
            await self.audit_repo.log(
                entity_type="Evidence",
                entity_id=entity_id,
                action=action,
                user_id=ctx.user_id,
                organization_id=ctx.organization_id,
                changes=changes,
            )

    async def create(self, payload: EvidenceCreate, ctx: RequestContext) -> EvidenceOut:
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
        return EvidenceOut.model_validate(ev)

    async def list_evidences(
        self, ctx: RequestContext, page: int = 1, page_size: int = 50
    ) -> EvidenceListOut:
        if not ctx.organization_id:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required")
        items, total = await self.repo.list_by_org(ctx.organization_id, page, page_size)
        return EvidenceListOut(
            items=[EvidenceOut.model_validate(ev) for ev in items],
            total=total,
        )

    async def link_to_data_point(
        self, dp_id: int, evidence_id: int, ctx: RequestContext
    ) -> dict:
        await self.repo.get_or_raise(evidence_id)
        await self.repo.link_to_data_point(dp_id, evidence_id, ctx.user_id)
        await self._audit("evidence_linked", evidence_id, ctx, {"data_point_id": dp_id})
        return {"data_point_id": dp_id, "evidence_id": evidence_id, "linked": True}
