import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models.audit_log import AuditLog
from app.db.models.boundary import BoundaryDefinition
from app.db.models.boundary_snapshot import BoundarySnapshot
from app.db.models.completeness import RequirementItemStatus
from app.db.models.data_point import DataPoint
from app.db.models.requirement_item import RequirementItem
from app.db.models.shared_element import SharedElement
from app.db.models.standard import DisclosureRequirement, Standard
from app.db.models.project import ReportingProject
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
    assert result == {"checked": 1, "processed": 1, "completed": 1, "failed": 0}

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
    assert run.json() == {"checked": 1, "processed": 1, "completed": 1, "failed": 0}

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
