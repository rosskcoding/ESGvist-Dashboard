"""
API tests for /api/v1/esg/facts/import/* endpoints.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_import_csv_preview_confirm_idempotent(client: AsyncClient):
    metric = await client.post(
        "/api/v1/esg/metrics",
        json={"name": "Imported Metric", "value_type": "number", "code": "IMP_NUM"},
    )
    assert metric.status_code == 201, metric.text

    csv_content = (
        "metric_code,period_type,period_start,period_end,value,sources_json,quality_json\n"
        "IMP_NUM,year,2025-01-01,2025-12-31,123.4,\"{}\",\"{}\"\n"
    ).encode("utf-8")

    preview = await client.post(
        "/api/v1/esg/facts/import/csv/preview",
        files={"file": ("facts.csv", csv_content, "text/csv")},
    )
    assert preview.status_code == 200, preview.text
    payload = preview.json()
    assert payload["total_rows"] == 1
    assert payload["create_rows"] == 1
    assert payload["error_rows"] == 0

    confirm = await client.post(
        "/api/v1/esg/facts/import/csv/confirm",
        files={"file": ("facts.csv", csv_content, "text/csv")},
    )
    assert confirm.status_code == 200, confirm.text
    res = confirm.json()
    assert res["total_rows"] == 1
    assert res["created"] == 1
    assert res["skipped"] == 0
    assert res["error_rows"] == 0

    confirm2 = await client.post(
        "/api/v1/esg/facts/import/csv/confirm",
        files={"file": ("facts.csv", csv_content, "text/csv")},
    )
    assert confirm2.status_code == 200, confirm2.text
    res2 = confirm2.json()
    assert res2["created"] == 0
    assert res2["skipped"] == 1
    assert res2["error_rows"] == 0


@pytest.mark.asyncio
async def test_import_csv_confirm_retries_on_version_conflict(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    metric = await client.post(
        "/api/v1/esg/metrics",
        json={"name": "Imported Metric Retry", "value_type": "number", "code": "IMP_RETRY"},
    )
    assert metric.status_code == 201, metric.text

    csv_content = (
        "metric_code,period_type,period_start,period_end,value\n"
        "IMP_RETRY,year,2025-01-01,2025-12-31,42\n"
    ).encode("utf-8")

    # Force the first flush inside confirm_rows() to raise a unique violation.
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

    confirm = await client.post(
        "/api/v1/esg/facts/import/csv/confirm",
        files={"file": ("facts.csv", csv_content, "text/csv")},
    )
    assert confirm.status_code == 200, confirm.text
    res = confirm.json()
    assert res["created"] == 1
    assert res["error_rows"] == 0


@pytest.mark.asyncio
async def test_import_csv_blocks_in_review_latest(client: AsyncClient):
    metric = await client.post(
        "/api/v1/esg/metrics",
        json={"name": "In review metric", "value_type": "number", "code": "IMP_REVIEW"},
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
    fact_id = fact.json()["fact_id"]

    submitted = await client.post(f"/api/v1/esg/facts/{fact_id}/submit-review")
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "in_review"

    csv_content = (
        "metric_code,period_type,period_start,period_end,value\n"
        "IMP_REVIEW,year,2025-01-01,2025-12-31,11\n"
    ).encode("utf-8")

    preview = await client.post(
        "/api/v1/esg/facts/import/csv/preview",
        files={"file": ("facts.csv", csv_content, "text/csv")},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["error_rows"] == 1
