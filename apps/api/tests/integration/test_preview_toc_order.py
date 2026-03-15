"""
Integration tests for Preview TOC ordering and template robustness.

We specifically validate two recent fixes:
1) Preview TOC ordering respects section hierarchy (parent → children).
2) Preview does not crash if a table builder row is missing `cells` in stored JSON.
"""

from __future__ import annotations

import re

import pytest
from httpx import AsyncClient


def _extract_toc_titles(html: str) -> list[str]:
    """
    Extract TOC link titles from preview HTML without external parsing deps.
    """
    m = re.search(
        r'<aside[^>]*id="toc"[^>]*>(.*?)</aside>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert m, "TOC <aside id='toc'> not found in preview HTML"

    toc_html = m.group(1)
    titles = re.findall(
        r'<a[^>]*class="[^"]*rpt-nav__link[^"]*"[^>]*>\s*([^<]+?)\s*</a>',
        toc_html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    cleaned: list[str] = []
    for t in titles:
        t = re.sub(r"\s+", " ", t).strip()
        if t:
            cleaned.append(t)
    return cleaned


@pytest.mark.asyncio
async def test_preview_toc_respects_section_hierarchy(auth_client: AsyncClient, test_report_id: str):
    async def create_section(payload: dict) -> dict:
        resp = await auth_client.post("/api/v1/sections", json=payload)
        assert resp.status_code == 201, resp.text
        return resp.json()

    # Root sections in a deterministic order.
    root_a = await create_section(
        {
            "report_id": test_report_id,
            "order_index": 0,
            "depth": 0,
            "i18n": [{"locale": "ru", "title": "Root A", "slug": "root-a"}],
        }
    )
    root_b = await create_section(
        {
            "report_id": test_report_id,
            "order_index": 1,
            "depth": 0,
            "i18n": [{"locale": "ru", "title": "Root B", "slug": "root-b"}],
        }
    )
    root_c = await create_section(
        {
            "report_id": test_report_id,
            "order_index": 2,
            "depth": 0,
            "i18n": [{"locale": "ru", "title": "Root C", "slug": "root-c"}],
        }
    )

    # Children under Root B.
    child_b1 = await create_section(
        {
            "report_id": test_report_id,
            "parent_section_id": root_b["section_id"],
            "order_index": 0,
            "depth": 1,
            "i18n": [{"locale": "ru", "title": "Child B1", "slug": "child-b1"}],
        }
    )
    await create_section(
        {
            "report_id": test_report_id,
            "parent_section_id": root_b["section_id"],
            "order_index": 1,
            "depth": 1,
            "i18n": [{"locale": "ru", "title": "Child B2", "slug": "child-b2"}],
        }
    )

    # Grandchild under Child B1.
    await create_section(
        {
            "report_id": test_report_id,
            "parent_section_id": child_b1["section_id"],
            "order_index": 0,
            "depth": 2,
            "i18n": [{"locale": "ru", "title": "Grandchild B1a", "slug": "grandchild-b1a"}],
        }
    )

    # Render preview for any section in the report; TOC should reflect the entire structure.
    resp = await auth_client.get(
        "/api/v1/preview/ru/sections/root-a",
        params={"report_id": test_report_id},
    )
    assert resp.status_code == 200, resp.text

    toc_titles = _extract_toc_titles(resp.text)
    assert toc_titles == [
        "Root A",
        "Root B",
        "Child B1",
        "Grandchild B1a",
        "Child B2",
        "Root C",
    ]


@pytest.mark.asyncio
async def test_preview_table_builder_row_without_cells_does_not_500(auth_client: AsyncClient, test_report_id: str):
    # Create a section that contains a table block.
    section_resp = await auth_client.post(
        "/api/v1/sections",
        json={
            "report_id": test_report_id,
            "order_index": 0,
            "depth": 0,
            "i18n": [{"locale": "ru", "title": "Table Section", "slug": "table-section"}],
        },
    )
    assert section_resp.status_code == 201, section_resp.text
    section_id = section_resp.json()["section_id"]

    # Create a table block where one row is missing `cells` (this used to crash Jinja template).
    block_resp = await auth_client.post(
        "/api/v1/blocks",
        json={
            "report_id": test_report_id,
            "section_id": section_id,
            "type": "table",
            "variant": "default",
            "order_index": 0,
            "data_json": {
                "mode": "builder",
                "columns": [
                    {"key": "a", "type": "text", "align": "left"},
                    {"key": "b", "type": "text", "align": "left"},
                ],
                "rows": [
                    {},  # Missing `cells` on purpose
                    {"cells": {"a": "x", "b": "y"}},
                ],
            },
            "i18n": [{"locale": "ru", "fields_json": {"caption": "Test table"}}],
        },
    )
    assert block_resp.status_code == 201, block_resp.text

    preview = await auth_client.get(
        "/api/v1/preview/ru/sections/table-section",
        params={"report_id": test_report_id},
    )
    assert preview.status_code == 200, preview.text



