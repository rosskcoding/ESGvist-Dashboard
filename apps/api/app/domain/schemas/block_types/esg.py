"""
ESG-specific block schemas.

Spec reference: 04_Content_Model.md Section 4.2.6
"""

from typing import Literal
from uuid import UUID

from pydantic import Field

from .base import BlockDataSchema, BlockI18nSchema


# --- Materiality Matrix ---


class MaterialityMatrixBlockData(BlockDataSchema):
    """Materiality matrix block data_json."""

    asset_id: UUID
    matrix_type: Literal["single", "double", "dynamic"] = "single"


class MaterialityMatrixBlockI18n(BlockI18nSchema):
    """Materiality matrix block fields_json."""

    caption: str = Field(default="", max_length=500)
    alt_text: str = Field(max_length=500)
    method_note: str | None = Field(default=None, max_length=2000)


# --- Risk / Opportunity / Impact ---


class ROIItemBlockData(BlockDataSchema):
    """Risk/Opportunity/Impact block data_json."""

    roi_type: Literal["risk", "opportunity", "impact"]
    time_horizon: Literal["short", "medium", "long"] | None = None
    severity: Literal["low", "medium", "high", "critical"] | None = None
    likelihood: Literal["unlikely", "possible", "likely", "certain"] | None = None


class ROIItemBlockI18n(BlockI18nSchema):
    """Risk/Opportunity/Impact block fields_json."""

    title: str = Field(max_length=200)
    description: str = Field(max_length=2000)
    mitigation: str | None = Field(default=None, max_length=2000)


# --- Policy ---


class PolicyBlockData(BlockDataSchema):
    """Policy block data_json."""

    document_asset_id: UUID | None = None
    policy_type: str | None = Field(default=None, max_length=100)


class PolicyBlockI18n(BlockI18nSchema):
    """Policy block fields_json."""

    policy_name: str = Field(max_length=300)
    summary: str = Field(max_length=2000)


# --- Target & Progress ---


class TargetProgressBlockData(BlockDataSchema):
    """Target and progress block data_json."""

    baseline_value: float | int
    baseline_year: int = Field(ge=2000, le=2100)
    current_value: float | int
    current_year: int = Field(ge=2000, le=2100)
    target_value: float | int
    target_year: int = Field(ge=2000, le=2100)
    unit: str = Field(max_length=50)
    show_progress_bar: bool = True


class TargetProgressBlockI18n(BlockI18nSchema):
    """Target and progress block fields_json."""

    title: str = Field(max_length=200)
    method_note: str | None = Field(default=None, max_length=1000)


# --- Case Study ---


class CaseStudyBlockData(BlockDataSchema):
    """Case study block data_json."""

    cover_image_asset_id: UUID | None = None


class CaseStudyBlockI18n(BlockI18nSchema):
    """Case study block fields_json."""

    title: str = Field(max_length=200)
    context: str = Field(max_length=3000)
    actions: str = Field(max_length=3000)
    results: str = Field(max_length=3000)


# --- Initiative Card ---


class InitiativeBlockData(BlockDataSchema):
    """Initiative block data_json."""

    icon_asset_id: UUID | None = None
    status: Literal["planned", "in_progress", "completed"] | None = None


class InitiativeBlockI18n(BlockI18nSchema):
    """Initiative block fields_json."""

    title: str = Field(max_length=200)
    goal: str = Field(max_length=1000)
    outcome: str | None = Field(default=None, max_length=1000)


# --- Stakeholder Engagement ---


class StakeholderGroup(BlockDataSchema):
    """Stakeholder group structure."""

    group_id: str = Field(max_length=50)


class StakeholderEngagementBlockData(BlockDataSchema):
    """Stakeholder engagement block data_json."""

    groups: list[StakeholderGroup] = Field(max_length=20)


class StakeholderGroupI18n(BlockI18nSchema):
    """Stakeholder group i18n."""

    name: str = Field(max_length=200)
    engagement_method: str = Field(max_length=500)
    topics: str = Field(max_length=1000)
    frequency: str = Field(max_length=200)


class StakeholderEngagementBlockI18n(BlockI18nSchema):
    """Stakeholder engagement block fields_json."""

    caption: str = Field(default="", max_length=500)
    groups: list[StakeholderGroupI18n] = Field(default_factory=list)

