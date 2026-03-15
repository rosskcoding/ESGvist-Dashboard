"""
Chart block schemas.

Type: chart
Purpose: Data visualizations (bar, line, pie, etc.)

Spec reference: 04_Content_Model.md Section 4.2.4
"""

from typing import Literal
from uuid import UUID

from pydantic import Field

from .base import CAPTION_MAX_LENGTH, BlockDataSchema, BlockI18nSchema


class InlineChartData(BlockDataSchema):
    """Inline tabular data for charts (v2)."""

    columns: list[str] = Field(default_factory=list, max_length=50)
    rows: list[list[str | float | int | None]] = Field(default_factory=list, max_length=2000)


class ChartDataPoint(BlockDataSchema):
    """Single data point in a legacy chart series (v1)."""

    x: str | float | int
    y: float | int
    label: str | None = None


class ChartSeries(BlockDataSchema):
    """
    Legacy series (v1) and compatibility shape.

    Supports:
    - cartesian series: key + data[]
    - pie/donut series: key + value
    """

    key: str = Field(max_length=50, description="Series identifier")
    data: list[ChartDataPoint] | None = Field(default=None, max_length=500)
    value: float | int | None = Field(default=None, description="Legacy pie/donut value")
    type: Literal["bar", "line", "area"] | None = Field(default=None)
    axis: Literal["left", "right"] = "left"
    color: str | None = Field(default=None, max_length=20)
    stack_group: str | None = Field(default=None, max_length=50)


class XMapping(BlockDataSchema):
    """X-axis field mapping (v2)."""

    field: str = Field(max_length=100)
    type: Literal["category", "date", "number"] = "category"


class SeriesMapping(BlockDataSchema):
    """Series mapping for tabular sources (v2)."""

    name: str = Field(max_length=100)
    y_field: str = Field(max_length=100)
    axis: Literal["left", "right"] = "left"
    color: str | None = Field(default=None, max_length=20)
    stack_group: str | None = Field(default=None, max_length=50)


class ChartMapping(BlockDataSchema):
    """Mapping configuration for v2 tabular data sources."""

    x: XMapping
    series: list[SeriesMapping] = Field(default_factory=list, max_length=20)
    group_by: str | None = Field(default=None, max_length=100)


class ChartDataSource(BlockDataSchema):
    """Chart data source configuration."""

    type: Literal["inline", "asset_csv", "asset_json", "from_table"] = "inline"
    asset_id: UUID | None = None
    table_block_id: UUID | None = None
    json_path: str | None = Field(default=None, max_length=200)

    # v2 tabular inline data
    inline_data: InlineChartData | None = None

    # legacy v1
    inline_series: list[ChartSeries] | None = None


class ReferenceLine(BlockDataSchema):
    """Reference line (baseline/target)."""

    value: float
    label: str | None = Field(default=None, max_length=100)
    color: str | None = Field(default=None, max_length=20)
    style: Literal["solid", "dashed", "dotted"] = "dashed"


class ChartOptions(BlockDataSchema):
    """Chart rendering options."""

    show_legend: bool = True
    legend_position: Literal["top", "bottom", "left", "right"] = "bottom"
    show_grid: bool = True
    show_values: bool = False
    stacked: bool = False
    animate: bool = True
    responsive: bool = True

    baseline_line: ReferenceLine | None = None
    target_line: ReferenceLine | None = None


class AxisConfig(BlockDataSchema):
    """Axis configuration."""

    label: str | None = Field(default=None, max_length=100)
    min: float | None = Field(default=None)
    max: float | None = Field(default=None)
    step: float | None = Field(default=None)
    decimals: int | None = Field(default=None, ge=0, le=6)


class ChartBlockData(BlockDataSchema):
    """
    Chart block data schema.

    Contains chart configuration and numerical data.
    """

    chart_type: Literal[
        "bar",
        "line",
        "area",
        "stacked",
        "pie",
        "donut",
        "timeseries",
        "scenario",
    ] = Field(
        description="Chart type",
    )
    data_source: ChartDataSource = Field(
        default_factory=ChartDataSource,
        description="Data source configuration",
    )

    # v2 mapping (tabular sources)
    mapping: ChartMapping | None = None

    # legacy/compat: some older data stored series on top-level
    series: list[ChartSeries] = Field(
        default_factory=list,
        max_length=20,
        description="Legacy series/value list (compat)",
    )
    options: ChartOptions = Field(
        default_factory=ChartOptions,
        description="Chart rendering options",
    )
    x_axis: AxisConfig | None = None
    y_axis: AxisConfig | None = None


class AxisLabels(BlockI18nSchema):
    """Axis labels (localized)."""

    x_label: str | None = Field(default=None, max_length=100)
    y_label: str | None = Field(default=None, max_length=100)


class ChartBlockI18n(BlockI18nSchema):
    """
    Chart block i18n schema.

    Contains caption, accessibility text, and labels.
    """

    caption: str = Field(
        default="",
        max_length=CAPTION_MAX_LENGTH,
        description="Chart caption",
    )
    insight_text: str = Field(
        default="",
        max_length=2000,
        description="Text description of the chart (required for A11Y)",
    )
    unit: str | None = Field(
        default=None,
        max_length=50,
        description="Display unit: 'tCO2e', '%'",
    )
    source: str | None = Field(
        default=None,
        max_length=500,
        description="Data source attribution",
    )
    axis_labels: AxisLabels | None = Field(
        default=None,
        description="Axis labels",
    )
    legend_labels: dict[str, str] | None = Field(
        default=None,
        description="Series key → localized legend label",
    )

