"""
KPI block schemas.

Type: kpi_cards
Purpose: Display key performance indicators as cards

Spec reference: 04_Content_Model.md Section 4.2.2
"""

from typing import Literal

from pydantic import Field

from .base import BlockDataSchema, BlockI18nSchema, FormatHint


class KPIItem(BlockDataSchema):
    """Single KPI item data (non-localized)."""

    item_id: str | None = Field(
        default=None,
        max_length=100,
        description="Unique item identifier",
    )
    value: float | int | str = Field(default="", description="The KPI value")
    unit: str = Field(default="", max_length=50, description="Unit of measurement")
    period: str = Field(default="", max_length=50, description="Period (e.g., '2024', 'Q3 2024')")
    trend: Literal["up", "down", "stable"] | None = Field(
        default=None,
        description="Trend indicator",
    )
    source: str | None = Field(
        default=None,
        max_length=200,
        description="Data source reference",
    )
    format_hint: FormatHint | None = Field(
        default=None,
        description="Formatting hints for display",
    )


class KPIItemI18n(BlockI18nSchema):
    """Single KPI item i18n (localized)."""

    label: str = Field(default="", max_length=200, description="KPI label/name")
    note: str | None = Field(
        default=None,
        max_length=500,
        description="Additional note or explanation",
    )


class KPICardsBlockData(BlockDataSchema):
    """
    KPI Cards block data schema.

    Contains numerical values, units, and trends.
    """

    items: list[KPIItem] = Field(
        default_factory=list,
        max_length=12,
        description="KPI items (max 12)",
    )


class KPICardsBlockI18n(BlockI18nSchema):
    """
    KPI Cards block i18n schema.

    Contains labels and notes for each KPI.
    """

    title: str = Field(
        default="",
        max_length=200,
        description="Section title (e.g., 'Company in Numbers')",
    )
    template_id: str | None = Field(
        default=None,
        max_length=50,
        description="Optional template identifier",
    )
    items: list[KPIItemI18n] = Field(
        default_factory=list,
        max_length=12,
        description="KPI item labels (must match data items count)",
    )


# KPI Grid variant
class KPIGridColumn(BlockDataSchema):
    """KPI Grid column definition."""

    key: str = Field(max_length=50)
    type: Literal["text", "number", "percent"] = "text"


class KPIGridBlockData(BlockDataSchema):
    """KPI Grid block data schema."""

    columns: list[KPIGridColumn] = Field(
        default_factory=list,
        max_length=10,
    )
    rows: list[dict] = Field(
        default_factory=list,
        max_length=20,
        description="Row data (numerical values)",
    )


class KPIGridBlockI18n(BlockI18nSchema):
    """KPI Grid block i18n schema."""

    column_labels: dict[str, str] = Field(
        default_factory=dict,
        description="Column key → localized label",
    )
    row_labels: list[str] = Field(
        default_factory=list,
        description="Row labels",
    )

