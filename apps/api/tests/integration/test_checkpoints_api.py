"""
Integration tests for Checkpoints + Restore endpoints.

Covers:
- create checkpoint + list
- throttle (429)
- restore from checkpoint (strict, deletes extra blocks)
- retention cap (max 30 checkpoints)
"""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Block, ReportCheckpoint


@pytest.mark.asyncio
async def test_create_and_list_checkpoints(
    client: AsyncClient,
    auth_headers: dict,
    test_report_id: str,
):
    resp = await client.post(
        f"/api/v1/reports/{test_report_id}/checkpoints",
        headers=auth_headers,
        json={"comment": "Before CFO review"},
    )
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["report_id"] == test_report_id
    assert created["comment"] == "Before CFO review"
    assert len(created["content_root_hash"]) == 64
    assert created["snapshot_size_bytes"] > 0

    list_resp = await client.get(
        f"/api/v1/reports/{test_report_id}/checkpoints",
        headers=auth_headers,
    )
    assert list_resp.status_code == 200, list_resp.text
    items = list_resp.json()
    assert isinstance(items, list)
    assert any(cp["checkpoint_id"] == created["checkpoint_id"] for cp in items)


@pytest.mark.asyncio
async def test_checkpoint_throttle_429(
    client: AsyncClient,
    auth_headers: dict,
    test_report_id: str,
):
    r1 = await client.post(
        f"/api/v1/reports/{test_report_id}/checkpoints",
        headers=auth_headers,
        json={"comment": "c1"},
    )
    assert r1.status_code == 201, r1.text

    r2 = await client.post(
        f"/api/v1/reports/{test_report_id}/checkpoints",
        headers=auth_headers,
        json={"comment": "c2"},
    )
    assert r2.status_code == 429, r2.text


@pytest.mark.asyncio
async def test_restore_checkpoint_strict_deletes_extra_blocks(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_report_id: str,
    test_section_id: str,
):
    # Create initial block
    b1_resp = await client.post(
        "/api/v1/blocks",
        headers=auth_headers,
        json={
            "report_id": test_report_id,
            "section_id": test_section_id,
            "type": "text",
            "variant": "default",
            "order_index": 0,
            "data_json": {},
            "i18n": [{"locale": "ru", "fields_json": {"body_html": "<p>v1</p>"}}],
        },
    )
    assert b1_resp.status_code == 201, b1_resp.text
    block1_id = b1_resp.json()["block_id"]

    # Create checkpoint capturing block1
    cp_resp = await client.post(
        f"/api/v1/reports/{test_report_id}/checkpoints",
        headers=auth_headers,
        json={"comment": "cp"},
    )
    assert cp_resp.status_code == 201, cp_resp.text
    checkpoint_id = cp_resp.json()["checkpoint_id"]

    # Create extra block after checkpoint
    b2_resp = await client.post(
        "/api/v1/blocks",
        headers=auth_headers,
        json={
            "report_id": test_report_id,
            "section_id": test_section_id,
            "type": "text",
            "variant": "default",
            "order_index": 1,
            "data_json": {},
            "i18n": [{"locale": "ru", "fields_json": {"body_html": "<p>extra</p>"}}],
        },
    )
    assert b2_resp.status_code == 201, b2_resp.text
    block2_id = b2_resp.json()["block_id"]

    # Sanity: block2 exists
    b2 = await db_session.get(Block, UUID(block2_id))
    assert b2 is not None

    # Restore
    restore_resp = await client.post(
        f"/api/v1/checkpoints/{checkpoint_id}/restore",
        headers=auth_headers,
        json={},
    )
    assert restore_resp.status_code == 200, restore_resp.text
    payload = restore_resp.json()
    assert payload["restored_to"] == checkpoint_id
    assert payload["safety_checkpoint_id"]

    # Extra block should be deleted; original remains
    b1 = await db_session.get(Block, UUID(block1_id))
    b2 = await db_session.get(Block, UUID(block2_id))
    assert b1 is not None
    assert b2 is None

    # Safety checkpoint row exists
    safety = await db_session.get(ReportCheckpoint, UUID(payload["safety_checkpoint_id"]))
    assert safety is not None
    assert safety.report_id == UUID(test_report_id)


@pytest.mark.asyncio
async def test_checkpoint_retention_max_30(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_report_id: str,
):
    # Create 35 checkpoints, bypassing throttle by shifting timestamps back each iteration.
    for i in range(35):
        resp = await client.post(
            f"/api/v1/reports/{test_report_id}/checkpoints",
            headers=auth_headers,
            json={"comment": f"cp-{i}"},
        )
        assert resp.status_code == 201, resp.text

        # Move all checkpoint timestamps back so the next request won't hit 60s throttle.
        await db_session.execute(
            text(
                "UPDATE report_checkpoints "
                "SET created_at_utc = created_at_utc - interval '61 seconds' "
                "WHERE report_id = :rid"
            ),
            {"rid": test_report_id},
        )
        await db_session.flush()

    rows = await db_session.execute(
        select(ReportCheckpoint.checkpoint_id).where(ReportCheckpoint.report_id == UUID(test_report_id))
    )
    checkpoint_ids = rows.scalars().all()
    assert len(checkpoint_ids) <= 30


