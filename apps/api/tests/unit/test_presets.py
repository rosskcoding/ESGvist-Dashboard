"""
Unit tests for block style presets registry.

Tests preset resolution, validation, and registry structure.
"""

import pytest

from app.domain.presets import (
    DEFAULT_PRESET_BY_TYPE,
    PRESET_DESCRIPTIONS,
    PRESETS,
    get_preset_description,
    get_preset_for_block,
    get_presets_for_type,
    validate_preset,
)


class TestPresetRegistry:
    """Tests for PRESETS registry structure."""

    def test_all_block_types_have_presets(self):
        """All block types should have at least one preset."""
        expected_types = [
            "text", "kpi_cards", "table", "chart", "quote",
            "image", "downloads", "accordion", "timeline", "custom"
        ]
        for block_type in expected_types:
            assert block_type in PRESETS
            assert len(PRESETS[block_type]) >= 1

    def test_all_block_types_have_default_preset(self):
        """All block types should have a default preset defined."""
        for block_type in PRESETS:
            assert block_type in DEFAULT_PRESET_BY_TYPE
            default = DEFAULT_PRESET_BY_TYPE[block_type]
            assert default in PRESETS[block_type]

    def test_all_presets_have_descriptions(self):
        """All presets should have human-readable descriptions."""
        for block_type, presets in PRESETS.items():
            assert block_type in PRESET_DESCRIPTIONS
            for preset in presets:
                assert preset in PRESET_DESCRIPTIONS[block_type], \
                    f"Missing description for {block_type}.{preset}"

    def test_kpi_presets(self):
        """KPI cards should have expected presets."""
        assert "cards" in PRESETS["kpi_cards"]
        assert "inline" in PRESETS["kpi_cards"]
        assert "big_number" in PRESETS["kpi_cards"]

    def test_table_presets(self):
        """Table should have expected presets."""
        assert "striped" in PRESETS["table"]
        assert "compact" in PRESETS["table"]
        assert "bordered" in PRESETS["table"]

    def test_quote_presets(self):
        """Quote should have expected presets."""
        assert "accent" in PRESETS["quote"]
        assert "subtle" in PRESETS["quote"]
        assert "plain" in PRESETS["quote"]


class TestValidatePreset:
    """Tests for validate_preset() function."""

    def test_valid_preset_for_type(self):
        """Valid preset for block type should return True."""
        assert validate_preset("kpi_cards", "cards") is True
        assert validate_preset("table", "striped") is True
        assert validate_preset("quote", "accent") is True

    def test_invalid_preset_for_type(self):
        """Invalid preset for block type should return False."""
        assert validate_preset("kpi_cards", "striped") is False  # striped is for table
        assert validate_preset("table", "accent") is False  # accent is for quote
        assert validate_preset("text", "big_number") is False

    def test_nonexistent_preset(self):
        """Nonexistent preset should return False."""
        assert validate_preset("text", "nonexistent") is False
        assert validate_preset("kpi_cards", "fancy") is False

    def test_unknown_block_type(self):
        """Unknown block type should fall back to ['default']."""
        # Unknown type only has "default" preset
        assert validate_preset("unknown_type", "default") is True
        assert validate_preset("unknown_type", "cards") is False

    def test_default_always_valid(self):
        """'default' preset should be valid for types that have it."""
        for block_type in ["text", "chart", "image", "downloads", "accordion", "timeline", "custom"]:
            assert validate_preset(block_type, "default") is True


class TestGetPresetForBlock:
    """Tests for get_preset_for_block() function."""

    def test_block_override_highest_priority(self):
        """Block-specific override should take precedence."""
        design_json = {
            "block_type_presets": {"kpi_cards": "inline"},
            "block_overrides": {"block-123": "big_number"},
        }
        result = get_preset_for_block("kpi_cards", "block-123", design_json)
        assert result == "big_number"

    def test_type_preset_second_priority(self):
        """Type preset should be used if no block override."""
        design_json = {
            "block_type_presets": {"kpi_cards": "inline"},
            "block_overrides": {},
        }
        result = get_preset_for_block("kpi_cards", "block-123", design_json)
        assert result == "inline"

    def test_system_default_fallback(self):
        """System default should be used if no overrides."""
        design_json = {}
        result = get_preset_for_block("kpi_cards", "block-123", design_json)
        assert result == "cards"  # DEFAULT_PRESET_BY_TYPE["kpi_cards"]

    def test_empty_design_json(self):
        """Empty design_json should use system defaults."""
        result = get_preset_for_block("table", "block-456", {})
        assert result == "striped"  # DEFAULT_PRESET_BY_TYPE["table"]

    def test_invalid_override_falls_back(self):
        """Invalid block override should fall back to type preset."""
        design_json = {
            "block_type_presets": {"kpi_cards": "inline"},
            "block_overrides": {"block-123": "invalid_preset"},
        }
        result = get_preset_for_block("kpi_cards", "block-123", design_json)
        assert result == "inline"  # Falls back to type preset

    def test_invalid_type_preset_falls_back(self):
        """Invalid type preset should fall back to system default."""
        design_json = {
            "block_type_presets": {"kpi_cards": "invalid_preset"},
            "block_overrides": {},
        }
        result = get_preset_for_block("kpi_cards", "block-123", design_json)
        assert result == "cards"  # Falls back to system default

    def test_different_block_types(self):
        """Different block types should resolve to their own defaults."""
        design_json = {}
        assert get_preset_for_block("text", "b1", design_json) == "default"
        assert get_preset_for_block("kpi_cards", "b2", design_json) == "cards"
        assert get_preset_for_block("table", "b3", design_json) == "striped"
        assert get_preset_for_block("quote", "b4", design_json) == "accent"

    def test_multiple_overrides(self):
        """Multiple block overrides should not interfere."""
        design_json = {
            "block_overrides": {
                "block-1": "inline",
                "block-2": "big_number",
            },
        }
        assert get_preset_for_block("kpi_cards", "block-1", design_json) == "inline"
        assert get_preset_for_block("kpi_cards", "block-2", design_json) == "big_number"
        # block-3 not in overrides, uses system default
        assert get_preset_for_block("kpi_cards", "block-3", design_json) == "cards"


class TestGetPresetsForType:
    """Tests for get_presets_for_type() function."""

    def test_known_block_type(self):
        """Known block type should return its presets."""
        presets = get_presets_for_type("kpi_cards")
        assert "cards" in presets
        assert "inline" in presets
        assert len(presets) >= 3

    def test_unknown_block_type(self):
        """Unknown block type should return ['default']."""
        presets = get_presets_for_type("unknown_type")
        assert presets == ["default"]

    def test_returns_list(self):
        """Should return a list."""
        for block_type in PRESETS:
            presets = get_presets_for_type(block_type)
            assert isinstance(presets, list)
            assert len(presets) >= 1


class TestGetPresetDescription:
    """Tests for get_preset_description() function."""

    def test_valid_preset_description(self):
        """Valid preset should return description."""
        desc = get_preset_description("kpi_cards", "cards")
        assert desc is not None
        assert "card" in desc.lower()

    def test_invalid_preset_returns_none(self):
        """Invalid preset should return None."""
        desc = get_preset_description("kpi_cards", "nonexistent")
        assert desc is None

    def test_unknown_block_type_returns_none(self):
        """Unknown block type should return None."""
        desc = get_preset_description("unknown_type", "default")
        assert desc is None

    def test_all_descriptions_are_strings(self):
        """All descriptions should be non-empty strings."""
        for block_type, presets in PRESETS.items():
            for preset in presets:
                desc = get_preset_description(block_type, preset)
                assert desc is not None, f"Missing description for {block_type}.{preset}"
                assert isinstance(desc, str)
                assert len(desc) > 0




