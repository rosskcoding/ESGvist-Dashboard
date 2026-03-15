"""
Unit tests for Vega-Lite converter (app.services.vega_converter).

Tests chart data conversion to Vega-Lite spec for export.
Note: Tests for actual rendering (SVG/PNG) require vl-convert to be installed.
"""

import pytest

from app.services.vega_converter import (
    chart_data_to_vega_lite,
    _transform_inline_data,
    _build_cartesian_spec,
    _build_pie_spec,
    get_export_formats,
    CHART_COLORS,
)


class TestTransformInlineData:
    """Test inline data transformation."""

    def test_empty_data(self):
        """Empty columns/rows returns empty list."""
        assert _transform_inline_data([], []) == ([], {})
        assert _transform_inline_data(["a", "b"], []) == ([], {})
        assert _transform_inline_data([], [[1, 2]]) == ([], {})

    def test_simple_transform(self):
        """Basic transformation works."""
        columns = ["year", "value"]
        rows = [
            ["2022", 100],
            ["2023", 120],
            ["2024", 150],
        ]

        values, field_mapping = _transform_inline_data(columns, rows)

        assert len(values) == 3
        assert values[0] == {"year": "2022", "value": 100}
        assert values[1] == {"year": "2023", "value": 120}
        assert values[2] == {"year": "2024", "value": 150}
        # For ASCII-safe columns, mapping should preserve names
        assert field_mapping == {"year": "year", "value": "value"}

    def test_handles_short_rows(self):
        """Rows shorter than columns handled gracefully."""
        columns = ["a", "b", "c"]
        rows = [
            [1, 2],  # Missing "c"
        ]

        values, field_mapping = _transform_inline_data(columns, rows)

        assert len(values) == 1
        assert values[0] == {"a": 1, "b": 2}
        assert field_mapping["a"] == "a"
        assert field_mapping["b"] == "b"
        assert field_mapping["c"] == "c"


class TestChartDataToVegaLite:
    """Test full conversion to Vega-Lite spec."""

    def test_bar_chart(self):
        """Bar chart conversion."""
        data_json = {
            "chart_type": "bar",
            "data_source": {
                "type": "inline",
                "inline_data": {
                    "columns": ["category", "value"],
                    "rows": [
                        ["A", 10],
                        ["B", 20],
                        ["C", 30],
                    ],
                },
            },
            "mapping": {
                "x": {"field": "category", "type": "category"},
                "series": [{"name": "Value", "y_field": "value"}],
            },
            "options": {},
        }
        fields_json = {"caption": "Test Chart"}

        spec = chart_data_to_vega_lite(data_json, fields_json)

        assert spec["$schema"] == "https://vega.github.io/schema/vega-lite/v5.json"
        assert spec["mark"]["type"] == "bar"
        assert spec["encoding"]["x"]["field"] == "category"
        assert spec["encoding"]["y"]["field"] == "value"
        assert spec["title"]["text"] == "Test Chart"

    def test_line_chart(self):
        """Line chart conversion."""
        data_json = {
            "chart_type": "line",
            "data_source": {
                "type": "inline",
                "inline_data": {
                    "columns": ["year", "revenue"],
                    "rows": [
                        ["2022", 100],
                        ["2023", 120],
                    ],
                },
            },
            "mapping": {
                "x": {"field": "year", "type": "category"},
                "series": [{"name": "Revenue", "y_field": "revenue"}],
            },
            "options": {},
        }
        fields_json = {}

        spec = chart_data_to_vega_lite(data_json, fields_json)

        assert spec["mark"]["type"] == "line"

    def test_area_chart(self):
        """Area chart conversion."""
        data_json = {
            "chart_type": "area",
            "data_source": {
                "type": "inline",
                "inline_data": {
                    "columns": ["quarter", "production"],
                    "rows": [
                        ["Q1 2024", 6.3],
                        ["Q2 2024", 6.7],
                    ],
                },
            },
            "mapping": {
                "x": {"field": "quarter", "type": "category"},
                "series": [{"name": "Production", "y_field": "production"}],
            },
            "options": {},
        }
        spec = chart_data_to_vega_lite(data_json, {})
        assert spec["mark"]["type"] == "area"

    def test_stacked_chart(self):
        """Stacked chart has stack encoding."""
        data_json = {
            "chart_type": "stacked",
            "data_source": {
                "type": "inline",
                "inline_data": {
                    "columns": ["year", "a", "b"],
                    "rows": [["2022", 10, 20]],
                },
            },
            "mapping": {
                "x": {"field": "year", "type": "category"},
                "series": [
                    {"name": "A", "y_field": "a"},
                    {"name": "B", "y_field": "b"},
                ],
            },
            "options": {"stacked": True},
        }
        fields_json = {}

        spec = chart_data_to_vega_lite(data_json, fields_json)

        assert spec["encoding"]["y"]["stack"] is True

    def test_pie_chart(self):
        """Pie chart conversion."""
        data_json = {
            "chart_type": "pie",
            "data_source": {
                "type": "inline",
                "inline_data": {
                    "columns": ["segment", "value"],
                    "rows": [
                        ["A", 30],
                        ["B", 50],
                        ["C", 20],
                    ],
                },
            },
            "mapping": {
                "x": {"field": "segment", "type": "category"},
                "series": [{"name": "Value", "y_field": "value"}],
            },
            "options": {},
        }
        fields_json = {}

        spec = chart_data_to_vega_lite(data_json, fields_json)

        assert spec["mark"]["type"] == "arc"
        assert "theta" in spec["encoding"]

    def test_donut_chart(self):
        """Donut chart has inner radius."""
        data_json = {
            "chart_type": "donut",
            "data_source": {
                "type": "inline",
                "inline_data": {
                    "columns": ["segment", "value"],
                    "rows": [["A", 100]],
                },
            },
            "mapping": {
                "x": {"field": "segment", "type": "category"},
                "series": [{"name": "Value", "y_field": "value"}],
            },
            "options": {},
        }
        fields_json = {}

        spec = chart_data_to_vega_lite(data_json, fields_json)

        assert spec["mark"]["type"] == "arc"
        assert spec["mark"]["innerRadius"] == 50

    def test_timeseries_chart(self):
        """Timeseries chart uses line mark and temporal X."""
        data_json = {
            "chart_type": "timeseries",
            "data_source": {
                "type": "inline",
                "inline_data": {
                    "columns": ["date", "price"],
                    "rows": [
                        ["2024-01-01", 21500],
                        ["2024-02-01", 22100],
                    ],
                },
            },
            "mapping": {
                "x": {"field": "date", "type": "date"},
                "series": [{"name": "Price", "y_field": "price"}],
            },
            "options": {},
        }
        spec = chart_data_to_vega_lite(data_json, {})
        assert spec["mark"]["type"] == "line"
        assert spec["encoding"]["x"]["type"] == "temporal"

    def test_scenario_chart_multiple_series(self):
        """Scenario chart supports multiple series (fold transform) and uses line mark."""
        data_json = {
            "chart_type": "scenario",
            "data_source": {
                "type": "inline",
                "inline_data": {
                    "columns": ["year", "base", "optimistic", "conservative"],
                    "rows": [
                        ["2024", 25.0, 25.0, 25.0],
                        ["2025", 26.5, 28.0, 25.2],
                    ],
                },
            },
            "mapping": {
                "x": {"field": "year", "type": "category"},
                "series": [
                    {"name": "Base", "y_field": "base"},
                    {"name": "Optimistic", "y_field": "optimistic"},
                    {"name": "Conservative", "y_field": "conservative"},
                ],
            },
            "options": {},
        }
        spec = chart_data_to_vega_lite(data_json, {})
        assert spec["mark"]["type"] == "line"
        assert spec["transform"][0]["fold"] == ["base", "optimistic", "conservative"]

    def test_multiple_series(self):
        """Multiple series uses fold transform."""
        data_json = {
            "chart_type": "bar",
            "data_source": {
                "type": "inline",
                "inline_data": {
                    "columns": ["year", "revenue", "profit"],
                    "rows": [
                        ["2022", 100, 20],
                        ["2023", 120, 25],
                    ],
                },
            },
            "mapping": {
                "x": {"field": "year", "type": "category"},
                "series": [
                    {"name": "Revenue", "y_field": "revenue"},
                    {"name": "Profit", "y_field": "profit"},
                ],
            },
            "options": {},
        }
        fields_json = {}

        spec = chart_data_to_vega_lite(data_json, fields_json)

        # Should have fold transform for multiple series
        assert "transform" in spec
        assert spec["transform"][0]["fold"] == ["revenue", "profit"]
        assert "color" in spec["encoding"]

    def test_custom_dimensions(self):
        """Custom width/height applied."""
        data_json = {
            "chart_type": "bar",
            "data_source": {
                "type": "inline",
                "inline_data": {
                    "columns": ["x", "y"],
                    "rows": [["A", 10]],
                },
            },
            "mapping": {
                "x": {"field": "x", "type": "category"},
                "series": [{"name": "Y", "y_field": "y"}],
            },
            "options": {},
        }

        spec = chart_data_to_vega_lite(data_json, {}, width=800, height=500)

        assert spec["width"] == 800
        assert spec["height"] == 500

    def test_x_type_mapping(self):
        """X axis type maps correctly."""
        # Test date type
        data_json = {
            "chart_type": "line",
            "data_source": {
                "type": "inline",
                "inline_data": {
                    "columns": ["date", "value"],
                    "rows": [["2022-01-01", 100]],
                },
            },
            "mapping": {
                "x": {"field": "date", "type": "date"},
                "series": [{"name": "Value", "y_field": "value"}],
            },
            "options": {},
        }

        spec = chart_data_to_vega_lite(data_json, {})

        assert spec["encoding"]["x"]["type"] == "temporal"


class TestBuildCartesianSpec:
    """Test cartesian chart spec building."""

    def test_single_series(self):
        """Single series uses simple encoding."""
        values = [{"x": "A", "y": 10}]
        mapping = {
            "x": {"field": "x", "type": "category"},
            "series": [{"name": "Y", "y_field": "y", "color": "#FF0000"}],
        }

        spec = _build_cartesian_spec(values, mapping, {}, "bar", "bar", 600, 400, {}, {})

        assert "transform" not in spec  # No transform for single series
        assert spec["mark"]["color"] == "#FF0000"


class TestBuildPieSpec:
    """Test pie chart spec building."""

    def test_pie_encoding(self):
        """Pie chart has theta encoding."""
        values = [{"cat": "A", "val": 30}, {"cat": "B", "val": 70}]
        mapping = {
            "x": {"field": "cat", "type": "category"},
            "series": [{"y_field": "val"}],
        }

        spec = _build_pie_spec(values, mapping, {}, {"type": "arc"}, 600, 400, {}, {})

        assert spec["encoding"]["theta"]["field"] == "val"
        assert spec["encoding"]["color"]["field"] == "cat"


class TestGetExportFormats:
    """Test export format listing."""

    def test_formats_available(self):
        """All expected formats available."""
        formats = get_export_formats()

        format_ids = [f["id"] for f in formats]
        assert "svg" in format_ids
        assert "png" in format_ids
        assert "pdf" in format_ids

    def test_format_structure(self):
        """Format entries have required fields."""
        formats = get_export_formats()

        for fmt in formats:
            assert "id" in fmt
            assert "name" in fmt
            assert "mime" in fmt
            assert "extension" in fmt


class TestChartColors:
    """Test color palette."""

    def test_colors_defined(self):
        """Color palette has enough colors."""
        assert len(CHART_COLORS) >= 8

    def test_colors_are_hex(self):
        """All colors are valid hex."""
        for color in CHART_COLORS:
            assert color.startswith("#")
            assert len(color) == 7



