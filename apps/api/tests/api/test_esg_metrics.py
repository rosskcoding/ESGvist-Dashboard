"""
API tests for /api/v1/esg/metrics endpoints.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_get_update_metric(client: AsyncClient):
    create = await client.post(
        "/api/v1/esg/metrics",
        json={
            "code": "GHG_SCOPE1",
            "name": "GHG Scope 1",
            "description": "Direct emissions",
            "value_type": "number",
            "unit": "tCO2e",
        },
    )
    assert create.status_code == 201
    metric = create.json()
    assert metric["name"] == "GHG Scope 1"
    metric_id = metric["metric_id"]

    fetched = await client.get(f"/api/v1/esg/metrics/{metric_id}")
    assert fetched.status_code == 200
    assert fetched.json()["metric_id"] == metric_id

    updated = await client.patch(
        f"/api/v1/esg/metrics/{metric_id}",
        json={"name": "GHG Scope 1 (Updated)", "is_active": False},
    )
    assert updated.status_code == 200
    payload = updated.json()
    assert payload["name"] == "GHG Scope 1 (Updated)"
    assert payload["is_active"] is False


@pytest.mark.asyncio
async def test_list_metrics_search(client: AsyncClient):
    await client.post(
        "/api/v1/esg/metrics",
        json={"name": "Water withdrawal", "value_type": "number", "unit": "m3"},
    )
    await client.post(
        "/api/v1/esg/metrics",
        json={"name": "Water discharge", "value_type": "number", "unit": "m3"},
    )

    resp = await client.get("/api/v1/esg/metrics", params={"search": "discharge"})
    assert resp.status_code == 200
    data = resp.json()
    assert any((i["name"] == "Water discharge") for i in data["items"])


@pytest.mark.asyncio
async def test_delete_metric(client: AsyncClient):
    create = await client.post(
        "/api/v1/esg/metrics",
        json={"name": "Temp metric", "value_type": "number", "unit": "t"},
    )
    assert create.status_code == 201
    metric_id = create.json()["metric_id"]

    deleted = await client.delete(f"/api/v1/esg/metrics/{metric_id}")
    assert deleted.status_code == 204

    fetched = await client.get(f"/api/v1/esg/metrics/{metric_id}")
    assert fetched.status_code == 404


@pytest.mark.asyncio
async def test_delete_metric_conflict_when_facts_exist(client: AsyncClient):
    create = await client.post(
        "/api/v1/esg/metrics",
        json={"name": "Metric with facts", "value_type": "number", "unit": "t"},
    )
    assert create.status_code == 201
    metric_id = create.json()["metric_id"]

    fact = await client.post(
        "/api/v1/esg/facts",
        json={
            "metric_id": metric_id,
            "period_type": "year",
            "period_start": "2025-01-01",
            "period_end": "2025-12-31",
            "is_ytd": False,
            "value_json": 123,
        },
    )
    assert fact.status_code == 201

    deleted = await client.delete(f"/api/v1/esg/metrics/{metric_id}")
    assert deleted.status_code == 409


@pytest.mark.asyncio
async def test_create_metric_conflict_on_duplicate_code(client: AsyncClient):
    one = await client.post(
        "/api/v1/esg/metrics",
        json={"code": "DUP_CODE_1", "name": "Dup metric 1", "value_type": "number"},
    )
    assert one.status_code == 201, one.text

    two = await client.post(
        "/api/v1/esg/metrics",
        json={"code": "DUP_CODE_1", "name": "Dup metric 2", "value_type": "number"},
    )
    assert two.status_code == 409, two.text
    payload = two.json()
    assert "detail" in payload
    assert "code" in payload["detail"].lower()


@pytest.mark.asyncio
async def test_update_metric_blocks_value_type_and_unit_changes_when_facts_exist(client: AsyncClient):
    create = await client.post(
        "/api/v1/esg/metrics",
        json={"name": "Immutable metric", "value_type": "number", "unit": "t", "code": "IMM_1"},
    )
    assert create.status_code == 201, create.text
    metric_id = create.json()["metric_id"]

    fact = await client.post(
        "/api/v1/esg/facts",
        json={
            "metric_id": metric_id,
            "period_type": "year",
            "period_start": "2025-01-01",
            "period_end": "2025-12-31",
            "is_ytd": False,
            "value_json": 123,
        },
    )
    assert fact.status_code == 201, fact.text

    change_type = await client.patch(f"/api/v1/esg/metrics/{metric_id}", json={"value_type": "integer"})
    assert change_type.status_code == 409, change_type.text

    change_unit = await client.patch(f"/api/v1/esg/metrics/{metric_id}", json={"unit": "kg"})
    assert change_unit.status_code == 409, change_unit.text

    ok = await client.patch(f"/api/v1/esg/metrics/{metric_id}", json={"name": "Still ok"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["name"] == "Still ok"
