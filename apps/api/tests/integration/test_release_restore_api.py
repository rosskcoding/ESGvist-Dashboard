"""
Integration tests for Release Restore endpoint.

Covers:
- POST /api/v1/releases/{build_id}/restore reads content-snapshot.json from ZIP
- creates safety checkpoint
- restores DB content (strict mode)
"""

from __future__ import annotations

import json
import tempfile
import zipfile
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Block, ReleaseBuild, ReportCheckpoint
from app.domain.models.enums import BuildScope, BuildStatus, BuildType, PackageMode
from app.services.content_snapshot import build_report_content_snapshot


@pytest.mark.asyncio
@pytest.mark.skip(reason="Endpoint /api/v1/releases/{build_id}/restore not yet implemented")
async def test_release_restore_deletes_blocks_strict(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_report_id: str,
    test_section_id: str,
):
    # Create a block that should be removed by restore
    b_resp = await client.post(
        "/api/v1/blocks",
        headers=auth_headers,
        json={
            "report_id": test_report_id,
            "section_id": test_section_id,
            "type": "text",
            "variant": "default",
            "order_index": 0,
            "data_json": {},
            "i18n": [{"locale": "ru", "fields_json": {"body_html": "<p>current</p>"}}],
        },
    )
    assert b_resp.status_code == 201, b_resp.text
    block_id = b_resp.json()["block_id"]

    # Build snapshot and remove blocks array to force deletion
    snapshot = await build_report_content_snapshot(db_session, UUID(test_report_id))
    snapshot["blocks"] = []

    # Write ZIP with content-snapshot.json
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        zip_path = tmp.name

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("content-snapshot.json", json.dumps(snapshot, ensure_ascii=False))

    # Create a successful RELEASE build pointing to the ZIP
    build = ReleaseBuild(
        report_id=UUID(test_report_id),
        build_type=BuildType.RELEASE,
        status=BuildStatus.SUCCESS,
        theme_slug="default",
        base_path="/",
        locales=["ru"],
        package_mode=PackageMode.PORTABLE,
        scope=BuildScope.FULL,
        zip_path=zip_path,
        zip_sha256=None,
        manifest_path=None,
    )
    db_session.add(build)
    await db_session.flush()

    # Restore from release
    r = await client.post(
        f"/api/v1/releases/{build.build_id}/restore",
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["status"] == "ok"
    assert payload["safety_checkpoint_id"]

    # Block should be deleted
    deleted = await db_session.get(Block, UUID(block_id))
    assert deleted is None

    # Safety checkpoint exists
    safety = await db_session.get(ReportCheckpoint, UUID(payload["safety_checkpoint_id"]))
    assert safety is not None
    assert safety.report_id == UUID(test_report_id)



