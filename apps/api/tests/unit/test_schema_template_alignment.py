"""
Schema ↔ template alignment tests.

These tests ensure that for each supported block type:
- data_json validates against the registered Pydantic schema
- fields_json validates against the registered i18n schema
- server-side preview rendering (Jinja templates) does not crash

This catches regressions like:
- template expects legacy keys (quote_html) while schema uses new keys (quote_text)
- preview crashes on partially missing structures
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.block_types import validate_block_data, validate_block_i18n
from app.domain.models.block import Block, BlockI18n
from app.domain.models.enums import BlockType, BlockVariant, ContentStatus, Locale
from app.services.renderer import Renderer
from tests.fixtures.block_payloads_v2 import ALL_BLOCK_PAYLOADS, BlockPayload


@pytest.mark.parametrize("payload", ALL_BLOCK_PAYLOADS, ids=[p.name for p in ALL_BLOCK_PAYLOADS])
def test_schema_and_template_alignment(payload: BlockPayload) -> None:
    # 1) Validate against schemas (same path API uses on create/update)
    validate_block_data(payload.block_type, payload.data_json or {})
    validate_block_i18n(payload.block_type, payload.fields_json or {}, payload.data_json or {})

    # 2) Render via server-side renderer (same path Design preview uses)
    block = Block(
        report_id=uuid4(),
        section_id=uuid4(),
        type=BlockType(payload.block_type.value),
        variant=BlockVariant(payload.variant.value),
        order_index=0,
        data_json=payload.data_json or {},
        qa_flags_global=[],
        custom_override_enabled=False,
        owner_user_id=None,
        version=1,
    )
    i18n = BlockI18n(
        block_id=block.block_id,
        locale=Locale.RU,
        status=ContentStatus.DRAFT,
        qa_flags_by_locale=[],
        fields_json=payload.fields_json or {},
        custom_html_sanitized=payload.custom_html_sanitized,
        custom_css_validated=None,
    )
    block.i18n = [i18n]

    renderer = Renderer()
    html = renderer.render_block(
        block,
        Locale.RU,
        theme=None,
        assets_base_url="/assets",
        asset_url_map={},
    )

    assert f'data-block-type="{payload.block_type.value}"' in html

    # Chart captions should not be duplicated between HTML header and Vega SVG title in preview.
    if payload.block_type == BlockType.CHART:
        caption = (payload.fields_json or {}).get("caption", "")
        if caption:
            assert html.count(caption) == 1



