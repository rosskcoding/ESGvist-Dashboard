"""
API tests for ESG fact evidence + compare endpoints.
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.domain.models import Asset
from app.domain.models.enums import AssetKind


@pytest.mark.asyncio
async def test_fact_evidence_crud(client: AsyncClient, db_session, test_company, current_user):
    metric = await client.post(
        "/api/v1/esg/metrics",
        json={"name": "Test Metric", "value_type": "number"},
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
            "value_json": 1.23,
        },
    )
    assert fact.status_code == 201, fact.text
    fact_id = fact.json()["fact_id"]

    link = await client.post(
        f"/api/v1/esg/facts/{fact_id}/evidence",
        json={
            "type": "link",
            "title": "Source",
            "url": "https://example.com",
            "source": "ERP export",
            "source_date": "2025-03-01",
            "owner_user_id": str(current_user.user_id),
        },
    )
    assert link.status_code == 201, link.text
    link_payload = link.json()
    link_id = link_payload["evidence_id"]
    assert link_payload["source"] == "ERP export"
    assert link_payload["source_date"] == "2025-03-01"
    assert link_payload["owner_user_id"] == str(current_user.user_id)

    note = await client.post(
        f"/api/v1/esg/facts/{fact_id}/evidence",
        json={"type": "note", "title": "Note", "note_md": "Hello"},
    )
    assert note.status_code == 201, note.text

    asset = Asset(
        asset_id=uuid4(),
        company_id=test_company.company_id,
        kind=AssetKind.ATTACHMENT,
        filename="evidence.pdf",
        storage_path=f"company/{test_company.company_id}/assets/{uuid4()}/evidence.pdf",
        mime_type="application/pdf",
        size_bytes=123,
        sha256="0" * 64,
        created_by=current_user.user_id,
    )
    db_session.add(asset)
    await db_session.flush()

    file_ev = await client.post(
        f"/api/v1/esg/facts/{fact_id}/evidence",
        json={"type": "file", "title": "Attachment", "asset_id": str(asset.asset_id)},
    )
    assert file_ev.status_code == 201, file_ev.text
    assert file_ev.json()["asset_id"] == str(asset.asset_id)

    listed = await client.get(f"/api/v1/esg/facts/{fact_id}/evidence")
    assert listed.status_code == 200, listed.text
    items = listed.json()
    assert len(items) == 3
    assert {i["type"] for i in items} == {"link", "note", "file"}

    updated = await client.patch(
        f"/api/v1/esg/facts/{fact_id}/evidence/{link_id}",
        json={
            "title": "Source (updated)",
            "source": "Data warehouse export",
            "source_date": None,
            "owner_user_id": None,
        },
    )
    assert updated.status_code == 200, updated.text
    updated_payload = updated.json()
    assert updated_payload["title"] == "Source (updated)"
    assert updated_payload["source"] == "Data warehouse export"
    assert updated_payload["source_date"] is None
    assert updated_payload["owner_user_id"] is None

    deleted = await client.delete(f"/api/v1/esg/facts/{fact_id}/evidence/{link_id}")
    assert deleted.status_code == 204, deleted.text

    listed2 = await client.get(f"/api/v1/esg/facts/{fact_id}/evidence")
    assert listed2.status_code == 200, listed2.text
    assert len(listed2.json()) == 2


@pytest.mark.asyncio
async def test_list_facts_returns_evidence_count(client: AsyncClient):
    metric = await client.post(
        "/api/v1/esg/metrics",
        json={"name": "Evidence Count Metric", "value_type": "number"},
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
            "value_json": 10,
        },
    )
    assert fact.status_code == 201, fact.text
    fact_payload = fact.json()

    listed = await client.get(
        "/api/v1/esg/facts",
        params={"logical_key_hash": fact_payload["logical_key_hash"], "latest_only": "true"},
    )
    assert listed.status_code == 200, listed.text
    items = listed.json()["items"]
    assert len(items) == 1
    assert items[0]["fact_id"] == fact_payload["fact_id"]
    assert items[0]["evidence_count"] == 0

    note = await client.post(
        f"/api/v1/esg/facts/{fact_payload['fact_id']}/evidence",
        json={"type": "note", "title": "Note", "note_md": "Hello"},
    )
    assert note.status_code == 201, note.text

    listed2 = await client.get(
        "/api/v1/esg/facts",
        params={"logical_key_hash": fact_payload["logical_key_hash"], "latest_only": "true"},
    )
    assert listed2.status_code == 200, listed2.text
    items2 = listed2.json()["items"]
    assert len(items2) == 1
    assert items2[0]["fact_id"] == fact_payload["fact_id"]
    assert items2[0]["evidence_count"] == 1


@pytest.mark.asyncio
async def test_list_facts_can_filter_by_has_evidence_and_respects_latest_only(client: AsyncClient):
    metric = await client.post(
        "/api/v1/esg/metrics",
        json={"name": "Evidence Filter Metric", "value_type": "number"},
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

    # No evidence yet => should show up when filtering for missing evidence.
    missing = await client.get(
        "/api/v1/esg/facts",
        params={
            "logical_key_hash": fact1["logical_key_hash"],
            "latest_only": "true",
            "has_evidence": "false",
        },
    )
    assert missing.status_code == 200, missing.text
    assert missing.json()["total"] == 1

    # Add evidence and publish.
    note = await client.post(
        f"/api/v1/esg/facts/{fact1['fact_id']}/evidence",
        json={"type": "note", "title": "Note", "note_md": "Hello"},
    )
    assert note.status_code == 201, note.text

    pub = await client.post(f"/api/v1/esg/facts/{fact1['fact_id']}/publish")
    assert pub.status_code == 200, pub.text

    # Create a newer draft version WITHOUT evidence. latest_only should still prefer the published fact.
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

    missing_latest = await client.get(
        "/api/v1/esg/facts",
        params={
            "logical_key_hash": fact1["logical_key_hash"],
            "latest_only": "true",
            "has_evidence": "false",
        },
    )
    assert missing_latest.status_code == 200, missing_latest.text
    assert missing_latest.json()["total"] == 0

    missing_any = await client.get(
        "/api/v1/esg/facts",
        params={
            "logical_key_hash": fact1["logical_key_hash"],
            "latest_only": "false",
            "has_evidence": "false",
        },
    )
    assert missing_any.status_code == 200, missing_any.text
    assert missing_any.json()["total"] == 1


@pytest.mark.asyncio
async def test_compare_endpoint_returns_latest_by_rules(client: AsyncClient):
    metric = await client.post(
        "/api/v1/esg/metrics",
        json={"name": "Compare Metric", "value_type": "number"},
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

    cmp1 = await client.post(
        "/api/v1/esg/facts/compare",
        json={"logical_key_hashes": [fact1["logical_key_hash"], "0" * 64]},
    )
    assert cmp1.status_code == 200, cmp1.text
    items = cmp1.json()
    assert len(items) == 2

    first = items[0]
    assert first["logical_key_hash"] == fact1["logical_key_hash"]
    assert first["latest"]["fact_id"] == fact1["fact_id"]
    assert first["latest"]["status"] == "published"

    assert items[1]["latest"] is None

    pub2 = await client.post(f"/api/v1/esg/facts/{fact2['fact_id']}/publish")
    assert pub2.status_code == 200, pub2.text

    cmp2 = await client.post(
        "/api/v1/esg/facts/compare",
        json={"logical_key_hashes": [fact1["logical_key_hash"]]},
    )
    assert cmp2.status_code == 200, cmp2.text
    assert cmp2.json()[0]["latest"]["fact_id"] == fact2["fact_id"]
