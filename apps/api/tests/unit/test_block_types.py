"""
Unit tests for block type schemas and validation.

Tests block registry and type-specific validation.
Spec reference: 04_Content_Model.md
"""

import pytest

from app.domain.block_types import (
    BlockValidationError,
    get_block_type_info,
    get_data_schema,
    get_i18n_schema,
    requires_qa_flag,
    validate_block_data,
    validate_block_i18n,
)
from app.domain.block_types.chart import ChartBlockData, ChartBlockI18n
from app.domain.block_types.image import ImageBlockData, ImageBlockI18n
from app.domain.block_types.kpi import KPICardsBlockData, KPICardsBlockI18n
from app.domain.block_types.table import (
    TableAdvancedData,
    TableBuilderData,
    TableCustomData,
    TableImageData,
)
from app.domain.block_types.text import TextBlockData, TextBlockI18n
from app.domain.models.enums import BlockType


class TestBlockRegistry:
    """Tests for block type registry."""

    def test_get_text_block_info(self):
        """Text block type info is available."""
        info = get_block_type_info(BlockType.TEXT)
        assert info is not None
        assert info.type == BlockType.TEXT
        assert info.data_schema == TextBlockData
        assert info.i18n_schema == TextBlockI18n

    def test_get_kpi_block_info(self):
        """KPI Cards block type info is available."""
        info = get_block_type_info(BlockType.KPI_CARDS)
        assert info is not None
        assert info.type == BlockType.KPI_CARDS
        assert info.data_schema == KPICardsBlockData
        assert info.i18n_schema == KPICardsBlockI18n

    def test_get_chart_block_info(self):
        """Chart block type info is available."""
        info = get_block_type_info(BlockType.CHART)
        assert info is not None
        assert info.data_schema == ChartBlockData
        assert info.i18n_schema == ChartBlockI18n

    def test_get_image_block_info(self):
        """Image block type info is available."""
        info = get_block_type_info(BlockType.IMAGE)
        assert info is not None
        assert info.data_schema == ImageBlockData
        assert info.i18n_schema == ImageBlockI18n

    def test_get_unknown_type_returns_none(self):
        """Unknown block type returns None."""
        info = get_block_type_info("unknown_type")
        assert info is None

    def test_get_extended_type_info(self):
        """Extended types (variants) are accessible."""
        info = get_block_type_info("intro")
        assert info is not None
        assert info.description == "Intro/lead paragraph"


class TestTableModeSchemas:
    """Tests for table block mode-based schemas."""

    def test_table_builder_mode_schema(self):
        """Builder mode uses TableBuilderData."""
        data_json = {"mode": "builder", "columns": [], "rows": []}
        schema = get_data_schema(BlockType.TABLE, data_json)
        assert schema == TableBuilderData

    def test_table_advanced_mode_schema(self):
        """Advanced mode uses TableAdvancedData."""
        data_json = {"mode": "advanced"}
        schema = get_data_schema(BlockType.TABLE, data_json)
        assert schema == TableAdvancedData

    def test_table_custom_mode_schema(self):
        """Custom mode uses TableCustomData."""
        data_json = {"mode": "custom", "custom_html": "<table></table>"}
        schema = get_data_schema(BlockType.TABLE, data_json)
        assert schema == TableCustomData

    def test_table_image_mode_schema(self):
        """Image mode uses TableImageData."""
        data_json = {"mode": "image", "asset_id": "abc123"}
        schema = get_data_schema(BlockType.TABLE, data_json)
        assert schema == TableImageData

    def test_table_default_mode_is_builder(self):
        """Default table mode is builder."""
        data_json = {}
        schema = get_data_schema(BlockType.TABLE, data_json)
        assert schema == TableBuilderData


class TestBlockDataValidation:
    """Tests for block data validation."""

    def test_text_block_valid_empty_data(self):
        """Text block accepts empty data (all content in i18n)."""
        is_valid, errors = validate_block_data(BlockType.TEXT, {}, raise_on_error=False)
        assert is_valid
        assert errors == []

    def test_kpi_cards_valid_data(self):
        """KPI Cards accepts valid data."""
        data = {
            "items": [
                {"value": 42, "unit": "%", "trend": "up"},
                {"value": 1000, "unit": "k RUB"},
            ]
        }
        is_valid, errors = validate_block_data(BlockType.KPI_CARDS, data, raise_on_error=False)
        assert is_valid

    def test_kpi_cards_max_items(self):
        """KPI Cards rejects more than 12 items."""
        data = {
            "items": [{"value": i} for i in range(15)]
        }
        is_valid, errors = validate_block_data(BlockType.KPI_CARDS, data, raise_on_error=False)
        assert not is_valid
        assert any("items" in str(e) for e in errors)

    def test_image_block_requires_asset_id(self):
        """Image block requires asset_id."""
        data = {"layout": "full"}
        is_valid, errors = validate_block_data(BlockType.IMAGE, data, raise_on_error=False)
        assert not is_valid
        assert any("asset_id" in str(e) for e in errors)

    def test_image_block_valid_data(self):
        """Image block accepts valid data."""
        data = {"asset_id": "abc123", "layout": "half"}
        is_valid, errors = validate_block_data(BlockType.IMAGE, data, raise_on_error=False)
        assert is_valid

    def test_chart_block_valid_legacy_series_data(self):
        """Chart block accepts legacy v1 data.series[] shape (compat)."""
        data = {
            "chart_type": "bar",
            "series": [{"key": "revenue"}],
        }
        is_valid, errors = validate_block_data(BlockType.CHART, data, raise_on_error=False)
        assert is_valid

    @pytest.mark.parametrize(
        "chart_type",
        [
            "bar",
            "line",
            "area",
            "stacked",
            "pie",
            "donut",
            "timeseries",
            "scenario",
        ],
    )
    def test_chart_block_valid_chart_types(self, chart_type: str):
        """Chart block accepts all supported chart_type values (v2 inline + mapping)."""
        data = {
            "schema_version": 2,
            "chart_type": chart_type,
            "data_source": {
                "type": "inline",
                "inline_data": {
                    "columns": ["category", "value"],
                    "rows": [["A", 10], ["B", 20]],
                },
            },
            "mapping": {
                "x": {"field": "category", "type": "category"},
                "series": [{"name": "Value", "y_field": "value"}],
            },
            "options": {},
        }
        is_valid, errors = validate_block_data(BlockType.CHART, data, raise_on_error=False)
        assert is_valid, errors

    def test_chart_block_invalid_type(self):
        """Chart block rejects invalid chart_type."""
        data = {"chart_type": "invalid_type"}
        is_valid, errors = validate_block_data(BlockType.CHART, data, raise_on_error=False)
        assert not is_valid

    def test_table_builder_limits(self):
        """Table builder enforces row/column limits."""
        data = {
            "mode": "builder",
            "columns": [{"key": f"col{i}"} for i in range(15)],  # Max 12
            "rows": [],
        }
        is_valid, errors = validate_block_data(BlockType.TABLE, data, raise_on_error=False)
        assert not is_valid
        assert any("columns" in str(e) for e in errors)

    def test_validation_raises_on_error(self):
        """Validation raises BlockValidationError when raise_on_error=True."""
        data = {"chart_type": "invalid"}
        with pytest.raises(BlockValidationError):
            validate_block_data(BlockType.CHART, data, raise_on_error=True)


class TestBlockI18nValidation:
    """Tests for block i18n validation."""

    def test_text_block_i18n_valid(self):
        """Text block i18n accepts body_html."""
        fields = {"body_html": "<p>Hello world</p>"}
        is_valid, errors = validate_block_i18n(BlockType.TEXT, fields, raise_on_error=False)
        assert is_valid

    def test_kpi_cards_i18n_valid(self):
        """KPI Cards i18n accepts items with labels."""
        fields = {
            "items": [
                {"label": "Revenue", "note": "YoY growth"},
                {"label": "Profit"},
            ]
        }
        is_valid, errors = validate_block_i18n(BlockType.KPI_CARDS, fields, raise_on_error=False)
        assert is_valid

    def test_image_block_i18n_alt_text_optional(self):
        """Image block i18n accepts empty alt_text (default='')."""
        # alt_text is now optional with default="" for flexibility,
        # but A11Y warnings are raised via block_validator service
        fields = {"caption": "A nice image"}
        is_valid, errors = validate_block_i18n(BlockType.IMAGE, fields, raise_on_error=False)
        assert is_valid

    def test_chart_i18n_insight_text_optional(self):
        """Chart block i18n accepts empty insight_text (default='')."""
        # insight_text is now optional with default="" for flexibility,
        # but A11Y warnings are raised via block_validator service
        fields = {"caption": "Revenue chart"}
        is_valid, errors = validate_block_i18n(BlockType.CHART, fields, raise_on_error=False)
        assert is_valid

    def test_chart_i18n_valid(self):
        """Chart block i18n accepts valid data."""
        fields = {
            "caption": "Revenue by quarter",
            "insight_text": "Revenue grew 25% in Q4 compared to Q3",
        }
        is_valid, errors = validate_block_i18n(BlockType.CHART, fields, raise_on_error=False)
        assert is_valid


class TestQAFlagRequirement:
    """Tests for QA flag requirements."""

    def test_custom_block_requires_qa(self):
        """Custom block type requires QA flag."""
        assert requires_qa_flag(BlockType.CUSTOM)

    def test_text_block_no_qa(self):
        """Text block does not require QA flag."""
        assert not requires_qa_flag(BlockType.TEXT)

    def test_table_custom_mode_requires_qa(self):
        """Table in custom mode requires QA flag."""
        data_json = {"mode": "custom"}
        assert requires_qa_flag(BlockType.TABLE, data_json)

    def test_table_builder_mode_no_qa(self):
        """Table in builder mode does not require QA flag."""
        data_json = {"mode": "builder"}
        assert not requires_qa_flag(BlockType.TABLE, data_json)
