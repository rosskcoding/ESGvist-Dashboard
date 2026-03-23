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
    return {"Authorization": f"Bearer {resp.json()['access_token']}", "X-Organization-Id": "1"}


@pytest.mark.asyncio
async def test_create_shared_element(client: AsyncClient, admin_headers: dict):
    resp = await client.post(
        "/api/shared-elements",
        json={
            "code": "GHG_SCOPE_1_TOTAL",
            "name": "Total Scope 1 GHG Emissions",
            "concept_domain": "emissions",
            "default_value_type": "number",
            "default_unit_code": "tCO2e",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["code"] == "GHG_SCOPE_1_TOTAL"
    assert data["concept_domain"] == "emissions"


@pytest.mark.asyncio
async def test_duplicate_code_returns_409(client: AsyncClient, admin_headers: dict):
    await client.post(
        "/api/shared-elements",
        json={"code": "DUP", "name": "Dup 1"},
        headers=admin_headers,
    )
    resp = await client.post(
        "/api/shared-elements",
        json={"code": "DUP", "name": "Dup 2"},
        headers=admin_headers,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_dimension(client: AsyncClient, admin_headers: dict):
    el = await client.post(
        "/api/shared-elements",
        json={"code": "GHG_S1", "name": "Scope 1"},
        headers=admin_headers,
    )
    el_id = el.json()["id"]

    resp = await client.post(
        f"/api/shared-elements/{el_id}/dimensions",
        json={"dimension_type": "scope", "is_required": True},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["dimension_type"] == "scope"
    assert resp.json()["is_required"] is True


@pytest.mark.asyncio
async def test_list_dimensions(client: AsyncClient, admin_headers: dict):
    el = await client.post(
        "/api/shared-elements",
        json={"code": "GHG_S1", "name": "Scope 1"},
        headers=admin_headers,
    )
    el_id = el.json()["id"]

    await client.post(
        f"/api/shared-elements/{el_id}/dimensions",
        json={"dimension_type": "scope", "is_required": True},
        headers=admin_headers,
    )
    await client.post(
        f"/api/shared-elements/{el_id}/dimensions",
        json={"dimension_type": "gas", "is_required": False},
        headers=admin_headers,
    )

    resp = await client.get(f"/api/shared-elements/{el_id}/dimensions")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_list_elements(client: AsyncClient, admin_headers: dict):
    for i in range(3):
        await client.post(
            "/api/shared-elements",
            json={"code": f"EL_{i}", "name": f"Element {i}"},
            headers=admin_headers,
        )

    resp = await client.get("/api/shared-elements")
    assert resp.status_code == 200
    assert resp.json()["total"] == 3


@pytest.mark.asyncio
async def test_get_element_with_dimensions(client: AsyncClient, admin_headers: dict):
    el = await client.post(
        "/api/shared-elements",
        json={"code": "FULL", "name": "Full Element"},
        headers=admin_headers,
    )
    el_id = el.json()["id"]

    await client.post(
        f"/api/shared-elements/{el_id}/dimensions",
        json={"dimension_type": "scope", "is_required": True},
        headers=admin_headers,
    )

    resp = await client.get(f"/api/shared-elements/{el_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["dimensions"]) == 1
    assert data["dimensions"][0]["dimension_type"] == "scope"
