"""
Unit tests for chart resolution pipeline (app.services.chart_resolver).
"""

from app.services.chart_resolver import ResolvedChartData, resolve_chart_data


class TestChartResolver:
    def test_annotations_default_is_list(self):
        m = ResolvedChartData(chart_type="bar", series=[], x_values=[])
        assert isinstance(m.annotations, list)
        assert m.annotations == []

    def test_resolve_legacy_inline_series(self):
        resolved = resolve_chart_data(
            {
                "chart_type": "bar",
                "data_source": {
                    "type": "inline",
                    "inline_series": [
                        {"key": "revenue", "data": [{"x": "2024", "y": 10}]},
                    ],
                },
                "options": {"annotations": [{"type": "vline", "x": "2024"}]},
            }
        )
        assert resolved.chart_type == "bar"
        assert len(resolved.series) == 1
        assert resolved.series[0].key == "revenue"
        assert resolved.x_values == ["2024"]
        assert isinstance(resolved.annotations, list)





