import base64
import csv
import hashlib
import json
import zipfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import BytesIO, StringIO
from xml.sax.saxutils import escape

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import get_project_for_ctx
from app.core.dependencies import RequestContext
from app.core.exceptions import AppError, GateBlockedError
from app.core.metrics import record_non_blocking_failure
from app.db.models.boundary import BoundaryDefinition, BoundaryMembership
from app.db.models.boundary_snapshot import BoundarySnapshot
from app.db.models.company_entity import CompanyEntity
from app.db.models.completeness import RequirementItemStatus
from app.db.models.data_point import DataPoint
from app.db.models.export_job import ExportJob
from app.db.models.mapping import RequirementItemSharedElement
from app.db.models.project import ReportingProject
from app.db.models.requirement_item import RequirementItem
from app.db.models.shared_element import SharedElement
from app.db.models.standard import DisclosureRequirement, Standard
from app.repositories.audit_repo import AuditRepository
from app.repositories.export_repo import ExportRepository
from app.repositories.idempotency_repo import IdempotencyRepository
from app.repositories.notification_repo import NotificationRepository
from app.schemas.export import ExportArtifactOut, ExportJobCreate, ExportJobListOut, ExportJobOut
from app.services.notification_service import NotificationService
from app.workflows.gates.base import GateEngine
from app.workflows.gates.boundary_gate import BoundaryNotLockedGate
from app.workflows.gates.completeness_gate import ProjectIncompleteGate
from app.workflows.gates.review_gate import ReviewNotCompletedGate
from app.workflows.gates.workflow_gate import ExportInProgressGate

EXPORT_RETRY_DELAYS_SECONDS = [1, 2, 4]
logger = structlog.get_logger("app.exports")


class ExportService:
    def __init__(
        self,
        session: AsyncSession,
        repo: ExportRepository | None = None,
        audit_repo: AuditRepository | None = None,
        idempotency_repo: IdempotencyRepository | None = None,
    ):
        self.session = session
        self.repo = repo or ExportRepository(session)
        self.audit_repo = audit_repo
        self.idempotency_repo = idempotency_repo or IdempotencyRepository(session)
        self.notification_service = NotificationService(NotificationRepository(session))
        self.export_gate_engine = GateEngine(
            [
                ReviewNotCompletedGate(),
                ProjectIncompleteGate(),
                BoundaryNotLockedGate(),
                ExportInProgressGate(),
            ]
        )

    @staticmethod
    def _require_export_admin(ctx: RequestContext) -> None:
        if ctx.role not in ("admin", "esg_manager", "platform_admin"):
            raise AppError("FORBIDDEN", 403, "Only admin or ESG manager can queue export jobs")

    @staticmethod
    def _require_export_reader(ctx: RequestContext) -> None:
        if ctx.role not in ("admin", "esg_manager", "platform_admin", "auditor"):
            raise AppError("FORBIDDEN", 403, "You don't have permission to access export jobs")

    @staticmethod
    def _classify_job_failure(exc: Exception) -> tuple[str, str]:
        if isinstance(exc, GateBlockedError):
            return "job_gate_blocked", getattr(exc, "code", "GATE_BLOCKED")
        if isinstance(exc, AppError):
            return "job_app_error", getattr(exc, "code", "APP_ERROR")
        if isinstance(exc, (ValueError, TypeError, UnicodeError, zipfile.BadZipFile)):
            return "artifact_generation_failed", type(exc).__name__
        return "job_unexpected_error", type(exc).__name__

    @staticmethod
    def _serialize_job(job: ExportJob) -> ExportJobOut:
        return ExportJobOut(
            id=job.id,
            organization_id=job.organization_id,
            reporting_project_id=job.reporting_project_id,
            requested_by_user_id=job.requested_by_user_id,
            report_type=job.report_type,
            export_format=job.export_format,
            status=job.status,
            content_type=job.content_type,
            artifact_name=job.artifact_name,
            artifact_encoding=job.artifact_encoding,
            artifact_size_bytes=job.artifact_size_bytes,
            checksum=job.checksum,
            error_message=job.error_message,
            attempt=job.attempt,
            max_attempts=job.max_attempts,
            next_retry_at=job.next_retry_at,
            created_at=job.created_at,
            updated_at=job.updated_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
        )

    @staticmethod
    def _format_scalar(value: object | None) -> str:
        if value is None:
            return ""
        if isinstance(value, Decimal):
            return format(value.normalize(), "f") if value == value.to_integral() else format(value, "f")
        return str(value)

    @staticmethod
    def _escape_pdf_text(value: str) -> str:
        return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    @staticmethod
    def _xml_name(value: str) -> str:
        sanitized = "".join(ch if ch.isalnum() else "_" for ch in value.strip())
        if not sanitized:
            return "fact"
        if sanitized[0].isdigit():
            sanitized = f"fact_{sanitized}"
        return sanitized

    @staticmethod
    def _xlsx_column_name(index: int) -> str:
        name = ""
        value = index
        while value:
            value, remainder = divmod(value - 1, 26)
            name = chr(65 + remainder) + name
        return name or "A"

    @staticmethod
    def _build_pdf_artifact(title: str, lines: list[str]) -> bytes:
        page_lines = [title, ""] + lines
        text_lines = [
            f"({ExportService._escape_pdf_text(line)}) Tj" if idx == 0 else f"T* ({ExportService._escape_pdf_text(line)}) Tj"
            for idx, line in enumerate(page_lines)
        ]
        contents = "BT /F1 11 Tf 50 780 Td 14 TL " + " ".join(text_lines) + " ET"
        objects = [
            "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
            "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
            "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj",
            "4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
            f"5 0 obj << /Length {len(contents.encode('utf-8'))} >> stream\n{contents}\nendstream endobj",
        ]
        pdf = "%PDF-1.4\n"
        offsets = [0]
        for obj in objects:
            offsets.append(len(pdf.encode("utf-8")))
            pdf += obj + "\n"
        xref_offset = len(pdf.encode("utf-8"))
        pdf += f"xref\n0 {len(objects) + 1}\n"
        pdf += "0000000000 65535 f \n"
        for offset in offsets[1:]:
            pdf += f"{offset:010d} 00000 n \n"
        pdf += f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF"
        return pdf.encode("utf-8")

    @staticmethod
    def _build_xlsx_artifact(sheet_name: str, rows: list[list[object]]) -> bytes:
        def cell_xml(row_idx: int, col_idx: int, value: object) -> str:
            ref = f"{ExportService._xlsx_column_name(col_idx)}{row_idx}"
            if value is None:
                return f'<c r="{ref}" t="inlineStr"><is><t></t></is></c>'
            if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
                return f'<c r="{ref}"><v>{value}</v></c>'
            return f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'

        sheet_rows = []
        for row_idx, row in enumerate(rows, start=1):
            cells = "".join(cell_xml(row_idx, col_idx, value) for col_idx, value in enumerate(row, start=1))
            sheet_rows.append(f'<row r="{row_idx}">{cells}</row>')
        worksheet = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetData>{"".join(sheet_rows)}</sheetData>'
            "</worksheet>"
        )
        workbook = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<sheets><sheet name="{escape(sheet_name[:31] or "Sheet1")}" sheetId="1" r:id="rId1"/></sheets>'
            "</workbook>"
        )
        content_types = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/styles.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            "</Types>"
        )
        root_rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/>'
            "</Relationships>"
        )
        workbook_rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
            'Target="styles.xml"/>'
            "</Relationships>"
        )
        styles = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
            '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
            '<borders count="1"><border/></borders>'
            '<cellStyleXfs count="1"><xf/></cellStyleXfs>'
            '<cellXfs count="1"><xf xfId="0"/></cellXfs>'
            '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
            "</styleSheet>"
        )

        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", content_types)
            archive.writestr("_rels/.rels", root_rels)
            archive.writestr("xl/workbook.xml", workbook)
            archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
            archive.writestr("xl/worksheets/sheet1.xml", worksheet)
            archive.writestr("xl/styles.xml", styles)
        return buffer.getvalue()

    @staticmethod
    def _text_artifact(body: str, content_type: str) -> tuple[str, str, str, int, str]:
        payload = body.encode("utf-8")
        return body, content_type, "utf-8", len(payload), hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _json_artifact(body: dict) -> tuple[str, str, str, int, str]:
        serialized = json.dumps(body, indent=2, sort_keys=True)
        payload = serialized.encode("utf-8")
        return serialized, "application/json", "json", len(payload), hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _binary_artifact(body: bytes, content_type: str) -> tuple[str, str, str, int, str]:
        return (
            base64.b64encode(body).decode("ascii"),
            content_type,
            "base64",
            len(body),
            hashlib.sha256(body).hexdigest(),
        )

    @staticmethod
    def _request_fingerprint(project_id: int, payload: ExportJobCreate) -> str:
        serialized = json.dumps(
            {
                "project_id": project_id,
                "payload": payload.model_dump(mode="json"),
            },
            sort_keys=True,
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    async def _audit(
        self,
        *,
        action: str,
        job: ExportJob | None = None,
        ctx: RequestContext | None = None,
        changes: dict | None = None,
    ) -> None:
        if not self.audit_repo:
            return
        await self.audit_repo.log(
            entity_type="ExportJob",
            entity_id=job.id if job else None,
            action=action,
            user_id=ctx.user_id if ctx else (job.requested_by_user_id if job else None),
            organization_id=job.organization_id if job else (ctx.organization_id if ctx else None),
            changes=changes,
            performed_by_platform_admin=bool(ctx and ctx.is_platform_admin),
        )

    async def _get_job_for_ctx(self, job_id: int, ctx: RequestContext) -> ExportJob:
        self._require_export_reader(ctx)
        job = await self.repo.get_job_or_raise(job_id)
        await get_project_for_ctx(
            self.session,
            job.reporting_project_id,
            ctx,
            allow_collectors=False,
            allow_reviewers=False,
        )
        return job

    async def _build_export_gate_context(
        self,
        project_id: int,
        ctx: RequestContext,
        completion_threshold: int = 100,
    ) -> dict:
        project = await get_project_for_ctx(
            self.session,
            project_id,
            ctx,
            allow_collectors=False,
            allow_reviewers=False,
        )
        total_data_point_count = (
            await self.session.execute(
                select(func.count()).select_from(DataPoint).where(
                    DataPoint.reporting_project_id == project_id
                )
            )
        ).scalar_one()
        reviewed_count = (
            await self.session.execute(
                select(func.count()).select_from(DataPoint).where(
                    DataPoint.reporting_project_id == project_id,
                    DataPoint.status.in_(("approved", "rejected", "needs_revision")),
                )
            )
        ).scalar_one()
        status_rows = (
            await self.session.execute(
                select(RequirementItemStatus.status, func.count())
                .where(RequirementItemStatus.reporting_project_id == project_id)
                .group_by(RequirementItemStatus.status)
            )
        ).all()
        status_counts = {status: count for status, count in status_rows}
        total_item_statuses = sum(status_counts.values())
        complete_items = status_counts.get("complete", 0)
        snapshot = (
            await self.session.execute(
                select(BoundarySnapshot).where(BoundarySnapshot.reporting_project_id == project_id)
            )
        ).scalar_one_or_none()
        completion_percent = (
            (complete_items / total_item_statuses) * 100 if total_item_statuses else 0
        )
        return {
            "project": project,
            "reviewed_count": reviewed_count,
            "total_data_point_count": total_data_point_count,
            "completion_percent": round(completion_percent, 1),
            "completion_threshold": completion_threshold,
            "boundary_snapshot_locked": (
                snapshot is not None
                and snapshot.boundary_definition_id == project.boundary_definition_id
            ),
            "active_export_count": await self.repo.count_active_jobs(project_id),
        }

    async def gate_check_start_export(self, project_id: int, ctx: RequestContext) -> dict:
        self._require_export_reader(ctx)
        context = await self._build_export_gate_context(project_id, ctx)
        result = await self.export_gate_engine.check("start_export", context)
        gate_log = {
            "action": "start_export",
            "allowed": result.allowed,
            "failed_codes": [gate.code for gate in result.failed_gates],
            "warning_codes": [gate.code for gate in result.warnings],
        }
        if self.audit_repo:
            await self.audit_repo.log(
                entity_type="ReportingProject",
                entity_id=project_id,
                action="gate_check",
                user_id=ctx.user_id,
                organization_id=ctx.organization_id,
                changes=gate_log,
                performed_by_platform_admin=ctx.is_platform_admin,
            )
        return {
            "allowed": result.allowed,
            "failedGates": [
                {"code": gate.code, "type": gate.gate_type, "message": gate.message, "severity": gate.severity}
                for gate in result.failed_gates
            ],
            "warnings": [
                {"code": gate.code, "type": gate.gate_type, "message": gate.message}
                for gate in result.warnings
            ],
        }

    @staticmethod
    def _project_report_rows(payload: dict) -> list[list[object]]:
        boundary = payload.get("boundary") or {}
        rows: list[list[object]] = [
            ["field", "value"],
            ["project_id", payload["project"]["id"]],
            ["project_name", payload["project"]["name"]],
            ["project_status", payload["project"]["status"]],
            ["reporting_year", payload["project"]["reporting_year"] or ""],
            ["completion_percent", payload["readiness"]["completion_percent"]],
            ["ready", str(payload["readiness"]["ready"]).lower()],
            ["total_items", payload["readiness"]["total_items"]],
            ["complete_items", payload["readiness"]["complete"]],
            ["partial_items", payload["readiness"]["partial"]],
            ["missing_items", payload["readiness"]["missing"]],
            ["blocking_issues", payload["readiness"]["blocking_issues"]],
            ["warnings", payload["readiness"]["warnings"]],
            ["boundary_type", boundary.get("boundary_type") or ""],
            ["entities_in_scope", boundary.get("entities_in_scope", 0)],
        ]
        for index, point in enumerate(payload.get("data_points", [])[:25], start=1):
            rows.append(
                [
                    f"data_point_{index}",
                    f"{point['shared_element_code']}={point['value']} {point.get('unit_code') or ''}".strip(),
                ]
            )
        return rows

    @staticmethod
    def _gri_index_rows(payload: dict) -> list[list[object]]:
        rows: list[list[object]] = [[
            "standard_code",
            "standard_name",
            "disclosure_code",
            "disclosure_title",
            "item_code",
            "item_name",
            "status",
            "shared_element_code",
            "shared_element_name",
            "requires_evidence",
        ]]
        for item in payload.get("index_rows", []):
            rows.append(
                [
                    item["standard_code"],
                    item["standard_name"],
                    item["disclosure_code"],
                    item["disclosure_title"],
                    item["item_code"],
                    item["item_name"],
                    item["status"],
                    item["shared_element_code"],
                    item["shared_element_name"],
                    "true" if item["requires_evidence"] else "false",
                ]
            )
        return rows

    @staticmethod
    def _build_csv_artifact(rows: list[list[object]]) -> str:
        buffer = StringIO()
        writer = csv.writer(buffer)
        for row in rows:
            writer.writerow([ExportService._format_scalar(value) for value in row])
        return buffer.getvalue()

    async def _collect_disclosure_rows(self, project_id: int) -> list[dict]:
        result = await self.session.execute(
            select(
                Standard.code,
                Standard.name,
                DisclosureRequirement.code,
                DisclosureRequirement.title,
                RequirementItem.item_code,
                RequirementItem.name,
                RequirementItem.requires_evidence,
                RequirementItem.unit_code,
                RequirementItemStatus.status,
                SharedElement.code,
                SharedElement.name,
            )
            .select_from(RequirementItemStatus)
            .join(RequirementItem, RequirementItem.id == RequirementItemStatus.requirement_item_id)
            .join(
                DisclosureRequirement,
                DisclosureRequirement.id == RequirementItem.disclosure_requirement_id,
            )
            .join(Standard, Standard.id == DisclosureRequirement.standard_id)
            .outerjoin(
                RequirementItemSharedElement,
                RequirementItemSharedElement.requirement_item_id == RequirementItem.id,
            )
            .outerjoin(SharedElement, SharedElement.id == RequirementItemSharedElement.shared_element_id)
            .where(RequirementItemStatus.reporting_project_id == project_id)
            .order_by(Standard.code, DisclosureRequirement.code, RequirementItem.sort_order, RequirementItem.id)
        )
        rows = []
        for standard_code, standard_name, disclosure_code, disclosure_title, item_code, item_name, requires_evidence, unit_code, status, shared_element_code, shared_element_name in result.all():
            rows.append(
                {
                    "standard_code": standard_code,
                    "standard_name": standard_name,
                    "disclosure_code": disclosure_code,
                    "disclosure_title": disclosure_title,
                    "item_code": item_code or "",
                    "item_name": item_name,
                    "requires_evidence": bool(requires_evidence),
                    "unit_code": unit_code or "",
                    "status": status,
                    "shared_element_code": shared_element_code or "",
                    "shared_element_name": shared_element_name or "",
                }
            )
        return rows

    async def _collect_data_points(self, project_id: int) -> list[dict]:
        result = await self.session.execute(
            select(
                DataPoint.id,
                DataPoint.status,
                DataPoint.numeric_value,
                DataPoint.text_value,
                DataPoint.unit_code,
                DataPoint.entity_id,
                DataPoint.facility_id,
                SharedElement.code,
                SharedElement.name,
            )
            .join(SharedElement, SharedElement.id == DataPoint.shared_element_id)
            .where(
                DataPoint.reporting_project_id == project_id,
                DataPoint.status == "approved",
            )
            .order_by(DataPoint.id)
        )
        rows = []
        for data_point_id, status, numeric_value, text_value, unit_code, entity_id, facility_id, shared_element_code, shared_element_name in result.all():
            rows.append(
                {
                    "id": data_point_id,
                    "status": status,
                    "value": self._format_scalar(numeric_value if numeric_value is not None else text_value),
                    "unit_code": unit_code or "",
                    "entity_id": entity_id,
                    "facility_id": facility_id,
                    "shared_element_code": shared_element_code,
                    "shared_element_name": shared_element_name,
                }
            )
        return rows

    async def _build_export_payload(self, project_id: int, report_type: str) -> dict:
        export_data = await self.export_data(project_id)
        readiness = await self.readiness_check(project_id)
        payload = {
            "project": {
                "id": export_data["project_id"],
                "name": export_data["project_name"],
                "status": export_data["status"],
                "reporting_year": export_data["reporting_year"],
            },
            "boundary": export_data["boundary"],
            "readiness": readiness,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        if report_type in {"project_report", "gri_content_index"}:
            payload["index_rows"] = await self._collect_disclosure_rows(project_id)
        if report_type in {"project_report", "xbrl_instance"}:
            payload["data_points"] = await self._collect_data_points(project_id)
        return payload

    @staticmethod
    def _validate_export_request(payload: ExportJobCreate) -> None:
        allowed_formats = {
            "project_report": {"json", "csv", "pdf", "xlsx"},
            "readiness_snapshot": {"json", "csv"},
            "gri_content_index": {"csv", "pdf", "xlsx"},
            "xbrl_instance": {"xml"},
        }
        if payload.export_format not in allowed_formats[payload.report_type]:
            raise AppError(
                "INVALID_EXPORT_FORMAT",
                422,
                f"Format '{payload.export_format}' is not supported for report type '{payload.report_type}'",
            )

    async def queue_export_job(
        self,
        project_id: int,
        payload: ExportJobCreate,
        ctx: RequestContext,
        idempotency_key: str | None = None,
    ) -> ExportJobOut:
        self._require_export_admin(ctx)
        if not ctx.organization_id:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required")
        self._validate_export_request(payload)

        path = f"/api/projects/{project_id}/exports"
        request_fingerprint = self._request_fingerprint(project_id, payload)
        reserved_record = None
        if idempotency_key:
            existing_record = await self.idempotency_repo.try_reserve(
                organization_id=ctx.organization_id,
                user_id=ctx.user_id,
                method="POST",
                path=path,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
            )
            if existing_record:
                if existing_record.request_fingerprint != request_fingerprint:
                    raise AppError(
                        "IDEMPOTENCY_KEY_REUSED",
                        409,
                        "Idempotency key was already used with a different request payload",
                    )
                if existing_record.response_status_code == 0 or not existing_record.response_body:
                    raise AppError(
                        "IDEMPOTENCY_REQUEST_PENDING",
                        409,
                        "A request with this idempotency key is still being processed",
                    )
                return ExportJobOut(**existing_record.response_body)

            reserved_record = await self.idempotency_repo.get_record(
                organization_id=ctx.organization_id,
                user_id=ctx.user_id,
                method="POST",
                path=path,
                idempotency_key=idempotency_key,
            )
            if reserved_record is None:
                raise AppError(
                    "IDEMPOTENCY_RESERVATION_FAILED",
                    500,
                    "Failed to finalize idempotency reservation",
                )

        context = await self._build_export_gate_context(project_id, ctx)
        gate_result = await self.gate_check_start_export(project_id, ctx)
        if not gate_result["allowed"]:
            primary = gate_result["failedGates"][0]
            raise GateBlockedError(
                code=primary["code"],
                message=primary["message"],
                failed_gates=gate_result["failedGates"],
                warnings=gate_result["warnings"],
            )

        project = context["project"]
        job = await self.repo.create_job(
            organization_id=project.organization_id,
            reporting_project_id=project.id,
            requested_by_user_id=ctx.user_id,
            report_type=payload.report_type,
            export_format=payload.export_format,
            status="queued",
            attempt=0,
            max_attempts=len(EXPORT_RETRY_DELAYS_SECONDS),
            next_retry_at=None,
        )
        await self._audit(
            action="export_job_queued",
            job=job,
            ctx=ctx,
            changes={"export_format": payload.export_format, "report_type": payload.report_type},
        )
        serialized = self._serialize_job(job)
        if reserved_record is not None:
            await self.idempotency_repo.finalize_record(
                reserved_record,
                status_code=201,
                response_body=serialized.model_dump(mode="json"),
            )
        return serialized

    async def list_export_jobs(
        self,
        project_id: int,
        ctx: RequestContext,
        page: int = 1,
        page_size: int = 20,
    ) -> ExportJobListOut:
        self._require_export_reader(ctx)
        project = await get_project_for_ctx(
            self.session,
            project_id,
            ctx,
            allow_collectors=False,
            allow_reviewers=False,
        )
        jobs, total = await self.repo.list_project_jobs(project.organization_id, project.id, page, page_size)
        return ExportJobListOut(items=[self._serialize_job(job) for job in jobs], total=total)

    async def get_export_job(self, job_id: int, ctx: RequestContext) -> ExportJobOut:
        job = await self._get_job_for_ctx(job_id, ctx)
        return self._serialize_job(job)

    async def get_export_artifact(self, job_id: int, ctx: RequestContext) -> ExportArtifactOut:
        job = await self._get_job_for_ctx(job_id, ctx)
        if (
            job.status != "completed"
            or not job.artifact_body
            or not job.content_type
            or not job.artifact_name
            or not job.artifact_encoding
        ):
            raise AppError("EXPORT_ARTIFACT_NOT_READY", 409, "Export artifact is not ready yet")
        if job.artifact_encoding == "json":
            content: dict | str = json.loads(job.artifact_body)
        else:
            content = job.artifact_body
        return ExportArtifactOut(
            job_id=job.id,
            export_format=job.export_format,
            content_type=job.content_type,
            artifact_encoding=job.artifact_encoding,
            artifact_name=job.artifact_name,
            content=content,
            checksum=job.checksum,
        )

    @staticmethod
    def _build_xbrl_artifact(payload: dict) -> str:
        project = payload["project"]
        unit_ids: dict[str, str] = {}
        unit_xml: list[str] = []
        facts: list[str] = []
        for point in payload.get("data_points", []):
            concept = ExportService._xml_name(point["shared_element_code"] or f"datapoint_{point['id']}")
            if point["unit_code"]:
                unit_id = unit_ids.setdefault(
                    point["unit_code"],
                    f"u{len(unit_ids) + 1}",
                )
                if len(unit_xml) < len(unit_ids):
                    unit_xml.append(
                        f'<xbrli:unit id="{unit_id}"><xbrli:measure>esgvu:{escape(point["unit_code"])}</xbrli:measure></xbrli:unit>'
                    )
                facts.append(
                    f'<esgv:{concept} contextRef="c1" unitRef="{unit_id}">{escape(point["value"])}</esgv:{concept}>'
                )
            else:
                facts.append(
                    f'<esgv:{concept} contextRef="c1">{escape(point["value"])}</esgv:{concept}>'
                )
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" '
            'xmlns:xlink="http://www.w3.org/1999/xlink" '
            'xmlns:esgv="https://esgvist.local/xbrl" '
            'xmlns:esgvu="https://esgvist.local/xbrl/units">'
            '<xbrli:context id="c1">'
            '<xbrli:entity><xbrli:identifier scheme="https://esgvist.local/project">'
            f'{project["id"]}'
            '</xbrli:identifier></xbrli:entity>'
            '<xbrli:period>'
            f'<xbrli:instant>{project["reporting_year"] or datetime.now(timezone.utc).year}-12-31</xbrli:instant>'
            '</xbrli:period>'
            '</xbrli:context>'
            f'{"".join(unit_xml)}'
            f'{"".join(facts)}'
            '</xbrli:xbrl>'
        )

    @staticmethod
    def _build_pdf_lines(payload: dict, report_type: str) -> list[str]:
        lines = [
            f'Project: {payload["project"]["name"]}',
            f'Status: {payload["project"]["status"]}',
            f'Reporting year: {payload["project"]["reporting_year"] or ""}',
            f'Completion: {payload["readiness"]["completion_percent"]}%',
            f'Boundary: {(payload.get("boundary") or {}).get("boundary_type") or "n/a"}',
        ]
        if report_type == "gri_content_index":
            lines.append("GRI Content Index")
            for row in payload.get("index_rows", [])[:25]:
                lines.append(
                    f'{row["disclosure_code"]} | {row["item_code"] or row["item_name"]} | {row["status"]}'
                )
        else:
            lines.append("Approved Data Points")
            for point in payload.get("data_points", [])[:25]:
                lines.append(
                    f'{point["shared_element_code"]}: {point["value"]} {point.get("unit_code") or ""}'.strip()
                )
        return lines

    @staticmethod
    def _build_xlsx_rows(payload: dict, report_type: str) -> tuple[str, list[list[object]]]:
        if report_type == "gri_content_index":
            return "GRI Index", ExportService._gri_index_rows(payload)
        return "Project Report", ExportService._project_report_rows(payload)

    @staticmethod
    def _artifact_extension(job: ExportJob) -> str:
        if job.report_type == "xbrl_instance":
            return "xml"
        return job.export_format

    async def _notify_export_job(self, job: ExportJob, *, type: str, title: str, message: str) -> None:
        if not job.requested_by_user_id:
            return
        await self.notification_service.notify(
            user_id=job.requested_by_user_id,
            org_id=job.organization_id,
            type=type,
            title=title,
            message=message,
            entity_type="ExportJob",
            entity_id=job.id,
            severity="critical" if type == "export_dead_letter" else "warning",
        )

    async def process_queued_jobs(self, limit: int = 25) -> dict:
        jobs = await self.repo.list_due_jobs(limit=limit)
        result = {
            "checked": len(jobs),
            "processed": 0,
            "completed": 0,
            "failed": 0,
            "retried": 0,
            "dead_letter": 0,
        }

        for job in jobs:
            result["processed"] += 1
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            job.attempt += 1
            job.next_retry_at = None
            job.error_message = None
            await self.session.flush()
            try:
                payload = await self._build_export_payload(job.reporting_project_id, job.report_type)
                if job.report_type == "readiness_snapshot":
                    payload = {
                        "project": payload["project"],
                        "readiness": payload["readiness"],
                        "generated_at": payload["generated_at"],
                    }

                if job.export_format == "json":
                    artifact_body, content_type, artifact_encoding, size_bytes, checksum = self._json_artifact(payload)
                elif job.export_format == "csv":
                    rows = (
                        self._gri_index_rows(payload)
                        if job.report_type == "gri_content_index"
                        else self._project_report_rows(payload)
                    )
                    artifact_body, content_type, artifact_encoding, size_bytes, checksum = self._text_artifact(
                        self._build_csv_artifact(rows),
                        "text/csv",
                    )
                elif job.export_format == "pdf":
                    title = "GRI Content Index" if job.report_type == "gri_content_index" else "ESG Project Report"
                    artifact_body, content_type, artifact_encoding, size_bytes, checksum = self._binary_artifact(
                        self._build_pdf_artifact(title, self._build_pdf_lines(payload, job.report_type)),
                        "application/pdf",
                    )
                elif job.export_format == "xlsx":
                    sheet_name, rows = self._build_xlsx_rows(payload, job.report_type)
                    artifact_body, content_type, artifact_encoding, size_bytes, checksum = self._binary_artifact(
                        self._build_xlsx_artifact(sheet_name, rows),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                else:
                    artifact_body, content_type, artifact_encoding, size_bytes, checksum = self._text_artifact(
                        self._build_xbrl_artifact(payload),
                        "application/xml",
                    )

                job.status = "completed"
                job.completed_at = datetime.now(timezone.utc)
                job.content_type = content_type
                job.artifact_encoding = artifact_encoding
                job.artifact_body = artifact_body
                job.artifact_size_bytes = size_bytes
                job.checksum = checksum
                job.artifact_name = (
                    f"project-{job.reporting_project_id}-export-{job.id}.{self._artifact_extension(job)}"
                )
                await self.session.flush()
                await self._audit(
                    action="export_job_completed",
                    job=job,
                    changes={
                        "artifact_name": job.artifact_name,
                        "export_format": job.export_format,
                        "report_type": job.report_type,
                    },
                )
                result["completed"] += 1
            except Exception as exc:
                failure_operation, failure_reason = self._classify_job_failure(exc)
                record_non_blocking_failure("export_service", failure_operation)
                job.error_message = str(exc)
                next_status = (
                    "retry_scheduled"
                    if job.attempt < job.max_attempts
                    else "dead_letter"
                )
                logger.warning(
                    "export_job_processing_failed",
                    export_job_id=job.id,
                    organization_id=job.organization_id,
                    reporting_project_id=job.reporting_project_id,
                    export_format=job.export_format,
                    report_type=job.report_type,
                    attempt=job.attempt,
                    max_attempts=job.max_attempts,
                    next_status=next_status,
                    failure_reason=failure_reason,
                    exception_type=type(exc).__name__,
                    exc_info=True,
                )
                if job.attempt < job.max_attempts:
                    delay_seconds = EXPORT_RETRY_DELAYS_SECONDS[job.attempt - 1]
                    job.status = "retry_scheduled"
                    job.completed_at = None
                    job.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
                    await self.session.flush()
                    await self._audit(
                        action="export_job_retry_scheduled",
                        job=job,
                        changes={
                            "error_message": job.error_message,
                            "attempt": job.attempt,
                            "max_attempts": job.max_attempts,
                            "next_retry_at": job.next_retry_at.isoformat() if job.next_retry_at else None,
                        },
                    )
                    await self._notify_export_job(
                        job,
                        type="export_retry_scheduled",
                        title="Export retry scheduled",
                        message=(
                            f"Export job #{job.id} failed on attempt {job.attempt} and will retry automatically."
                        ),
                    )
                    result["retried"] += 1
                    result["failed"] += 1
                else:
                    job.status = "dead_letter"
                    job.completed_at = datetime.now(timezone.utc)
                    job.next_retry_at = None
                    await self.session.flush()
                    await self._audit(
                        action="export_job_dead_letter",
                        job=job,
                        changes={
                            "error_message": job.error_message,
                            "attempt": job.attempt,
                            "max_attempts": job.max_attempts,
                        },
                    )
                    await self._notify_export_job(
                        job,
                        type="export_dead_letter",
                        title="Export failed permanently",
                        message=(
                            f"Export job #{job.id} failed after {job.attempt} attempts and requires attention."
                        ),
                    )
                    result["dead_letter"] += 1
                    result["failed"] += 1
        return result

    async def _get_boundary_metadata(self, project: ReportingProject) -> dict:
        """Gather boundary metadata for a project."""
        boundary_type = None
        snapshot_id = None
        snapshot_date = None
        entities_in_scope = 0
        manual_overrides = 0

        if project.boundary_definition_id:
            # Get boundary definition
            bd_result = await self.session.execute(
                select(BoundaryDefinition).where(
                    BoundaryDefinition.id == project.boundary_definition_id
                )
            )
            boundary_def = bd_result.scalar_one_or_none()
            if boundary_def:
                boundary_type = boundary_def.boundary_type

            # Count entities in scope
            entity_count_q = select(func.count()).select_from(BoundaryMembership).where(
                BoundaryMembership.boundary_definition_id == project.boundary_definition_id,
                BoundaryMembership.included == True,
            )
            entities_in_scope = (await self.session.execute(entity_count_q)).scalar_one()

            # Count manual overrides
            override_count_q = select(func.count()).select_from(BoundaryMembership).where(
                BoundaryMembership.boundary_definition_id == project.boundary_definition_id,
                BoundaryMembership.inclusion_source == "manual",
            )
            manual_overrides = (await self.session.execute(override_count_q)).scalar_one()

        # Get snapshot info
        snap_result = await self.session.execute(
            select(BoundarySnapshot).where(
                BoundarySnapshot.reporting_project_id == project.id
            )
        )
        snapshot = snap_result.scalar_one_or_none()
        if snapshot:
            snapshot_id = snapshot.id
            snapshot_date = snapshot.created_at.isoformat() if snapshot.created_at else None

        return {
            "boundary_type": boundary_type,
            "snapshot_id": snapshot_id,
            "snapshot_date": snapshot_date,
            "entities_in_scope": entities_in_scope,
            "manual_overrides": manual_overrides,
        }

    async def _get_boundary_validation(self, project: ReportingProject) -> dict | None:
        if not project.boundary_definition_id:
            return None

        boundary_result = await self.session.execute(
            select(BoundaryDefinition).where(BoundaryDefinition.id == project.boundary_definition_id)
        )
        boundary = boundary_result.scalar_one_or_none()
        if not boundary:
            return None

        default_boundary_result = await self.session.execute(
            select(BoundaryDefinition.id).where(
                BoundaryDefinition.organization_id == project.organization_id,
                BoundaryDefinition.is_default == True,
            )
        )
        default_boundary_id = default_boundary_result.scalar_one_or_none()

        snapshot_result = await self.session.execute(
            select(BoundarySnapshot).where(BoundarySnapshot.reporting_project_id == project.id)
        )
        snapshot = snapshot_result.scalar_one_or_none()
        snapshot_locked = (
            snapshot is not None
            and snapshot.boundary_definition_id == project.boundary_definition_id
        )

        memberships = (
            await self.session.execute(
                select(BoundaryMembership).where(
                    BoundaryMembership.boundary_definition_id == project.boundary_definition_id,
                    BoundaryMembership.included == True,
                )
            )
        ).scalars().all()
        entity_ids = sorted({membership.entity_id for membership in memberships})
        entity_names = {}
        if entity_ids:
            entity_result = await self.session.execute(
                select(CompanyEntity).where(CompanyEntity.id.in_(entity_ids))
            )
            entity_names = {entity.id: entity.name for entity in entity_result.scalars().all()}

        data_points_result = await self.session.execute(
            select(DataPoint).where(DataPoint.reporting_project_id == project.id)
        )
        covered_entity_ids = set()
        for data_point in data_points_result.scalars().all():
            scope_entity_id = data_point.facility_id or data_point.entity_id
            if scope_entity_id in entity_ids:
                covered_entity_ids.add(scope_entity_id)

        entities_without_data = [
            entity_names[entity_id]
            for entity_id in entity_ids
            if entity_id not in covered_entity_ids and entity_id in entity_names
        ]

        return {
            "selected_boundary": boundary.name,
            "snapshot_locked": snapshot_locked,
            "entities_in_scope": len(entity_ids),
            "manual_overrides": sum(1 for membership in memberships if membership.inclusion_source == "manual"),
            "unresolved_structure_issues": 0,
            "boundary_differs_from_default": bool(
                default_boundary_id and default_boundary_id != project.boundary_definition_id
            ),
            "entities_without_data": entities_without_data,
        }

    async def readiness_check(self, project_id: int, ctx: RequestContext | None = None) -> dict:
        if ctx:
            if ctx.role not in ("admin", "esg_manager", "platform_admin", "auditor"):
                raise AppError("FORBIDDEN", 403, "You don't have permission to view export readiness")
            project = await get_project_for_ctx(
                self.session,
                project_id,
                ctx,
                allow_collectors=False,
                allow_reviewers=False,
            )
        else:
            proj = await self.session.execute(
                select(ReportingProject).where(ReportingProject.id == project_id)
            )
            project = proj.scalar_one_or_none()
            if not project:
                raise AppError("NOT_FOUND", 404, f"Project {project_id} not found")

        # Count item statuses
        statuses_q = select(RequirementItemStatus.status, func.count()).where(
            RequirementItemStatus.reporting_project_id == project_id
        ).group_by(RequirementItemStatus.status)
        result = await self.session.execute(statuses_q)
        status_counts = {row[0]: row[1] for row in result.all()}

        complete = status_counts.get("complete", 0)
        partial = status_counts.get("partial", 0)
        missing = status_counts.get("missing", 0)
        total = complete + partial + missing

        snapshot_result = await self.session.execute(
            select(BoundarySnapshot).where(BoundarySnapshot.reporting_project_id == project_id)
        )
        snapshot = snapshot_result.scalar_one_or_none()
        boundary_locked = (
            project.boundary_definition_id is not None
            and snapshot is not None
            and snapshot.boundary_definition_id == project.boundary_definition_id
        )

        blocking = missing + (0 if boundary_locked else 1)
        warnings = partial  # partial items are warnings

        overall_pct = (complete / total * 100) if total > 0 else 0

        # Boundary metadata
        boundary_meta = await self._get_boundary_metadata(project)
        boundary_validation = await self._get_boundary_validation(project)
        blocking_issue_details = []
        warning_details = []
        if missing:
            blocking_issue_details.append(
                {
                    "code": "MISSING_REQUIRED_ITEMS",
                    "message": f"{missing} required items are still missing",
                    "count": missing,
                }
            )
        if not boundary_locked:
            blocking_issue_details.append(
                {
                    "code": "BOUNDARY_SNAPSHOT_REQUIRED",
                    "message": "Boundary snapshot must be created and match the active boundary",
                    "count": 1,
                }
            )
        if partial:
            warning_details.append(
                {
                    "code": "PARTIAL_ITEMS",
                    "message": f"{partial} items are partially complete",
                    "count": partial,
                }
            )
        if boundary_validation and boundary_validation["entities_without_data"]:
            warning_details.append(
                {
                    "code": "BOUNDARY_ENTITIES_WITHOUT_DATA",
                    "message": "Some entities in boundary do not have project data yet",
                    "count": len(boundary_validation["entities_without_data"]),
                }
            )

        return {
            "project_id": project_id,
            "ready": blocking == 0,
            "overall_ready": blocking == 0,
            "completion_percent": round(overall_pct, 1),
            "total_items": total,
            "complete": complete,
            "partial": partial,
            "missing": missing,
            "blocking_issues": blocking,
            "warnings": warnings,
            "blocking_issue_details": blocking_issue_details,
            "warning_details": warning_details,
            "boundary_locked": boundary_locked,
            "boundary_validation": boundary_validation,
            **boundary_meta,
        }

    async def export_data(self, project_id: int, ctx: RequestContext | None = None) -> dict:
        """Export project data with boundary metadata."""
        if ctx:
            project = await get_project_for_ctx(
                self.session,
                project_id,
                ctx,
                allow_collectors=False,
                allow_reviewers=False,
            )
        else:
            proj = await self.session.execute(
                select(ReportingProject).where(ReportingProject.id == project_id)
            )
            project = proj.scalar_one_or_none()
            if not project:
                raise AppError("NOT_FOUND", 404, f"Project {project_id} not found")

        boundary_meta = await self._get_boundary_metadata(project)

        return {
            "project_id": project_id,
            "project_name": project.name,
            "status": project.status,
            "reporting_year": project.reporting_year,
            "boundary": boundary_meta,
        }

    async def publish(self, project_id: int, ctx: RequestContext) -> dict:
        """Publish a project.

        Delegates to ProjectService.publish_project() which runs full
        workflow gates, fires events, and invalidates caches.  This
        avoids having two independent publish paths with divergent
        invariants.
        """
        from app.services.project_service import ProjectService
        from app.repositories.project_repo import ProjectRepository

        project_service = ProjectService(
            repo=ProjectRepository(self.session),
            audit_repo=self.audit_repo,
        )
        return await project_service.publish_project(project_id, ctx)
