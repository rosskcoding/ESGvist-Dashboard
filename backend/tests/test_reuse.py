import pytest
from httpx import AsyncClient


@pytest.fixture
async def ctx(client: AsyncClient) -> dict:
    await client.post(
        "/api/auth/register",
        json={"email": "a@t.com", "password": "password123", "full_name": "A"},
    )
    login = await client.post("/api/auth/login", json={"email": "a@t.com", "password": "password123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    org = await client.post("/api/organizations/setup", json={"name": "Co"}, headers=headers)
    headers["X-Organization-Id"] = str(org.json()["organization_id"])

    el = await client.post("/api/shared-elements", json={"code": "S1", "name": "S1"}, headers=headers)
    proj = await client.post("/api/projects", json={"name": "R"}, headers=headers)

    std = await client.post("/api/standards", json={"code": "GRI", "name": "GRI"}, headers=headers)
    disc = await client.post(
        f"/api/standards/{std.json()['id']}/disclosures",
        json={"code": "305-1", "title": "E", "requirement_type": "quantitative", "mandatory_level": "mandatory"},
        headers=headers,
    )
    item = await client.post(
        f"/api/disclosures/{disc.json()['id']}/items",
        json={"name": "Scope1", "item_type": "metric", "value_type": "number"},
        headers=headers,
    )

    dp = await client.post(
        f"/api/projects/{proj.json()['id']}/data-points",
        json={"shared_element_id": el.json()["id"], "numeric_value": 500, "unit_code": "tCO2e"},
        headers=headers,
    )

    return {
        "headers": headers,
        "project_id": proj.json()["id"],
        "element_id": el.json()["id"],
        "item_id": item.json()["id"],
        "dp_id": dp.json()["id"],
    }


@pytest.mark.asyncio
async def test_find_reuse_candidates(client: AsyncClient, ctx: dict):
    resp = await client.get(
        f"/api/projects/{ctx['project_id']}/data-points/find-reuse?shared_element_id={ctx['element_id']}"
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["numeric_value"] == 500


@pytest.mark.asyncio
async def test_find_reuse_no_match(client: AsyncClient, ctx: dict):
    resp = await client.get(
        f"/api/projects/{ctx['project_id']}/data-points/find-reuse?shared_element_id=9999"
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 0


@pytest.mark.asyncio
async def test_reuse_info_single_binding(client: AsyncClient, ctx: dict):
    # Bind dp to item
    await client.post(
        f"/api/projects/{ctx['project_id']}/bindings",
        json={"requirement_item_id": ctx["item_id"], "data_point_id": ctx["dp_id"]},
    )

    resp = await client.get(f"/api/data-points/{ctx['dp_id']}/reuse-info")
    assert resp.status_code == 200
    assert resp.json()["binding_count"] == 1


@pytest.mark.asyncio
async def test_reuse_info_no_bindings(client: AsyncClient, ctx: dict):
    resp = await client.get(f"/api/data-points/{ctx['dp_id']}/reuse-info")
    assert resp.status_code == 200
    assert resp.json()["binding_count"] == 0
