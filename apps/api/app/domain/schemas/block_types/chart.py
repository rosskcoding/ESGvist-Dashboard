"""
Chart block schemas.

Spec reference: 04_Content_Model.md Section 4.2.4
"""

from typing import Literal
from uuid import UUID

from pydantic import Field

from .base import BlockDataSchema, BlockI18nSchema


# --- Legacy v1 structures (kept for backward compat) ---


class ChartDataPoint(BlockDataSchema):
    """Single data point in a chart series (legacy v1)."""

    x: str | float | int
    y: float | int
    label: str | None = None


class ChartSeries(BlockDataSchema):
    """Chart data series (legacy v1)."""

    key: str = Field(max_length=50)
    data: list[ChartDataPoint] = Field(max_length=500)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    type: Literal["line", "bar", "area"] | None = None  # For combo charts


# --- v2 Mapping-based structures ---


class XMapping(BlockDataSchema):
    """X-axis field mapping."""

    field: str = Field(max_length=100, description="Column/field name for X axis")
    type: Literal["category", "date", "number"] = Field(
        default="category",
        description="X axis data type",
    )


class SeriesMapping(BlockDataSchema):
    """Series configuration for mapping-based charts."""

    name: str = Field(max_length=100, description="Series display name")
    y_field: str = Field(max_length=100, description="Column/field name for Y values")
    axis: Literal["left", "right"] = Field(default="left", description="Y axis to use")
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    stack_group: str | None = Field(default=None, max_length=50, description="Stack group ID")
    chart_type: Literal["line", "bar", "area"] | None = Field(
        default=None,
        description="Override chart type for combo charts",
    )


class ChartMapping(BlockDataSchema):
    """Mapping configuration for tabular data sources."""

    x: XMapping
    series: list[SeriesMapping] = Field(max_length=20)
    group_by: str | None = Field(
        default=None,
        max_length=100,
        description="Field for grouping/clustering",
    )


class InlineChartData(BlockDataSchema):
    """Inline tabular data for charts (v2)."""

    columns: list[str] = Field(max_length=50, description="Column names")
    rows: list[list[str | float | int | None]] = Field(
        max_length=2000,
        description="Data rows",
    )


# --- Data Source ---


class ChartDataSource(BlockDataSchema):
    """Data source for chart."""

    type: Literal["inline", "asset_csv", "asset_json", "from_table"] = "inline"
    asset_id: UUID | None = Field(default=None, description="Asset ID for CSV/JSON files")
    table_block_id: UUID | None = Field(default=None, description="Block ID for from_table mode")
    json_path: str | None = Field(default=None, max_length=200, description="JSON path for asset_json")

    # v2: Tabular inline data (used with mapping)
    inline_data: InlineChartData | None = Field(default=None, description="Inline tabular data")

    # Legacy v1: Pre-built series (kept for backward compat)
    inline_series: list[ChartSeries] | None = Field(default=None, description="Legacy: pre-built series")


# --- Chart Options ---


class ReferenceLine(BlockDataSchema):
    """Reference line (baseline/target)."""

    value: float
    label: str | None = Field(default=None, max_length=100)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    style: Literal["solid", "dashed", "dotted"] = "dashed"


class ChartAnnotation(BlockDataSchema):
    """Chart annotation (e.g., vertical line with label)."""

    type: Literal["vline", "hline", "point", "area"] = "vline"
    x: str | float | int | None = None
    y: float | None = None
    x_end: str | float | int | None = None
    y_end: float | None = None
    label: str | None = Field(default=None, max_length=200)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")


class ChartOptions(BlockDataSchema):
    """Chart display options."""

    show_legend: bool = True
    legend_position: Literal["top", "bottom", "left", "right"] = "bottom"
    show_grid: bool = True
    show_values: bool = False
    stacked: bool = False
    animate: bool = True
    responsive: bool = True

    # Reference lines
    baseline_line: ReferenceLine | None = Field(default=None, description="Baseline/comparison line")
    target_line: ReferenceLine | None = Field(default=None, description="Target/goal line")

    # Annotations
    annotations: list[ChartAnnotation] = Field(
        default_factory=list,
        max_length=20,
        description="Chart annotations (vertical lines, labels, etc.)",
    )


# --- Axis Configuration ---


class AxisConfig(BlockDataSchema):
    """Axis configuration."""

    label: str | None = Field(default=None, max_length=100, description="Axis label")
    min: float | None = None
    max: float | None = None
    step: float | None = None
    format: str | None = Field(default=None, description="Number format: ',.0f', '%', etc.")
    decimals: int | None = Field(default=None, ge=0, le=6)


class YAxisConfig(BlockDataSchema):
    """Y-axis configuration (supports dual axis)."""

    left: AxisConfig | None = Field(default=None, description="Left Y axis")
    right: AxisConfig | None = Field(default=None, description="Right Y axis (for dual-axis charts)")


# --- Main Chart Block ---


class ChartBlockData(BlockDataSchema):
    """
    Chart block data_json schema.

    Universal chart block supporting multiple chart types.
    Supports both legacy inline_series (v1) and mapping-based data (v2).
    """

    chart_type: Literal["bar", "line", "pie", "donut", "stacked", "area", "timeseries", "scenario"]
    data_source: ChartDataSource

    # v2: Mapping configuration (for tabular data sources)
    mapping: ChartMapping | None = Field(
        default=None,
        description="Column-to-series mapping for tabular data",
    )

    # Chart configuration
    options: ChartOptions = Field(default_factory=ChartOptions)
    x_axis: AxisConfig | None = None
    y_axes: YAxisConfig | None = Field(default=None, description="Y axis configuration (dual axis support)")

    # Legacy single y_axis (kept for backward compat)
    y_axis: AxisConfig | None = None

    # Metadata
    source_ref: str | None = Field(default=None, max_length=500)


class AxisLabels(BlockI18nSchema):
    """Localized axis labels."""

    x_label: str = Field(default="", max_length=100)
    y_label: str = Field(default="", max_length=100)
    y_label_right: str | None = Field(default=None, max_length=100, description="Right Y axis label")


class ChartBlockI18n(BlockI18nSchema):
    """
    Chart block fields_json schema.

    Contains localized labels and accessibility text.
    """

    caption: str = Field(default="", max_length=500)
    insight_text: str = Field(
        default="",
        max_length=2000,
        description="Required for A11Y - textual description of the chart",
    )
    unit: str | None = Field(default=None, max_length=50, description="Display unit: 'tCO2e', '%'")
    source: str | None = Field(default=None, max_length=500, description="Data source attribution")
    axis_labels: AxisLabels | None = None
    legend_labels: dict[str, str] = Field(
        default_factory=dict,
        description="Map of series key to localized label",
    )
    notes: str | None = Field(default=None, max_length=2000)

