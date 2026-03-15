"""
Integration smoke test: preview rendering for a section containing all block types.

Goal:
- Catch template/schema drift that would otherwise surface as 500s in Design preview
- Ensure charts do not duplicate caption between HTML header and Vega SVG title in preview
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.fixtures.block_payloads_v2 import ALL_BLOCK_PAYLOADS


@pytest.mark.asyncio
async def test_preview_section_by_id_renders_all_blocks_without_crash(
    auth_client: AsyncClient, test_report_id: str
) -> None:
    # Create a dedicated section
    section_resp = await auth_client.post(
        "/api/v1/sections",
        json={
            "report_id": test_report_id,
            "order_index": 0,
            "depth": 0,
            "i18n": [{"locale": "ru", "title": "Preview Smoke", "slug": "preview-smoke"}],
        },
    )
    assert section_resp.status_code == 201, section_resp.text
    section_id = section_resp.json()["section_id"]

    created_blocks: list[dict] = []

    # Create one block per payload (includes all block types + table modes + 8 chart types)
    for payload in ALL_BLOCK_PAYLOADS:
        i18n_entry: dict = {"locale": "ru", "fields_json": payload.fields_json or {}}
        if payload.custom_html_sanitized:
            i18n_entry["custom_html_sanitized"] = payload.custom_html_sanitized

        block_resp = await auth_client.post(
            "/api/v1/blocks",
            json={
                "report_id": test_report_id,
                "section_id": section_id,
                "type": payload.block_type.value,
                "variant": payload.variant.value,
                "order_index": 0,  # append
                "data_json": payload.data_json or {},
                "i18n": [i18n_entry],
            },
        )
        assert block_resp.status_code == 201, block_resp.text
        created_blocks.append(block_resp.json())

    # Render preview for the section by ID (Design page uses this endpoint)
    preview = await auth_client.get(
        f"/api/v1/preview/ru/sections-by-id/{section_id}",
        params={"theme_slug": "default"},
    )
    assert preview.status_code == 200, preview.text
    html = preview.text

    # Ensure all created blocks are present in HTML
    for b in created_blocks:
        block_id = b["block_id"]
        assert f'block-{block_id}' in html, f"Missing rendered block {block_id}"

    # Ensure chart captions are not duplicated (HTML header should be the only place)
    for payload in ALL_BLOCK_PAYLOADS:
        if payload.block_type.value != "chart":
            continue
        caption = (payload.fields_json or {}).get("caption") or ""
        if caption:
            assert html.count(caption) == 1, f"Caption duplicated in preview HTML: {caption}"



