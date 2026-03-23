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

    return {
        "headers": headers,
        "standard_id": std.json()["id"],
        "item_id": item.json()["id"],
    }


# --- Deltas ---
@pytest.mark.asyncio
async def test_create_delta(client: AsyncClient, ctx: dict):
    resp = await client.post(
        "/api/deltas",
        json={
            "requirement_item_id": ctx["item_id"],
            "standard_id": ctx["standard_id"],
            "delta_type": "additional_item",
            "description": "IFRS requires financial impact assessment",
        },
        headers=ctx["headers"],
    )
    assert resp.status_code == 201
    assert resp.json()["delta_type"] == "additional_item"


@pytest.mark.asyncio
async def test_list_deltas(client: AsyncClient, ctx: dict):
    await client.post(
        "/api/deltas",
        json={"requirement_item_id": ctx["item_id"], "standard_id": ctx["standard_id"], "delta_type": "extra_dimension"},
        headers=ctx["headers"],
    )
    resp = await client.get("/api/deltas")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


# --- AI Assistant ---
@pytest.mark.asyncio
async def test_ai_explain_field(client: AsyncClient, ctx: dict):
    resp = await client.post(
        "/api/ai/explain/field",
        json={"requirement_item_id": ctx["item_id"]},
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    assert "text" in resp.json()
    assert resp.json()["confidence"] == "high"


@pytest.mark.asyncio
async def test_ai_explain_completeness(client: AsyncClient, ctx: dict):
    resp = await client.post(
        "/api/ai/explain/completeness",
        json={"project_id": 1},
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    assert "next_actions" in resp.json()


@pytest.mark.asyncio
async def test_ai_explain_boundary(client: AsyncClient, ctx: dict):
    resp = await client.post(
        "/api/ai/explain/boundary",
        json={"entity_id": 1},
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    assert "reasons" in resp.json()


@pytest.mark.asyncio
async def test_ai_ask(client: AsyncClient, ctx: dict):
    resp = await client.post(
        "/api/ai/ask",
        json={"question": "Why is Plant G not in the report?", "screen": "boundary_view"},
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    assert "text" in resp.json()


@pytest.mark.asyncio
async def test_ai_review_assist(client: AsyncClient, ctx: dict):
    resp = await client.post(
        "/api/ai/review-assist?data_point_id=1",
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    assert "summary" in resp.json()
