"""
Block style presets registry (hardcoded for MVP).

Spec reference: Design System -> Styled Blocks
Presets define visual styles for blocks, separate from block variants.
"""

from typing import Any

__all__ = [
    "PRESETS",
    "DEFAULT_PRESET_BY_TYPE",
    "PRESET_DESCRIPTIONS",
    "get_preset_for_block",
    "validate_preset",
    "get_presets_for_type",
]


# Available presets per block type
PRESETS: dict[str, list[str]] = {
    "text": ["default", "lead", "compact", "highlight"],
    "kpi_cards": ["cards", "inline", "big_number", "minimal", "grid"],
    "table": ["striped", "compact", "bordered", "minimal", "cards"],
    "chart": ["default", "compact", "large", "minimal"],
    "quote": ["accent", "subtle", "plain", "large"],
    "image": ["default", "full_width", "captioned", "gallery"],
    "downloads": ["default", "compact", "cards", "list"],
    "accordion": ["default", "bordered", "minimal"],
    "timeline": ["default", "compact", "detailed", "minimal"],
    "custom": ["default"],
}

# Default preset for each block type
DEFAULT_PRESET_BY_TYPE: dict[str, str] = {
    "text": "default",
    "kpi_cards": "cards",
    "table": "striped",
    "chart": "default",
    "quote": "accent",
    "image": "default",
    "downloads": "default",
    "accordion": "default",
    "timeline": "default",
    "custom": "default",
}

# Human-readable descriptions for presets
PRESET_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "text": {
        "default": "Standard text block",
        "lead": "Larger text for introductions",
        "compact": "Reduced spacing for dense content",
        "highlight": "Highlighted background",
    },
    "kpi_cards": {
        "cards": "KPI values displayed as cards",
        "inline": "KPI values in a horizontal row",
        "big_number": "Large prominent numbers",
        "minimal": "Clean minimal styling",
        "grid": "Grid layout for multiple KPIs",
    },
    "table": {
        "striped": "Alternating row colors",
        "compact": "Reduced cell padding",
        "bordered": "Full borders on all cells",
        "minimal": "Clean minimal borders",
        "cards": "Rows as cards (mobile-friendly)",
    },
    "chart": {
        "default": "Standard chart size",
        "compact": "Reduced height chart",
        "large": "Full-width large chart",
        "minimal": "Clean minimal styling",
    },
    "quote": {
        "accent": "Colored accent border",
        "subtle": "Light background styling",
        "plain": "Simple quotation marks",
        "large": "Large centered quote",
    },
    "image": {
        "default": "Standard image with optional caption",
        "full_width": "Edge-to-edge image",
        "captioned": "Image with prominent caption",
        "gallery": "Multiple images in gallery layout",
    },
    "downloads": {
        "default": "List of download links",
        "compact": "Compact link list",
        "cards": "Files as download cards",
        "list": "Simple bulleted list",
    },
    "accordion": {
        "default": "Expandable sections",
        "bordered": "Bordered accordion items",
        "minimal": "Clean minimal styling",
    },
    "timeline": {
        "default": "Vertical timeline with markers",
        "compact": "Compact timeline layout",
        "detailed": "Timeline with full details",
        "minimal": "Simple timeline styling",
    },
    "custom": {
        "default": "Custom HTML block",
    },
}


def get_preset_for_block(
    block_type: str,
    block_id: str,
    design_json: dict[str, Any],
) -> str:
    """
    Resolve the preset to use for a block.

    Priority order:
    1. Block-specific override in design_json.block_overrides[block_id]
    2. Type default in design_json.block_type_presets[block_type]
    3. System default from DEFAULT_PRESET_BY_TYPE

    Args:
        block_type: The block type (e.g., "kpi_cards", "table")
        block_id: The block UUID as string
        design_json: The report's design_json settings

    Returns:
        The preset name to use for this block
    """
    # Check block-specific override
    overrides = design_json.get("block_overrides", {})
    if block_id in overrides:
        preset = overrides[block_id]
        if validate_preset(block_type, preset):
            return preset

    # Check type default from design settings
    type_presets = design_json.get("block_type_presets", {})
    if block_type in type_presets:
        preset = type_presets[block_type]
        if validate_preset(block_type, preset):
            return preset

    # Fall back to system default
    return DEFAULT_PRESET_BY_TYPE.get(block_type, "default")


def validate_preset(block_type: str, preset: str) -> bool:
    """
    Check if a preset is valid for a given block type.

    Args:
        block_type: The block type
        preset: The preset name to validate

    Returns:
        True if the preset is valid for this block type
    """
    available = PRESETS.get(block_type, ["default"])
    return preset in available


def get_presets_for_type(block_type: str) -> list[str]:
    """
    Get all available presets for a block type.

    Args:
        block_type: The block type

    Returns:
        List of available preset names
    """
    return PRESETS.get(block_type, ["default"])


def get_preset_description(block_type: str, preset: str) -> str | None:
    """
    Get the human-readable description for a preset.

    Args:
        block_type: The block type
        preset: The preset name

    Returns:
        Description string or None if not found
    """
    type_descriptions = PRESET_DESCRIPTIONS.get(block_type, {})
    return type_descriptions.get(preset)




