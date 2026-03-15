import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_esg_gaps_reports_missing_metrics_and_quality_issues(client: AsyncClient):
    metric_ok = await client.post(
        "/api/v1/esg/metrics",
        json={"name": "Ok metric", "value_type": "number", "code": "OK_1"},
    )
    assert metric_ok.status_code == 201, metric_ok.text
    metric_ok_id = metric_ok.json()["metric_id"]

    metric_blocked = await client.post(
        "/api/v1/esg/metrics",
        json={
            "name": "Blocked metric",
            "value_type": "number",
            "code": "BLK_1",
            "value_schema_json": {
                "requirements": {
                    "sources": {"required_fields": ["source"]},
                    "evidence": {"min_items": 1},
                },
                "checks": {"range": {"min": 0, "max": 10}},
            },
        },
    )
    assert metric_blocked.status_code == 201, metric_blocked.text
    metric_blocked_id = metric_blocked.json()["metric_id"]

    # Published fact covers OK_1 for 2025.
    f_ok = await client.post(
        "/api/v1/esg/facts",
        json={
            "metric_id": metric_ok_id,
            "period_type": "year",
            "period_start": "2025-01-01",
            "period_end": "2025-12-31",
            "is_ytd": False,
            "value_json": 5.0,
        },
    )
    assert f_ok.status_code == 201, f_ok.text
    ok_fact_id = f_ok.json()["fact_id"]

    pub_ok = await client.post(f"/api/v1/esg/facts/{ok_fact_id}/publish")
    assert pub_ok.status_code == 200, pub_ok.text

    # Draft fact for BLK_1 should show as missing published + quality issues.
    f_blk = await client.post(
        "/api/v1/esg/facts",
        json={
            "metric_id": metric_blocked_id,
            "period_type": "year",
            "period_start": "2025-01-01",
            "period_end": "2025-12-31",
            "is_ytd": False,
            "value_json": 50.0,
            "sources_json": {},
            "quality_json": {},
        },
    )
    assert f_blk.status_code == 201, f_blk.text
    blk_fact_id = f_blk.json()["fact_id"]

    gaps = await client.get(
        "/api/v1/esg/gaps",
        params={
            "period_type": "year",
            "period_start": "2025-01-01",
            "period_end": "2025-12-31",
            "is_ytd": "false",
        },
    )
    assert gaps.status_code == 200, gaps.text
    data = gaps.json()

    assert data["metrics_total"] == 2
    assert data["metrics_with_published"] == 1
    assert data["metrics_missing_published"] == 1
    assert any((m["metric_id"] == metric_blocked_id) for m in data["missing_metrics"])

    attention = next((f for f in data["attention_facts"] if f["fact_id"] == blk_fact_id), None)
    assert attention is not None
    issue_codes = {i["code"] for i in attention["issues"]}
    assert "missing_evidence" in issue_codes
    assert "missing_source:source" in issue_codes
    assert "range_above_max" in issue_codes


@pytest.mark.asyncio
async def test_esg_gaps_filters_metrics_by_standard_mapping(client: AsyncClient):
    metric_gri = await client.post(
        "/api/v1/esg/metrics",
        json={
            "name": "GRI mapped metric",
            "value_type": "number",
            "code": "GRI_1",
            "value_schema_json": {
                "standards": [
                    {"standard": "GRI", "disclosure_id": "305-1", "required": True},
                ]
            },
        },
    )
    assert metric_gri.status_code == 201, metric_gri.text
    metric_gri_id = metric_gri.json()["metric_id"]

    metric_unmapped = await client.post(
        "/api/v1/esg/metrics",
        json={"name": "Unmapped metric", "value_type": "number", "code": "UNM_1"},
    )
    assert metric_unmapped.status_code == 201, metric_unmapped.text

    # Published fact covers GRI_1 for 2025.
    f_ok = await client.post(
        "/api/v1/esg/facts",
        json={
            "metric_id": metric_gri_id,
            "period_type": "year",
            "period_start": "2025-01-01",
            "period_end": "2025-12-31",
            "is_ytd": False,
            "value_json": 1.0,
        },
    )
    assert f_ok.status_code == 201, f_ok.text
    ok_fact_id = f_ok.json()["fact_id"]

    pub_ok = await client.post(f"/api/v1/esg/facts/{ok_fact_id}/publish")
    assert pub_ok.status_code == 200, pub_ok.text

    gaps = await client.get(
        "/api/v1/esg/gaps",
        params={
            "period_type": "year",
            "period_start": "2025-01-01",
            "period_end": "2025-12-31",
            "is_ytd": "false",
            "standard": "GRI",
        },
    )
    assert gaps.status_code == 200, gaps.text
    data = gaps.json()

    assert data["standard"] == "GRI"
    assert data["metrics_total"] == 1
    assert data["metrics_with_published"] == 1
    assert data["metrics_missing_published"] == 0


@pytest.mark.asyncio
async def test_esg_snapshot_returns_hash_and_published_facts(client: AsyncClient):
    metric_gri = await client.post(
        "/api/v1/esg/metrics",
        json={
            "name": "GRI snapshot metric",
            "value_type": "number",
            "code": "GRI_SNAP_1",
            "value_schema_json": {"standards": [{"standard": "GRI", "disclosure_id": "305-1"}]},
        },
    )
    assert metric_gri.status_code == 201, metric_gri.text
    metric_gri_id = metric_gri.json()["metric_id"]

    metric_other = await client.post(
        "/api/v1/esg/metrics",
        json={"name": "Other metric", "value_type": "number", "code": "OTHER_1"},
    )
    assert metric_other.status_code == 201, metric_other.text

    f_ok = await client.post(
        "/api/v1/esg/facts",
        json={
            "metric_id": metric_gri_id,
            "period_type": "year",
            "period_start": "2025-01-01",
            "period_end": "2025-12-31",
            "is_ytd": False,
            "value_json": 2.0,
        },
    )
    assert f_ok.status_code == 201, f_ok.text
    ok_fact_id = f_ok.json()["fact_id"]

    pub_ok = await client.post(f"/api/v1/esg/facts/{ok_fact_id}/publish")
    assert pub_ok.status_code == 200, pub_ok.text

    snap = await client.get(
        "/api/v1/esg/snapshot",
        params={
            "period_type": "year",
            "period_start": "2025-01-01",
            "period_end": "2025-12-31",
            "is_ytd": "false",
            "standard": "GRI",
        },
    )
    assert snap.status_code == 200, snap.text
    data = snap.json()

    assert data["standard"] == "GRI"
    assert isinstance(data["snapshot_hash"], str)
    assert len(data["snapshot_hash"]) == 64
    assert data["metrics_total"] == 1
    assert data["facts_published"] == 1
    assert any((f["fact"]["fact_id"] == ok_fact_id) for f in data["facts"])
