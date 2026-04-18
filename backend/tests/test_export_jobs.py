import base64
import io
import zipfile
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.metrics import NON_BLOCKING_FAILURES
from app.domain.catalog import prepare_shared_element_defaults
from app.db.models.audit_log import AuditLog
from app.db.models.boundary import BoundaryDefinition
from app.db.models.boundary_snapshot import BoundarySnapshot
from app.db.models.completeness import RequirementItemStatus
from app.db.models.data_point import DataPoint
from app.db.models.export_job import ExportJob
from app.db.models.idempotency_record import IdempotencyRecord
from app.db.models.mapping import RequirementItemSharedElement
from app.db.models.project import ReportingProject
from app.db.models.requirement_item import RequirementItem
from app.db.models.shared_element import SharedElement
from app.db.models.standard import DisclosureRequirement, Standard
from app.repositories.idempotency_repo import IdempotencyRepository
from app.schemas.export import ExportJobCreate
from app.services.export_service import ExportService
from app.workers.job_runner import JobRunner
from tests.conftest import TestSessionLocal


async def _register_and_login(client: AsyncClient, *, email: str, full_name: str) -> dict:
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123", "full_name": full_name},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "password123"},
    )
    return {
        "token": login.json()["access_token"],
        "headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
    }


async def _setup_project(client: AsyncClient, *, email: str, org_name: str, project_name: str) -> dict:
    admin = await _register_and_login(client, email=email, full_name="Export Admin")
    me = await client.get("/api/auth/me", headers=admin["headers"])
    org = await client.post(
        "/api/organizations/setup",
        json={"name": org_name, "country": "GB"},
        headers=admin["headers"],
    )
    tenant_headers = dict(admin["headers"])
    tenant_headers["X-Organization-Id"] = str(org.json()["organization_id"])
    project = await client.post(
        "/api/projects",
        json={"name": project_name, "reporting_year": 2025},
        headers=tenant_headers,
    )
    assert project.status_code == 201
    await _make_project_export_ready(
        organization_id=org.json()["organization_id"],
        project_id=project.json()["id"],
        user_id=me.json()["id"],
    )
    return {
        "platform_headers": admin["headers"],
        "tenant_headers": tenant_headers,
        "org_id": org.json()["organization_id"],
        "project_id": project.json()["id"],
        "user_id": me.json()["id"],
    }


async def _make_project_export_ready(*, organization_id: int, project_id: int, user_id: int) -> None:
    async with TestSessionLocal() as session:
        project = await session.get(ReportingProject, project_id)

        boundary = BoundaryDefinition(
            organization_id=organization_id,
            name=f"Export Boundary {project_id}",
            boundary_type="operational_control",
            is_default=False,
        )
        session.add(boundary)
        await session.flush()
        project.boundary_definition_id = boundary.id

        shared_element = SharedElement(
            code=f"EXPORT-SE-{project_id}",
            name=f"Export Shared Element {project_id}",
            **prepare_shared_element_defaults(code=f"EXPORT-SE-{project_id}"),
        )
        session.add(shared_element)
        await session.flush()

        standard = Standard(code=f"EXPORT-STD-{project_id}", name=f"Export Standard {project_id}")
        session.add(standard)
        await session.flush()

        disclosure = DisclosureRequirement(
            standard_id=standard.id,
            code=f"DISC-{project_id}",
            title=f"Disclosure {project_id}",
            requirement_type="quantitative",
            mandatory_level="mandatory",
        )
        session.add(disclosure)
        await session.flush()

        item = RequirementItem(
            disclosure_requirement_id=disclosure.id,
            item_code=f"ITEM-{project_id}",
            name=f"Item {project_id}",
            item_type="metric",
            value_type="number",
            is_required=True,
        )
        session.add(item)
        await session.flush()

        session.add(
            RequirementItemSharedElement(
                requirement_item_id=item.id,
                shared_element_id=shared_element.id,
                mapping_type="full",
            )
        )
        await session.flush()

        data_point = DataPoint(
            reporting_project_id=project_id,
            shared_element_id=shared_element.id,
            status="approved",
            numeric_value=1,
            created_by=user_id,
        )
        session.add(data_point)
        await session.flush()

        session.add(
            RequirementItemStatus(
                reporting_project_id=project_id,
                requirement_item_id=item.id,
                status="complete",
            )
        )
        session.add(
            BoundarySnapshot(
                reporting_project_id=project_id,
                boundary_definition_id=boundary.id,
                snapshot_data={"locked": True},
                created_by=user_id,
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_job_runner_processes_json_export_jobs(client: AsyncClient):
    ctx = await _setup_project(
        client,
        email="export-runner@test.com",
        org_name="Export Runner Org",
        project_name="Runner Export Project",
    )

    queued = await client.post(
        f"/api/projects/{ctx['project_id']}/exports",
        json={"export_format": "json", "report_type": "project_report"},
        headers=ctx["tenant_headers"],
    )
    assert queued.status_code == 201
    assert queued.json()["status"] == "queued"

    listed = await client.get(
        f"/api/projects/{ctx['project_id']}/exports",
        headers=ctx["tenant_headers"],
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["status"] == "queued"

    result = await JobRunner(session_factory=TestSessionLocal).run_export_jobs()
    assert result == {
        "checked": 1,
        "processed": 1,
        "completed": 1,
        "failed": 0,
        "retried": 0,
        "dead_letter": 0,
    }

    job_id = queued.json()["id"]
    job = await client.get(f"/api/exports/{job_id}", headers=ctx["tenant_headers"])
    assert job.status_code == 200
    assert job.json()["status"] == "completed"
    assert job.json()["content_type"] == "application/json"

    artifact = await client.get(f"/api/exports/{job_id}/artifact", headers=ctx["tenant_headers"])
    assert artifact.status_code == 200
    data = artifact.json()
    assert data["export_format"] == "json"
    assert data["content_type"] == "application/json"
    assert data["artifact_name"].endswith(".json")
    assert data["content"]["project"]["id"] == ctx["project_id"]
    assert "readiness" in data["content"]
    assert data["checksum"]


@pytest.mark.asyncio
async def test_platform_job_endpoint_processes_csv_export_jobs_and_audits(client: AsyncClient):
    ctx = await _setup_project(
        client,
        email="export-platform@test.com",
        org_name="Export Platform Org",
        project_name="Platform Export Project",
    )

    queued = await client.post(
        f"/api/projects/{ctx['project_id']}/exports",
        json={"export_format": "csv", "report_type": "readiness_snapshot"},
        headers=ctx["tenant_headers"],
    )
    assert queued.status_code == 201

    run = await client.post("/api/platform/jobs/exports", headers=ctx["platform_headers"])
    assert run.status_code == 200
    assert run.json() == {
        "checked": 1,
        "processed": 1,
        "completed": 1,
        "failed": 0,
        "retried": 0,
        "dead_letter": 0,
    }

    artifact = await client.get(
        f"/api/exports/{queued.json()['id']}/artifact",
        headers=ctx["tenant_headers"],
    )
    assert artifact.status_code == 200
    payload = artifact.json()
    assert payload["export_format"] == "csv"
    assert payload["content_type"] == "text/csv"
    assert payload["artifact_name"].endswith(".csv")
    assert "field,value" in payload["content"]
    assert "completion_percent" in payload["content"]

    async with TestSessionLocal() as session:
        logs = (await session.execute(select(AuditLog).order_by(AuditLog.id))).scalars().all()
    assert any(log.action == "platform_export_jobs_triggered" and log.performed_by_platform_admin for log in logs)
    assert any(log.action == "export_job_completed" for log in logs)


@pytest.mark.asyncio
async def test_export_artifact_returns_conflict_while_job_is_still_queued(client: AsyncClient):
    ctx = await _setup_project(
        client,
        email="export-pending@test.com",
        org_name="Export Pending Org",
        project_name="Pending Export Project",
    )

    queued = await client.post(
        f"/api/projects/{ctx['project_id']}/exports",
        json={"export_format": "json", "report_type": "project_report"},
        headers=ctx["tenant_headers"],
    )
    assert queued.status_code == 201

    artifact = await client.get(
        f"/api/exports/{queued.json()['id']}/artifact",
        headers=ctx["tenant_headers"],
    )
    assert artifact.status_code == 409
    assert artifact.json()["error"]["code"] == "EXPORT_ARTIFACT_NOT_READY"


@pytest.mark.asyncio
async def test_duplicate_export_is_blocked_while_job_is_active(client: AsyncClient):
    ctx = await _setup_project(
        client,
        email="export-duplicate@test.com",
        org_name="Export Duplicate Org",
        project_name="Duplicate Export Project",
    )

    first = await client.post(
        f"/api/projects/{ctx['project_id']}/exports",
        json={"export_format": "json", "report_type": "project_report"},
        headers=ctx["tenant_headers"],
    )
    assert first.status_code == 201

    second = await client.post(
        f"/api/projects/{ctx['project_id']}/exports",
        json={"export_format": "csv", "report_type": "readiness_snapshot"},
        headers=ctx["tenant_headers"],
    )
    assert second.status_code == 422
    assert second.json()["error"]["code"] == "EXPORT_IN_PROGRESS"


@pytest.mark.asyncio
async def test_export_queue_replays_same_job_with_idempotency_key(client: AsyncClient):
    ctx = await _setup_project(
        client,
        email="export-idempotent@test.com",
        org_name="Export Idempotent Org",
        project_name="Idempotent Export Project",
    )
    headers = {**ctx["tenant_headers"], "X-Idempotency-Key": "export-key-1"}

    first = await client.post(
        f"/api/projects/{ctx['project_id']}/exports",
        json={"export_format": "json", "report_type": "project_report"},
        headers=headers,
    )
    assert first.status_code == 201

    replay = await client.post(
        f"/api/projects/{ctx['project_id']}/exports",
        json={"export_format": "json", "report_type": "project_report"},
        headers=headers,
    )
    assert replay.status_code == 201
    assert replay.json()["id"] == first.json()["id"]
    assert replay.json()["status"] == "queued"

    conflict = await client.post(
        f"/api/projects/{ctx['project_id']}/exports",
        json={"export_format": "csv", "report_type": "readiness_snapshot"},
        headers=headers,
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


@pytest.mark.asyncio
async def test_export_queue_uses_atomic_idempotency_reserve_and_finalize(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    ctx = await _setup_project(
        client,
        email="export-idempotent-atomic@test.com",
        org_name="Export Idempotent Atomic Org",
        project_name="Atomic Export Project",
    )
    headers = {**ctx["tenant_headers"], "X-Idempotency-Key": "export-atomic-key"}
    calls: list[str] = []

    original_try_reserve = IdempotencyRepository.try_reserve
    original_finalize = IdempotencyRepository.finalize_record

    async def spy_try_reserve(self, **kwargs):
        calls.append("try_reserve")
        return await original_try_reserve(self, **kwargs)

    async def spy_finalize(self, record, *, status_code: int, response_body: dict):
        calls.append(f"finalize:{status_code}")
        return await original_finalize(
            self,
            record,
            status_code=status_code,
            response_body=response_body,
        )

    async def fail_create_record(self, **kwargs):
        raise AssertionError("create_record should not be used for export idempotency")

    monkeypatch.setattr(IdempotencyRepository, "try_reserve", spy_try_reserve)
    monkeypatch.setattr(IdempotencyRepository, "finalize_record", spy_finalize)
    monkeypatch.setattr(IdempotencyRepository, "create_record", fail_create_record)

    queued = await client.post(
        f"/api/projects/{ctx['project_id']}/exports",
        json={"export_format": "json", "report_type": "project_report"},
        headers=headers,
    )

    assert queued.status_code == 201
    assert queued.json()["status"] == "queued"
    assert calls == ["try_reserve", "finalize:201"]


@pytest.mark.asyncio
async def test_export_queue_rejects_pending_idempotency_record(client: AsyncClient):
    ctx = await _setup_project(
        client,
        email="export-idempotent-pending@test.com",
        org_name="Export Idempotent Pending Org",
        project_name="Pending Idempotent Export Project",
    )
    payload = ExportJobCreate(export_format="json", report_type="project_report")
    idempotency_key = "export-pending-key"

    async with TestSessionLocal() as session:
        session.add(
            IdempotencyRecord(
                organization_id=ctx["org_id"],
                user_id=ctx["user_id"],
                method="POST",
                path=f"/api/projects/{ctx['project_id']}/exports",
                idempotency_key=idempotency_key,
                request_fingerprint=ExportService._request_fingerprint(ctx["project_id"], payload),
                response_status_code=0,
                response_body={},
            )
        )
        await session.commit()

    blocked = await client.post(
        f"/api/projects/{ctx['project_id']}/exports",
        json=payload.model_dump(mode="json"),
        headers={**ctx["tenant_headers"], "X-Idempotency-Key": idempotency_key},
    )

    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "IDEMPOTENCY_REQUEST_PENDING"


@pytest.mark.asyncio
async def test_gate_check_supports_start_export_and_reports_active_export(client: AsyncClient):
    ctx = await _setup_project(
        client,
        email="export-gate@test.com",
        org_name="Export Gate Org",
        project_name="Gate Export Project",
    )

    allowed = await client.post(
        "/api/gate-check",
        json={"action": "start_export", "project_id": ctx["project_id"]},
        headers=ctx["tenant_headers"],
    )
    assert allowed.status_code == 200
    assert allowed.json()["allowed"] is True

    queued = await client.post(
        f"/api/projects/{ctx['project_id']}/exports",
        json={"export_format": "json", "report_type": "project_report"},
        headers=ctx["tenant_headers"],
    )
    assert queued.status_code == 201

    blocked = await client.post(
        "/api/gate-check",
        json={"action": "start_export", "project_id": ctx["project_id"]},
        headers=ctx["tenant_headers"],
    )
    assert blocked.status_code == 200
    assert blocked.json()["allowed"] is False
    assert any(gate["code"] == "EXPORT_IN_PROGRESS" for gate in blocked.json()["failedGates"])


@pytest.mark.asyncio
async def test_gri_index_pdf_export_returns_base64_pdf_artifact(client: AsyncClient):
    ctx = await _setup_project(
        client,
        email="export-gri@test.com",
        org_name="Export GRI Org",
        project_name="GRI Export Project",
    )

    queued = await client.post(
        f"/api/projects/{ctx['project_id']}/export/gri-index?export_format=pdf",
        headers=ctx["tenant_headers"],
    )
    assert queued.status_code == 201
    assert queued.json()["report_type"] == "gri_content_index"
    assert queued.json()["export_format"] == "pdf"

    run = await client.post("/api/platform/jobs/exports", headers=ctx["platform_headers"])
    assert run.status_code == 200

    artifact = await client.get(
        f"/api/exports/{queued.json()['id']}/artifact",
        headers=ctx["tenant_headers"],
    )
    assert artifact.status_code == 200
    payload = artifact.json()
    assert payload["content_type"] == "application/pdf"
    assert payload["artifact_encoding"] == "base64"
    assert payload["artifact_name"].endswith(".pdf")
    pdf_bytes = base64.b64decode(payload["content"])
    assert pdf_bytes.startswith(b"%PDF-")
    assert b"GRI Content Index" in pdf_bytes


@pytest.mark.asyncio
async def test_project_report_xlsx_export_returns_valid_workbook(client: AsyncClient):
    ctx = await _setup_project(
        client,
        email="export-xlsx@test.com",
        org_name="Export XLSX Org",
        project_name="Workbook Export Project",
    )

    queued = await client.post(
        f"/api/projects/{ctx['project_id']}/export/report?export_format=xlsx",
        headers=ctx["tenant_headers"],
    )
    assert queued.status_code == 201
    assert queued.json()["export_format"] == "xlsx"

    run = await client.post("/api/platform/jobs/exports", headers=ctx["platform_headers"])
    assert run.status_code == 200

    artifact = await client.get(
        f"/api/exports/{queued.json()['id']}/artifact",
        headers=ctx["tenant_headers"],
    )
    assert artifact.status_code == 200
    payload = artifact.json()
    assert payload["content_type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert payload["artifact_encoding"] == "base64"
    workbook_bytes = base64.b64decode(payload["content"])
    with zipfile.ZipFile(io.BytesIO(workbook_bytes), "r") as archive:
        names = set(archive.namelist())
        assert "[Content_Types].xml" in names
        assert "xl/workbook.xml" in names
        sheet_xml = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "Workbook Export Project" in sheet_xml
    assert "completion_percent" in sheet_xml


@pytest.mark.asyncio
async def test_xbrl_export_generates_xml_instance(client: AsyncClient):
    ctx = await _setup_project(
        client,
        email="export-xbrl@test.com",
        org_name="Export XBRL Org",
        project_name="XBRL Export Project",
    )

    queued = await client.post(
        f"/api/projects/{ctx['project_id']}/export/xbrl",
        headers=ctx["tenant_headers"],
    )
    assert queued.status_code == 201
    assert queued.json()["report_type"] == "xbrl_instance"
    assert queued.json()["export_format"] == "xml"

    run = await client.post("/api/platform/jobs/exports", headers=ctx["platform_headers"])
    assert run.status_code == 200

    artifact = await client.get(
        f"/api/exports/{queued.json()['id']}/artifact",
        headers=ctx["tenant_headers"],
    )
    assert artifact.status_code == 200
    payload = artifact.json()
    assert payload["content_type"] == "application/xml"
    assert payload["artifact_encoding"] == "utf-8"
    assert payload["artifact_name"].endswith(".xml")
    assert "<xbrli:xbrl" in payload["content"]
    assert "EXPORT_SE" in payload["content"] or "EXPORT_SE_" in payload["content"]


@pytest.mark.asyncio
async def test_export_job_failure_schedules_retry_and_then_completes(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    ctx = await _setup_project(
        client,
        email="export-retry@test.com",
        org_name="Export Retry Org",
        project_name="Retry Export Project",
    )

    queued = await client.post(
        f"/api/projects/{ctx['project_id']}/exports",
        json={"export_format": "json", "report_type": "project_report"},
        headers=ctx["tenant_headers"],
    )
    assert queued.status_code == 201
    job_id = queued.json()["id"]

    original = ExportService._build_export_payload
    state = {"calls": 0}

    async def flaky_payload(self, project_id: int, report_type: str):
        state["calls"] += 1
        if state["calls"] == 1:
            raise RuntimeError("temporary export failure")
        return await original(self, project_id, report_type)

    monkeypatch.setattr(ExportService, "_build_export_payload", flaky_payload)

    first = await JobRunner(session_factory=TestSessionLocal).run_export_jobs()
    assert first["retried"] == 1
    assert first["dead_letter"] == 0

    job = await client.get(f"/api/exports/{job_id}", headers=ctx["tenant_headers"])
    assert job.status_code == 200
    assert job.json()["status"] == "retry_scheduled"
    assert job.json()["attempt"] == 1
    assert job.json()["next_retry_at"] is not None

    notifications = await client.get("/api/notifications", headers=ctx["tenant_headers"])
    assert notifications.status_code == 200
    assert any(item["type"] == "export_retry_scheduled" for item in notifications.json()["items"])

    async with TestSessionLocal() as session:
        db_job = await session.get(ExportJob, job_id)
        db_job.next_retry_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await session.commit()

    second = await JobRunner(session_factory=TestSessionLocal).run_export_jobs()
    assert second["completed"] == 1
    assert second["retried"] == 0

    completed = await client.get(f"/api/exports/{job_id}", headers=ctx["tenant_headers"])
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["attempt"] == 2


@pytest.mark.asyncio
async def test_export_job_dead_letter_notifies_requester(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    ctx = await _setup_project(
        client,
        email="export-dead-letter@test.com",
        org_name="Export Dead Letter Org",
        project_name="Dead Letter Export Project",
    )

    queued = await client.post(
        f"/api/projects/{ctx['project_id']}/exports",
        json={"export_format": "json", "report_type": "project_report"},
        headers=ctx["tenant_headers"],
    )
    assert queued.status_code == 201
    job_id = queued.json()["id"]

    async with TestSessionLocal() as session:
        db_job = await session.get(ExportJob, job_id)
        db_job.max_attempts = 1
        await session.commit()

    async def always_fail(self, project_id: int, report_type: str):
        raise RuntimeError("permanent export failure")

    monkeypatch.setattr(ExportService, "_build_export_payload", always_fail)

    result = await JobRunner(session_factory=TestSessionLocal).run_export_jobs()
    assert result["dead_letter"] == 1

    job = await client.get(f"/api/exports/{job_id}", headers=ctx["tenant_headers"])
    assert job.status_code == 200
    assert job.json()["status"] == "dead_letter"
    assert job.json()["attempt"] == 1
    assert job.json()["error_message"] == "permanent export failure"

    notifications = await client.get("/api/notifications", headers=ctx["tenant_headers"])
    assert notifications.status_code == 200
    assert any(item["type"] == "export_dead_letter" for item in notifications.json()["items"])


@pytest.mark.asyncio
async def test_export_job_failure_logs_and_counts_classified_reason(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import export_service as export_module

    class _FakeLogger:
        def __init__(self):
            self.calls: list[tuple[str, str, dict]] = []

        def warning(self, event: str, **kwargs):
            self.calls.append(("warning", event, kwargs))

    fake_logger = _FakeLogger()
    before = NON_BLOCKING_FAILURES.labels(
        component="export_service",
        operation="artifact_generation_failed",
    )._value.get()
    monkeypatch.setattr(export_module, "logger", fake_logger)

    ctx = await _setup_project(
        client,
        email="export-observability@test.com",
        org_name="Export Observability Org",
        project_name="Observability Export Project",
    )

    queued = await client.post(
        f"/api/projects/{ctx['project_id']}/exports",
        json={"export_format": "json", "report_type": "project_report"},
        headers=ctx["tenant_headers"],
    )
    assert queued.status_code == 201

    async def invalid_payload(self, project_id: int, report_type: str):
        raise ValueError("invalid export payload")

    monkeypatch.setattr(ExportService, "_build_export_payload", invalid_payload)

    result = await JobRunner(session_factory=TestSessionLocal).run_export_jobs()

    after = NON_BLOCKING_FAILURES.labels(
        component="export_service",
        operation="artifact_generation_failed",
    )._value.get()
    assert result["retried"] == 1
    assert result["failed"] == 1
    assert after == before + 1
    assert fake_logger.calls[0][1] == "export_job_processing_failed"
    assert fake_logger.calls[0][2]["failure_reason"] == "ValueError"
    assert fake_logger.calls[0][2]["next_status"] == "retry_scheduled"
