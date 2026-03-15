"""
Unit tests for Renderer block type → template mapping.

Goal:
- Ensure every registered BlockType has an explicit template mapping (not generic)
- Ensure mapped template files exist on disk

This prevents silent regressions where new block types (or renamed templates)
fall back to generic rendering and then break preview/export unexpectedly.
"""

from pathlib import Path

from app.domain.block_types import get_block_type_info
from app.domain.models.enums import BlockType
from app.services.renderer import Renderer, TEMPLATES_DIR


def test_registered_block_types_have_templates_on_disk() -> None:
    renderer = Renderer()

    for bt in BlockType:
        # Only enforce mapping for registered types (future-proof if enum grows)
        if get_block_type_info(bt) is None:
            continue

        template_name = renderer._get_block_template(bt)
        assert template_name != "blocks/generic.html", f"{bt.value} should not fall back to generic template"

        template_path = Path(TEMPLATES_DIR) / template_name
        assert template_path.exists(), f"Missing template file for {bt.value}: {template_path}"



