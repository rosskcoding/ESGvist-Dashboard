"""
API tests for /api/v1/esg dimension endpoints.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_list_entities(client: AsyncClient):
    create = await client.post(
        "/api/v1/esg/entities",
        json={"code": "HQ", "name": "Headquarters", "description": "Main legal entity"},
    )
    assert create.status_code == 201
    created = create.json()
    assert created["name"] == "Headquarters"
    assert created["code"] == "HQ"
    assert "entity_id" in created

    listed = await client.get("/api/v1/esg/entities")
    assert listed.status_code == 200
    data = listed.json()
    assert data["total"] >= 1
    assert any((i["entity_id"] == created["entity_id"]) for i in data["items"])


@pytest.mark.asyncio
async def test_entity_search(client: AsyncClient):
    await client.post("/api/v1/esg/entities", json={"code": "PLANT-1", "name": "Plant One"})
    await client.post("/api/v1/esg/entities", json={"code": "PLANT-2", "name": "Plant Two"})

    resp = await client.get("/api/v1/esg/entities", params={"search": "Two"})
    assert resp.status_code == 200
    data = resp.json()
    assert any((i["name"] == "Plant Two") for i in data["items"])


@pytest.mark.asyncio
async def test_update_location(client: AsyncClient):
    created = await client.post("/api/v1/esg/locations", json={"code": "KZ", "name": "Kazakhstan"})
    assert created.status_code == 201
    location_id = created.json()["location_id"]

    updated = await client.patch(
        f"/api/v1/esg/locations/{location_id}",
        json={"name": "Kazakhstan (Updated)", "is_active": False},
    )
    assert updated.status_code == 200
    payload = updated.json()
    assert payload["name"] == "Kazakhstan (Updated)"
    assert payload["is_active"] is False


@pytest.mark.asyncio
async def test_create_segment(client: AsyncClient):
    created = await client.post("/api/v1/esg/segments", json={"name": "Upstream"})
    assert created.status_code == 201
    payload = created.json()
    assert payload["name"] == "Upstream"
    assert payload["is_active"] is True


@pytest.mark.asyncio
async def test_create_entity_conflict_on_duplicate_code(client: AsyncClient):
    one = await client.post("/api/v1/esg/entities", json={"code": "DUP_ENT_1", "name": "Dup entity 1"})
    assert one.status_code == 201, one.text

    two = await client.post("/api/v1/esg/entities", json={"code": "DUP_ENT_1", "name": "Dup entity 2"})
    assert two.status_code == 409, two.text
    payload = two.json()
    assert "detail" in payload
    assert "code" in payload["detail"].lower()
