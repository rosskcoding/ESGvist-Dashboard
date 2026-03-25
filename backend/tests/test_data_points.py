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


async def _create_requirement_item(
    client: AsyncClient,
    *,
    headers: dict,
    project_id: int,
    attach_to_project: bool,
) -> int:
    standard = await client.post(
        "/api/standards",
        json={"code": "GRI", "name": "GRI"},
        headers=headers,
    )
    assert standard.status_code == 201

    disclosure = await client.post(
        f"/api/standards/{standard.json()['id']}/disclosures",
        json={
            "code": "305-1",
            "title": "Gross direct GHG emissions",
            "requirement_type": "quantitative",
            "mandatory_level": "mandatory",
        },
        headers=headers,
    )
    assert disclosure.status_code == 201

    item = await client.post(
        f"/api/disclosures/{disclosure.json()['id']}/items",
        json={
            "name": "Scope 1 total",
            "item_type": "metric",
            "value_type": "number",
            "unit_code": "tCO2e",
            "item_code": "305-1.a",
        },
        headers=headers,
    )
    assert item.status_code == 201

    if attach_to_project:
        linked = await client.post(
            f"/api/projects/{project_id}/standards",
            json={"standard_id": standard.json()["id"], "is_base_standard": True},
            headers=headers,
        )
        assert linked.status_code == 200

    return item.json()["id"]


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

    resp = await client.get(
        f"/api/projects/{ctx['project_id']}/data-points",
        headers=ctx["headers"],
    )
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
async def test_create_evidence_file_requires_non_empty_file_uri(client: AsyncClient, ctx: dict):
    resp = await client.post(
        "/api/evidences",
        json={
            "type": "file",
            "title": "Broken Upload",
            "file_name": "broken.pdf",
            "file_uri": "   ",
        },
        headers=ctx["headers"],
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_INPUT"
    assert "file_uri" in resp.json()["error"]["message"]


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
async def test_create_evidence_rejects_oversized_file_message_matches_limit(
    client: AsyncClient,
    ctx: dict,
):
    resp = await client.post(
        "/api/evidences",
        json={
            "type": "file",
            "title": "Too Large",
            "file_name": "large.pdf",
            "file_uri": "s3://bucket/large.pdf",
            "mime_type": "application/pdf",
            "file_size": 10 * 1024 * 1024 + 1,
        },
        headers=ctx["headers"],
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "FILE_TOO_LARGE"
    assert "10MB" in resp.json()["error"]["message"]
    assert "50MB" not in resp.json()["error"]["message"]


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


@pytest.mark.asyncio
async def test_bind_requirement_rejects_item_outside_active_reporting_context(
    client: AsyncClient,
    ctx: dict,
):
    evidence = await client.post(
        "/api/evidences",
        json={"type": "file", "title": "Proof", "file_name": "proof.pdf", "file_uri": "s3://proof"},
        headers=ctx["headers"],
    )
    assert evidence.status_code == 201

    requirement_item_id = await _create_requirement_item(
        client,
        headers=ctx["headers"],
        project_id=ctx["project_id"],
        attach_to_project=False,
    )

    resp = await client.post(
        f"/api/evidence/{evidence.json()['id']}/bind-requirement",
        json={"requirement_item_id": requirement_item_id},
        headers=ctx["headers"],
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_REQUIREMENT_ITEM_CONTEXT"


@pytest.mark.asyncio
async def test_bind_requirement_allows_item_active_in_org_project_context(
    client: AsyncClient,
    ctx: dict,
):
    evidence = await client.post(
        "/api/evidences",
        json={"type": "file", "title": "Proof", "file_name": "proof.pdf", "file_uri": "s3://proof"},
        headers=ctx["headers"],
    )
    assert evidence.status_code == 201

    requirement_item_id = await _create_requirement_item(
        client,
        headers=ctx["headers"],
        project_id=ctx["project_id"],
        attach_to_project=True,
    )

    resp = await client.post(
        f"/api/evidence/{evidence.json()['id']}/bind-requirement",
        json={"requirement_item_id": requirement_item_id},
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["linked"] is True
    assert resp.json()["requirement_item_id"] == requirement_item_id


@pytest.mark.asyncio
async def test_bind_requirement_rejects_item_active_only_in_other_project_context(
    client: AsyncClient,
    ctx: dict,
):
    second_project = await client.post(
        "/api/projects",
        json={"name": "Report 2026"},
        headers=ctx["headers"],
    )
    assert second_project.status_code == 201

    dp = await client.post(
        f"/api/projects/{ctx['project_id']}/data-points",
        json={"shared_element_id": ctx["element_id"], "numeric_value": 100},
        headers=ctx["headers"],
    )
    assert dp.status_code == 201

    evidence = await client.post(
        "/api/evidences",
        json={
            "type": "file",
            "title": "Proof",
            "file_name": "proof.pdf",
            "file_uri": "s3://proof",
        },
        headers=ctx["headers"],
    )
    assert evidence.status_code == 201

    linked = await client.post(
        f"/api/data-points/{dp.json()['id']}/evidences",
        json={"evidence_id": evidence.json()["id"]},
        headers=ctx["headers"],
    )
    assert linked.status_code == 200

    requirement_item_id = await _create_requirement_item(
        client,
        headers=ctx["headers"],
        project_id=second_project.json()["id"],
        attach_to_project=True,
    )

    resp = await client.post(
        f"/api/evidence/{evidence.json()['id']}/bind-requirement",
        json={"requirement_item_id": requirement_item_id},
        headers=ctx["headers"],
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_REQUIREMENT_ITEM_CONTEXT"
    assert "linked to this evidence" in resp.json()["error"]["message"]
