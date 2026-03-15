"""
KPI block schemas.

Spec reference: 04_Content_Model.md Section 4.2.2
"""

from typing import Literal

from pydantic import Field

from .base import BlockDataSchema, BlockI18nSchema


# --- KPI Cards ---


class FormatHint(BlockDataSchema):
    """Formatting hint for KPI values."""

    type: Literal["number", "percent", "currency", "custom"] = "number"
    decimals: int = Field(default=0, ge=0, le=4)
    prefix: str = ""
    suffix: str = ""


class KPIItemData(BlockDataSchema):
    """Single KPI item data (non-localized)."""

    item_id: str | None = Field(default=None, max_length=50, description="Unique ID for drag/edit stability")

    # Core value
    value: float | int | str
    unit: str = ""

    # Period (required for reporting) - optional initially, will become required
    period: str | None = Field(
        default=None,
        max_length=50,
        description="Reporting period: '2024', 'Q3 2024', '2024-H1'",
    )

    # Trend and comparison
    trend: Literal["up", "down", "stable"] | None = None
    baseline_value: float | None = Field(
        default=None,
        description="Baseline value for comparison",
    )
    baseline_period: str | None = Field(
        default=None,
        max_length=50,
        description="Baseline period: '2022'",
    )
    target_value: float | None = Field(
        default=None,
        description="Target value",
    )
    status: Literal["on_track", "at_risk", "off_track"] | None = Field(
        default=None,
        description="Progress status towards target",
    )

    # Metadata
    value_kind: Literal["actual", "estimate", "restated"] | None = Field(
        default=None,
        description="Value type for reporting",
    )
    perimeter: str | None = Field(
        default=None,
        max_length=100,
        description="Reporting perimeter: 'Group', 'Company', 'Subsidiary'",
    )
    source: str | None = Field(
        default=None,
        max_length=500,
        description="Data source: 'SAP, extracted 2024-12-15'",
    )
    datapoint_id: str | None = Field(
        default=None,
        max_length=50,
        description="Link to datapoint registry (UUID)",
    )

    # Formatting
    format_hint: FormatHint | None = None


class KPICardsBlockData(BlockDataSchema):
    """
    KPI Cards block data_json schema.

    Contains numerical values and configuration.
    """

    items: list[KPIItemData] = Field(
        default_factory=list,
        max_length=12,
        description="KPI items (max 12)",
    )


class KPIItemI18n(BlockI18nSchema):
    """Single KPI item i18n (localized)."""

    label: str = Field(max_length=200)
    note: str | None = Field(default=None, max_length=500)


class KPICardsBlockI18n(BlockI18nSchema):
    """
    KPI Cards block fields_json schema.

    Contains localized labels and notes.
    """

    title: str | None = Field(
        default=None,
        max_length=200,
        description="Block title: 'Company in Numbers'",
    )
    template_id: str | None = Field(
        default=None,
        max_length=50,
        description="Template: 'company_in_numbers', 'climate', 'hse', 'people'",
    )
    items: list[KPIItemI18n] = Field(default_factory=list)


# --- KPI Grid ---


class KPIGridColumnDef(BlockDataSchema):
    """Column definition for KPI grid."""

    key: str = Field(max_length=50)
    type: Literal["text", "number", "percent"] = "text"
    width: int | None = None


class KPIGridRowData(BlockDataSchema):
    """Row data for KPI grid."""

    values: dict[str, float | int | str] = Field(default_factory=dict)


class KPIGridBlockData(BlockDataSchema):
    """KPI Grid block data_json."""

    columns: list[KPIGridColumnDef] = Field(max_length=12)
    rows: list[KPIGridRowData] = Field(max_length=50)


class KPIGridBlockI18n(BlockI18nSchema):
    """KPI Grid block fields_json."""

    column_labels: dict[str, str] = Field(
        default_factory=dict,
        description="Map of column key to localized label",
    )
    row_labels: dict[str, str] = Field(
        default_factory=dict,
        description="Map of row index to localized label",
    )


# --- Metric with Context ---


class MetricContextBlockData(BlockDataSchema):
    """Metric with context block data_json."""

    value: float | int | str
    unit: str = ""
    trend: Literal["up", "down", "stable"] | None = None


class MetricContextBlockI18n(BlockI18nSchema):
    """Metric with context block fields_json."""

    label: str = Field(max_length=200)
    context_text: str = Field(max_length=1000)

