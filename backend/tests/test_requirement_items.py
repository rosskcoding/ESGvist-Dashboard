import pytest
from httpx import AsyncClient


@pytest.fixture
async def admin_headers(client: AsyncClient) -> dict:
    await client.post(
        "/api/auth/register",
        json={"email": "admin@test.com", "password": "password123", "full_name": "Admin"},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"email": "admin@test.com", "password": "password123"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
async def disclosure_id(client: AsyncClient, admin_headers: dict) -> int:
    std = await client.post(
        "/api/standards",
        json={"code": "GRI", "name": "GRI"},
        headers=admin_headers,
    )
    sid = std.json()["id"]
    disc = await client.post(
        f"/api/standards/{sid}/disclosures",
        json={
            "code": "305-1",
            "title": "Emissions",
            "requirement_type": "quantitative",
            "mandatory_level": "mandatory",
        },
        headers=admin_headers,
    )
    return disc.json()["id"]


@pytest.mark.asyncio
async def test_create_requirement_item(
    client: AsyncClient, admin_headers: dict, disclosure_id: int
):
    resp = await client.post(
        f"/api/disclosures/{disclosure_id}/items",
        json={
            "name": "Scope 1 total",
            "item_type": "metric",
            "value_type": "number",
            "unit_code": "tCO2e",
            "item_code": "305-1.a",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Scope 1 total"
    assert data["item_type"] == "metric"
    assert data["value_type"] == "number"
    assert data["unit_code"] == "tCO2e"


@pytest.mark.asyncio
async def test_item_hierarchy(client: AsyncClient, admin_headers: dict, disclosure_id: int):
    parent = await client.post(
        f"/api/disclosures/{disclosure_id}/items",
        json={"name": "Parent", "item_type": "metric", "value_type": "number"},
        headers=admin_headers,
    )
    parent_id = parent.json()["id"]

    child = await client.post(
        f"/api/disclosures/{disclosure_id}/items",
        json={
            "name": "Child",
            "item_type": "dimension",
            "value_type": "text",
            "parent_item_id": parent_id,
        },
        headers=admin_headers,
    )
    assert child.status_code == 201
    assert child.json()["parent_item_id"] == parent_id


@pytest.mark.asyncio
async def test_json_rules(client: AsyncClient, admin_headers: dict, disclosure_id: int):
    resp = await client.post(
        f"/api/disclosures/{disclosure_id}/items",
        json={
            "name": "With rules",
            "item_type": "metric",
            "value_type": "number",
            "granularity_rule": {"by_scope": True},
            "validation_rule": {"min": 0, "deviation_threshold": 0.4},
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["granularity_rule"]["by_scope"] is True
    assert data["validation_rule"]["min"] == 0


@pytest.mark.asyncio
async def test_create_dependency(client: AsyncClient, admin_headers: dict, disclosure_id: int):
    item_a = await client.post(
        f"/api/disclosures/{disclosure_id}/items",
        json={"name": "A", "item_type": "metric", "value_type": "number"},
        headers=admin_headers,
    )
    item_b = await client.post(
        f"/api/disclosures/{disclosure_id}/items",
        json={"name": "B", "item_type": "metric", "value_type": "number"},
        headers=admin_headers,
    )

    resp = await client.post(
        f"/api/items/{item_a.json()['id']}/dependencies",
        json={"depends_on_item_id": item_b.json()["id"], "dependency_type": "requires"},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["dependency_type"] == "requires"


@pytest.mark.asyncio
async def test_list_items(client: AsyncClient, admin_headers: dict, disclosure_id: int):
    for i in range(3):
        await client.post(
            f"/api/disclosures/{disclosure_id}/items",
            json={"name": f"Item {i}", "item_type": "metric", "value_type": "number"},
            headers=admin_headers,
        )

    resp = await client.get(f"/api/disclosures/{disclosure_id}/items", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 3
