import pytest
from httpx import AsyncClient


@pytest.fixture
async def ctx(client: AsyncClient) -> dict:
    """Full setup: register, org, project, shared element."""
    await client.post(
        "/api/auth/register",
        json={"email": "admin@test.com", "password": "password123", "full_name": "Admin"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": "admin@test.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    org = await client.post(
        "/api/organizations/setup", json={"name": "Co"}, headers=headers
    )
    org_id = org.json()["organization_id"]
    headers["X-Organization-Id"] = str(org_id)

    proj = await client.post(
        "/api/projects", json={"name": "Report 2025"}, headers=headers
    )
    proj_id = proj.json()["id"]

    el = await client.post(
        "/api/shared-elements",
        json={"code": "GHG_S1", "name": "Scope 1"},
        headers=headers,
    )

    return {
        "headers": headers,
        "project_id": proj_id,
        "element_id": el.json()["id"],
        "org_id": org_id,
    }


@pytest.mark.asyncio
async def test_create_data_point(client: AsyncClient, ctx: dict):
    resp = await client.post(
        f"/api/projects/{ctx['project_id']}/data-points",
        json={
            "shared_element_id": ctx["element_id"],
            "numeric_value": 1240.5,
            "unit_code": "tCO2e",
        },
        headers=ctx["headers"],
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "draft"
    assert data["numeric_value"] == 1240.5
    assert data["unit_code"] == "tCO2e"


@pytest.mark.asyncio
async def test_create_data_point_with_dimensions(client: AsyncClient, ctx: dict):
    resp = await client.post(
        f"/api/projects/{ctx['project_id']}/data-points",
        json={
            "shared_element_id": ctx["element_id"],
            "numeric_value": 100,
            "dimensions": [
                {"dimension_type": "scope", "dimension_value": "Scope 1"},
                {"dimension_type": "gas", "dimension_value": "CO2"},
            ],
        },
        headers=ctx["headers"],
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_list_data_points(client: AsyncClient, ctx: dict):
    for i in range(3):
        await client.post(
            f"/api/projects/{ctx['project_id']}/data-points",
            json={"shared_element_id": ctx["element_id"], "numeric_value": i * 10},
            headers=ctx["headers"],
        )

    resp = await client.get(f"/api/projects/{ctx['project_id']}/data-points", headers=ctx["headers"])
    assert resp.status_code == 200
    assert resp.json()["total"] == 3


@pytest.mark.asyncio
async def test_get_data_point(client: AsyncClient, ctx: dict):
    create = await client.post(
        f"/api/projects/{ctx['project_id']}/data-points",
        json={"shared_element_id": ctx["element_id"], "numeric_value": 42},
        headers=ctx["headers"],
    )
    dp_id = create.json()["id"]

    resp = await client.get(f"/api/data-points/{dp_id}", headers=ctx["headers"])
    assert resp.status_code == 200
    assert resp.json()["numeric_value"] == 42


# --- Evidence ---
@pytest.mark.asyncio
async def test_create_evidence_file(client: AsyncClient, ctx: dict):
    resp = await client.post(
        "/api/evidences",
        json={
            "type": "file",
            "title": "Emissions Report",
            "file_name": "report.pdf",
            "file_uri": "s3://bucket/report.pdf",
            "mime_type": "application/pdf",
            "file_size": 2400000,
        },
        headers=ctx["headers"],
    )
    assert resp.status_code == 201
    assert resp.json()["type"] == "file"
    assert resp.json()["title"] == "Emissions Report"


@pytest.mark.asyncio
async def test_create_evidence_link(client: AsyncClient, ctx: dict):
    resp = await client.post(
        "/api/evidences",
        json={
            "type": "link",
            "title": "Company Policy",
            "url": "https://company.com/policy",
            "label": "ESG Policy Page",
        },
        headers=ctx["headers"],
    )
    assert resp.status_code == 201
    assert resp.json()["type"] == "link"


@pytest.mark.asyncio
async def test_list_evidences(client: AsyncClient, ctx: dict):
    await client.post(
        "/api/evidences",
        json={"type": "file", "title": "Doc 1", "file_name": "a.pdf", "file_uri": "s3://a"},
        headers=ctx["headers"],
    )
    await client.post(
        "/api/evidences",
        json={"type": "link", "title": "Link 1", "url": "https://x.com"},
        headers=ctx["headers"],
    )

    resp = await client.get("/api/evidences", headers=ctx["headers"])
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


@pytest.mark.asyncio
async def test_link_evidence_to_data_point(client: AsyncClient, ctx: dict):
    # Create data point
    dp = await client.post(
        f"/api/projects/{ctx['project_id']}/data-points",
        json={"shared_element_id": ctx["element_id"], "numeric_value": 100},
        headers=ctx["headers"],
    )
    # Create evidence
    ev = await client.post(
        "/api/evidences",
        json={"type": "file", "title": "Proof", "file_name": "p.pdf", "file_uri": "s3://p"},
        headers=ctx["headers"],
    )
    # Link
    resp = await client.post(
        f"/api/data-points/{dp.json()['id']}/evidences",
        json={"evidence_id": ev.json()["id"]},
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["linked"] is True
