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


async def _create_item(client, admin_headers, std_code, disc_code, item_name):
    """Helper: create standard → disclosure → item, return item_id."""
    std_resp = await client.post(
        "/api/standards", json={"code": std_code, "name": std_code}, headers=admin_headers
    )
    if std_resp.status_code == 201:
        sid = std_resp.json()["id"]
    else:
        # Already exists — find it
        list_resp = await client.get("/api/standards", headers=admin_headers)
        sid = next(s["id"] for s in list_resp.json()["items"] if s["code"] == std_code)

    disc_resp = await client.post(
        f"/api/standards/{sid}/disclosures",
        json={
            "code": disc_code,
            "title": disc_code,
            "requirement_type": "quantitative",
            "mandatory_level": "mandatory",
        },
        headers=admin_headers,
    )
    did = disc_resp.json()["id"]

    item_resp = await client.post(
        f"/api/disclosures/{did}/items",
        json={"name": item_name, "item_type": "metric", "value_type": "number"},
        headers=admin_headers,
    )
    return item_resp.json()["id"]


@pytest.mark.asyncio
async def test_create_mapping(client: AsyncClient, admin_headers: dict):
    item_id = await _create_item(client, admin_headers, "GRI", "305-1", "Scope 1")

    el_resp = await client.post(
        "/api/shared-elements",
        json={"code": "GHG_S1", "name": "Scope 1 Total"},
        headers=admin_headers,
    )
    el_id = el_resp.json()["id"]

    resp = await client.post(
        "/api/mappings",
        json={
            "requirement_item_id": item_id,
            "shared_element_id": el_id,
            "mapping_type": "full",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["mapping_type"] == "full"


@pytest.mark.asyncio
async def test_duplicate_mapping_creates_new_version(client: AsyncClient, admin_headers: dict):
    item_id = await _create_item(client, admin_headers, "GRI", "305-1", "Scope 1")

    el_resp = await client.post(
        "/api/shared-elements",
        json={"code": "GHG_S1", "name": "Scope 1 Total"},
        headers=admin_headers,
    )
    el_id = el_resp.json()["id"]

    first = await client.post(
        "/api/mappings",
        json={"requirement_item_id": item_id, "shared_element_id": el_id},
        headers=admin_headers,
    )
    assert first.status_code == 201
    assert first.json()["version"] == 1
    assert first.json()["is_current"] is True

    resp = await client.post(
        "/api/mappings",
        json={"requirement_item_id": item_id, "shared_element_id": el_id},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["version"] == 2
    assert resp.json()["is_current"] is True

    history = await client.get(
        f"/api/mappings/{item_id}/{el_id}/history",
        headers=admin_headers,
    )
    assert history.status_code == 200
    assert history.json()["total"] == 2
    assert history.json()["items"][0]["version"] == 2
    assert history.json()["items"][0]["is_current"] is True
    assert history.json()["items"][1]["version"] == 1
    assert history.json()["items"][1]["is_current"] is False


@pytest.mark.asyncio
async def test_mapping_diff_between_versions(client: AsyncClient, admin_headers: dict):
    item_id = await _create_item(client, admin_headers, "GRI", "305-2", "Scope 2")

    el_resp = await client.post(
        "/api/shared-elements",
        json={"code": "GHG_S2", "name": "Scope 2 Total"},
        headers=admin_headers,
    )
    el_id = el_resp.json()["id"]

    first = await client.post(
        "/api/mappings",
        json={
            "requirement_item_id": item_id,
            "shared_element_id": el_id,
            "mapping_type": "full",
        },
        headers=admin_headers,
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/mappings",
        json={
            "requirement_item_id": item_id,
            "shared_element_id": el_id,
            "mapping_type": "partial",
        },
        headers=admin_headers,
    )
    assert second.status_code == 201

    diff = await client.get(
        f"/api/mappings/{item_id}/{el_id}/diff?v1=1&v2=2",
        headers=admin_headers,
    )
    assert diff.status_code == 200
    changes = diff.json()["changes"]
    assert any(change["field"] == "mapping_type" for change in changes)


@pytest.mark.asyncio
async def test_cross_standard_query(client: AsyncClient, admin_headers: dict):
    # Create shared element
    el_resp = await client.post(
        "/api/shared-elements",
        json={"code": "GHG_S1", "name": "Scope 1 Total"},
        headers=admin_headers,
    )
    el_id = el_resp.json()["id"]

    # Map GRI item
    gri_item = await _create_item(client, admin_headers, "GRI", "305-1", "GRI Scope 1")
    await client.post(
        "/api/mappings",
        json={"requirement_item_id": gri_item, "shared_element_id": el_id},
        headers=admin_headers,
    )

    # Map IFRS item
    ifrs_item = await _create_item(client, admin_headers, "IFRS_S2", "S2.29", "IFRS Scope 1")
    await client.post(
        "/api/mappings",
        json={"requirement_item_id": ifrs_item, "shared_element_id": el_id},
        headers=admin_headers,
    )

    # Query cross-standard
    resp = await client.get("/api/mappings/cross-standard", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["shared_element_code"] == "GHG_S1"
    assert set(data[0]["standards"]) == {"GRI", "IFRS_S2"}
    assert data[0]["mapping_count"] == 2


@pytest.mark.asyncio
async def test_list_mappings(client: AsyncClient, admin_headers: dict):
    el_resp = await client.post(
        "/api/shared-elements",
        json={"code": "EL1", "name": "Element 1"},
        headers=admin_headers,
    )
    el_id = el_resp.json()["id"]

    for i in range(3):
        item_id = await _create_item(client, admin_headers, "GRI", f"D{i}", f"Item {i}")
        await client.post(
            "/api/mappings",
            json={"requirement_item_id": item_id, "shared_element_id": el_id},
            headers=admin_headers,
        )

    resp = await client.get("/api/mappings?page_size=500", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 3
    assert len(resp.json()["items"]) == 3


@pytest.mark.asyncio
async def test_one_element_multiple_items(client: AsyncClient, admin_headers: dict):
    """One shared element can be mapped to N items from different standards."""
    el_resp = await client.post(
        "/api/shared-elements",
        json={"code": "ENERGY_TOTAL", "name": "Total Energy"},
        headers=admin_headers,
    )
    el_id = el_resp.json()["id"]

    item1 = await _create_item(client, admin_headers, "GRI", "302-1", "GRI Energy")
    item2 = await _create_item(client, admin_headers, "IFRS", "E1.1", "IFRS Energy")

    r1 = await client.post(
        "/api/mappings",
        json={"requirement_item_id": item1, "shared_element_id": el_id},
        headers=admin_headers,
    )
    r2 = await client.post(
        "/api/mappings",
        json={"requirement_item_id": item2, "shared_element_id": el_id},
        headers=admin_headers,
    )
    assert r1.status_code == 201
    assert r2.status_code == 201
