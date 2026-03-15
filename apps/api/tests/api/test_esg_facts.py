"""
API tests for /api/v1/esg/facts endpoints.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_create_fact_versions_and_latest_only(client: AsyncClient):
    metric = await client.post(
        "/api/v1/esg/metrics",
        json={"name": "GHG Scope 1", "value_type": "number", "unit": "tCO2e"},
    )
    assert metric.status_code == 201, metric.text
    metric_id = metric.json()["metric_id"]

    entity = await client.post("/api/v1/esg/entities", json={"name": "HQ"})
    assert entity.status_code == 201, entity.text
    entity_id = entity.json()["entity_id"]

    f1 = await client.post(
        "/api/v1/esg/facts",
        json={
            "metric_id": metric_id,
            "period_type": "year",
            "period_start": "2025-01-01",
            "period_end": "2025-12-31",
            "is_ytd": False,
            "entity_id": entity_id,
            "value_json": 123.4,
            "tags": ["A", "b ", "a"],
        },
    )
    assert f1.status_code == 201, f1.text
    fact1 = f1.json()
    assert fact1["status"] == "draft"
    assert fact1["version_number"] == 1
    assert len(fact1["logical_key_hash"]) == 64
    assert fact1["tags"] == ["a", "b"]

    f2 = await client.post(
        "/api/v1/esg/facts",
        json={
            "metric_id": metric_id,
            "period_type": "year",
            "period_start": "2025-01-01",
            "period_end": "2025-12-31",
            "is_ytd": False,
            "entity_id": entity_id,
            "value_json": 125.0,
            "tags": ["b", "a"],
        },
    )
    assert f2.status_code == 201, f2.text
    fact2 = f2.json()
    assert fact2["version_number"] == 2
    assert fact2["supersedes_fact_id"] == fact1["fact_id"]
    assert fact2["logical_key_hash"] == fact1["logical_key_hash"]

    latest = await client.get("/api/v1/esg/facts", params={"latest_only": True})
    assert latest.status_code == 200, latest.text
    latest_items = latest.json()["items"]
    assert len(latest_items) >= 1
    assert any((i["fact_id"] == fact2["fact_id"]) for i in latest_items)

    versions = await client.get(
        "/api/v1/esg/facts",
        params={"logical_key_hash": fact1["logical_key_hash"], "latest_only": False, "page_size": 100},
    )
    assert versions.status_code == 200, versions.text
    ids = [i["fact_id"] for i in versions.json()["items"]]
    assert fact1["fact_id"] in ids
    assert fact2["fact_id"] in ids


@pytest.mark.asyncio
async def test_create_fact_retries_on_version_conflict(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    metric = await client.post(
        "/api/v1/esg/metrics",
        json={"name": "Retry Metric", "value_type": "number", "code": "RETRY_1"},
    )
    assert metric.status_code == 201, metric.text
    metric_id = metric.json()["metric_id"]

    original_flush = db_session.flush
    calls = {"n": 0}

    async def flaky_flush(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            orig = Exception('duplicate key value violates unique constraint "uq_esg_facts_company_logical_version"')
            setattr(orig, "sqlstate", "23505")
            raise IntegrityError("stmt", {}, orig)
        return await original_flush(*args, **kwargs)

    monkeypatch.setattr(db_session, "flush", flaky_flush)

    f1 = await client.post(
        "/api/v1/esg/facts",
        json={
            "metric_id": metric_id,
            "period_type": "year",
            "period_start": "2025-01-01",
            "period_end": "2025-12-31",
            "is_ytd": False,
            "value_json": 1.23,
        },
    )
    assert f1.status_code == 201, f1.text
    assert f1.json()["version_number"] == 1


@pytest.mark.asyncio
async def test_latest_only_prefers_published_over_newer_draft(client: AsyncClient):
    metric = await client.post(
        "/api/v1/esg/metrics",
        json={"name": "Water withdrawal", "value_type": "number", "unit": "m3"},
    )
    assert metric.status_code == 201, metric.text
    metric_id = metric.json()["metric_id"]

    f1 = await client.post(
        "/api/v1/esg/facts",
        json={
            "metric_id": metric_id,
            "period_type": "year",
            "period_start": "2025-01-01",
            "period_end": "2025-12-31",
            "is_ytd": False,
            "value_json": 10,
        },
    )
    assert f1.status_code == 201, f1.text
    fact1 = f1.json()

    pub1 = await client.post(f"/api/v1/esg/facts/{fact1['fact_id']}/publish")
    assert pub1.status_code == 200, pub1.text
    assert pub1.json()["status"] == "published"

    f2 = await client.post(
        "/api/v1/esg/facts",
        json={
            "metric_id": metric_id,
            "period_type": "year",
            "period_start": "2025-01-01",
            "period_end": "2025-12-31",
            "is_ytd": False,
            "value_json": 12,
        },
    )
    assert f2.status_code == 201, f2.text
    fact2 = f2.json()
    assert fact2["status"] == "draft"
    assert fact2["version_number"] == 2

    latest = await client.get(
        "/api/v1/esg/facts",
        params={"latest_only": True, "logical_key_hash": fact1["logical_key_hash"]},
    )
    assert latest.status_code == 200, latest.text
    latest_items = latest.json()["items"]
    assert len(latest_items) == 1
    assert latest_items[0]["fact_id"] == fact1["fact_id"]
    assert latest_items[0]["status"] == "published"

    pub2 = await client.post(f"/api/v1/esg/facts/{fact2['fact_id']}/publish")
    assert pub2.status_code == 200, pub2.text
    assert pub2.json()["status"] == "published"

    latest2 = await client.get(
        "/api/v1/esg/facts",
        params={"latest_only": True, "logical_key_hash": fact1["logical_key_hash"]},
    )
    assert latest2.status_code == 200, latest2.text
    latest_items2 = latest2.json()["items"]
    assert len(latest_items2) == 1
    assert latest_items2[0]["fact_id"] == fact2["fact_id"]
    assert latest_items2[0]["status"] == "published"

    old_now = await client.get(f"/api/v1/esg/facts/{fact1['fact_id']}")
    assert old_now.status_code == 200, old_now.text
    assert old_now.json()["status"] == "superseded"


@pytest.mark.asyncio
async def test_fact_review_workflow_submit_request_changes_publish(client: AsyncClient):
    metric = await client.post(
        "/api/v1/esg/metrics",
        json={"name": "Workflow Metric", "value_type": "number", "code": "WF_1"},
    )
    assert metric.status_code == 201, metric.text
    metric_id = metric.json()["metric_id"]

    fact = await client.post(
        "/api/v1/esg/facts",
        json={
            "metric_id": metric_id,
            "period_type": "year",
            "period_start": "2025-01-01",
            "period_end": "2025-12-31",
            "is_ytd": False,
            "value_json": 1.0,
        },
    )
    assert fact.status_code == 201, fact.text
    fact_id = fact.json()["fact_id"]
    logical_key_hash = fact.json()["logical_key_hash"]

    submitted = await client.post(f"/api/v1/esg/facts/{fact_id}/submit-review")
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "in_review"

    blocked_new_version = await client.post(
        "/api/v1/esg/facts",
        json={
            "metric_id": metric_id,
            "period_type": "year",
            "period_start": "2025-01-01",
            "period_end": "2025-12-31",
            "is_ytd": False,
            "value_json": 2.0,
        },
    )
    assert blocked_new_version.status_code == 409

    changes = await client.post(
        f"/api/v1/esg/facts/{fact_id}/request-changes",
        json={"reason": "Need evidence"},
    )
    assert changes.status_code == 200, changes.text
    assert changes.json()["status"] == "draft"

    submitted2 = await client.post(f"/api/v1/esg/facts/{fact_id}/submit-review")
    assert submitted2.status_code == 200, submitted2.text
    assert submitted2.json()["status"] == "in_review"

    published = await client.post(f"/api/v1/esg/facts/{fact_id}/publish")
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published"

    latest = await client.get("/api/v1/esg/facts", params={"latest_only": True, "logical_key_hash": logical_key_hash})
    assert latest.status_code == 200, latest.text
    assert latest.json()["items"][0]["fact_id"] == fact_id
    assert latest.json()["items"][0]["status"] == "published"


@pytest.mark.asyncio
async def test_restatement_creates_new_version_and_links_supersedes(client: AsyncClient):
    metric = await client.post(
        "/api/v1/esg/metrics",
        json={"name": "Test Metric", "value_type": "integer"},
    )
    assert metric.status_code == 201, metric.text
    metric_id = metric.json()["metric_id"]

    f1 = await client.post(
        "/api/v1/esg/facts",
        json={
            "metric_id": metric_id,
            "period_type": "custom",
            "period_start": "2025-06-01",
            "period_end": "2025-06-30",
            "is_ytd": False,
            "value_json": 1,
        },
    )
    assert f1.status_code == 201, f1.text
    fact1 = f1.json()

    pub1 = await client.post(f"/api/v1/esg/facts/{fact1['fact_id']}/publish")
    assert pub1.status_code == 200, pub1.text

    restated = await client.post(f"/api/v1/esg/facts/{fact1['fact_id']}/restatement")
    assert restated.status_code == 201, restated.text
    f2 = restated.json()
    assert f2["status"] == "draft"
    assert f2["version_number"] == 2
    assert f2["supersedes_fact_id"] == fact1["fact_id"]
    assert f2["logical_key_hash"] == fact1["logical_key_hash"]


@pytest.mark.asyncio
async def test_publish_dataset_fact_creates_dataset_revision_snapshot(client: AsyncClient):
    metric = await client.post(
        "/api/v1/esg/metrics",
        json={"name": "Emissions table", "value_type": "dataset"},
    )
    assert metric.status_code == 201, metric.text
    metric_id = metric.json()["metric_id"]

    ds = await client.post(
        "/api/v1/datasets",
        json={
            "name": "Emissions dataset",
            "schema_json": {"columns": [{"key": "year", "type": "text"}, {"key": "tco2e", "type": "number"}]},
            "rows_json": [["2025", 1.23]],
            "meta_json": {"source": "test"},
        },
    )
    assert ds.status_code == 201, ds.text
    dataset_id = ds.json()["dataset_id"]
    assert ds.json()["current_revision"] == 1

    fact = await client.post(
        "/api/v1/esg/facts",
        json={
            "metric_id": metric_id,
            "period_type": "year",
            "period_start": "2025-01-01",
            "period_end": "2025-12-31",
            "is_ytd": False,
            "dataset_id": dataset_id,
        },
    )
    assert fact.status_code == 201, fact.text
    fact_payload = fact.json()
    assert fact_payload["dataset_id"] == dataset_id


@pytest.mark.asyncio
async def test_fact_review_comments_create_and_list(client: AsyncClient):
    metric = await client.post(
        "/api/v1/esg/metrics",
        json={"name": "Comment Metric", "value_type": "number"},
    )
    assert metric.status_code == 201, metric.text
    metric_id = metric.json()["metric_id"]

    fact = await client.post(
        "/api/v1/esg/facts",
        json={
            "metric_id": metric_id,
            "period_type": "year",
            "period_start": "2025-01-01",
            "period_end": "2025-12-31",
            "is_ytd": False,
            "value_json": 1.0,
        },
    )
    assert fact.status_code == 201, fact.text
    fact_id = fact.json()["fact_id"]

    created = await client.post(
        f"/api/v1/esg/facts/{fact_id}/comments",
        json={"body_md": "Please check @test-admin@example.com"},
    )
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["body_md"] == "Please check @test-admin@example.com"
    assert payload["created_by_name"] == "Test Admin"
    assert payload["created_by_email"] == "test-admin@example.com"

    listed = await client.get(f"/api/v1/esg/facts/{fact_id}/comments")
    assert listed.status_code == 200, listed.text
    items = listed.json()
    assert len(items) == 1
    assert items[0]["comment_id"] == payload["comment_id"]


@pytest.mark.asyncio
async def test_fact_timeline_includes_request_changes_reason(client: AsyncClient):
    metric = await client.post(
        "/api/v1/esg/metrics",
        json={"name": "Timeline Metric", "value_type": "number"},
    )
    assert metric.status_code == 201, metric.text
    metric_id = metric.json()["metric_id"]

    fact = await client.post(
        "/api/v1/esg/facts",
        json={
            "metric_id": metric_id,
            "period_type": "year",
            "period_start": "2025-01-01",
            "period_end": "2025-12-31",
            "is_ytd": False,
            "value_json": 1.0,
        },
    )
    assert fact.status_code == 201, fact.text
    fact_id = fact.json()["fact_id"]

    submitted = await client.post(f"/api/v1/esg/facts/{fact_id}/submit-review")
    assert submitted.status_code == 200, submitted.text

    changes = await client.post(
        f"/api/v1/esg/facts/{fact_id}/request-changes",
        json={"reason": "Need evidence"},
    )
    assert changes.status_code == 200, changes.text

    timeline = await client.get(f"/api/v1/esg/facts/{fact_id}/timeline")
    assert timeline.status_code == 200, timeline.text
    events = timeline.json()
    assert any(
        (
            e["action"] == "esg.fact.request_changes"
            and isinstance(e.get("metadata_json"), dict)
            and e["metadata_json"].get("reason") == "Need evidence"
        )
        for e in events
    )
