import csv
import json
from datetime import datetime
from io import StringIO

from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.db.models.audit_log import AuditLog
from app.repositories.audit_repo import AuditRepository
from app.schemas.audit import AuditLogExportOut, AuditLogListOut, AuditLogOut


class AuditService:
    def __init__(self, repo: AuditRepository):
        self.repo = repo

    @staticmethod
    def _require_audit_reader(ctx: RequestContext) -> None:
        if ctx.role not in ("platform_admin", "admin", "esg_manager", "auditor"):
            raise AppError("FORBIDDEN", 403, "You do not have permission to access audit log")

    @staticmethod
    def _resolve_org_scope(ctx: RequestContext, organization_id: int | None) -> int | None:
        if ctx.is_platform_admin:
            return organization_id
        if not ctx.organization_id:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required")
        if organization_id is not None and organization_id != ctx.organization_id:
            raise AppError("FORBIDDEN", 403, "You can only view audit logs for your organization")
        return ctx.organization_id

    @staticmethod
    def _serialize(entry: AuditLog) -> AuditLogOut:
        return AuditLogOut(
            id=entry.id,
            organization_id=entry.organization_id,
            user_id=entry.user_id,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            action=entry.action,
            changes=entry.changes,
            request_id=entry.request_id,
            performed_by_platform_admin=entry.performed_by_platform_admin,
            created_at=entry.created_at,
        )

    async def list_logs(
        self,
        *,
        ctx: RequestContext,
        organization_id: int | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        action: str | None = None,
        user_id: int | None = None,
        request_id: str | None = None,
        performed_by_platform_admin: bool | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> AuditLogListOut:
        self._require_audit_reader(ctx)
        scoped_org_id = self._resolve_org_scope(ctx, organization_id)
        items, total = await self.repo.list_logs(
            organization_id=scoped_org_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            user_id=user_id,
            request_id=request_id,
            performed_by_platform_admin=performed_by_platform_admin,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        )
        return AuditLogListOut(items=[self._serialize(item) for item in items], total=total)

    async def export_logs(
        self,
        *,
        export_format: str,
        ctx: RequestContext,
        organization_id: int | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        action: str | None = None,
        user_id: int | None = None,
        request_id: str | None = None,
        performed_by_platform_admin: bool | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> AuditLogExportOut:
        self._require_audit_reader(ctx)
        scoped_org_id = self._resolve_org_scope(ctx, organization_id)
        entries = await self.repo.export_logs(
            organization_id=scoped_org_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            user_id=user_id,
            request_id=request_id,
            performed_by_platform_admin=performed_by_platform_admin,
            date_from=date_from,
            date_to=date_to,
        )
        serialized = [self._serialize(entry).model_dump(mode="json") for entry in entries]
        filename_scope = f"org-{scoped_org_id}" if scoped_org_id is not None else "platform"
        if export_format == "json":
            return AuditLogExportOut(
                format="json",
                content_type="application/json",
                filename=f"audit-log-{filename_scope}.json",
                content={"items": serialized, "total": len(serialized)},
                total=len(serialized),
            )

        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "id",
                "organization_id",
                "user_id",
                "entity_type",
                "entity_id",
                "action",
                "request_id",
                "performed_by_platform_admin",
                "created_at",
                "changes",
            ]
        )
        for item in serialized:
            writer.writerow(
                [
                    item["id"],
                    item["organization_id"] or "",
                    item["user_id"] or "",
                    item["entity_type"],
                    item["entity_id"] or "",
                    item["action"],
                    item["request_id"] or "",
                    str(item["performed_by_platform_admin"]).lower(),
                    item["created_at"] or "",
                    json.dumps(item["changes"], sort_keys=True) if item["changes"] is not None else "",
                ]
            )
        return AuditLogExportOut(
            format="csv",
            content_type="text/csv",
            filename=f"audit-log-{filename_scope}.csv",
            content=buffer.getvalue(),
            total=len(serialized),
        )
