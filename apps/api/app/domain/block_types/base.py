"""
Base classes for block type schemas.

Each block type has two schemas:
- data_schema: stored in Block.data_json (non-localized structural data)
- i18n_schema: stored in BlockI18n.fields_json (localized text fields)

Spec reference: 04_Content_Model.md Section 4.0
"""

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field


class BlockDataSchema(BaseModel):
    """
    Base class for block data schemas (non-localized).

    Stored in Block.data_json.
    Contains: structural data, numbers, asset references, configuration.
    """

    model_config = ConfigDict(
        extra="ignore",  # Flexible: ignore unknown fields
        str_strip_whitespace=True,
    )


class BlockI18nSchema(BaseModel):
    """
    Base class for block i18n schemas (localized).

    Stored in BlockI18n.fields_json.
    Contains: all text content that needs translation.
    """

    model_config = ConfigDict(
        extra="ignore",  # Flexible: ignore unknown fields
        str_strip_whitespace=True,
    )


class FormatHint(BaseModel):
    """Format hint for numeric values."""

    type: str = Field(
        default="number",
        description="number | percent | currency | custom",
    )
    decimals: int = Field(default=0, ge=0, le=10)
    prefix: str = ""
    suffix: str = ""
    thousands_sep: bool = True


class AssetReference(BaseModel):
    """Reference to an asset."""

    asset_id: str = Field(description="UUID of the asset")
    purpose: str = Field(default="content", description="content | thumbnail | background")


# Common field constraints (from SYSTEM_REGISTRY)
TITLE_MAX_LENGTH = 240
CAPTION_MAX_LENGTH = 600
BODY_MAX_LENGTH = 50000
TAGS_MAX_COUNT = 50
TAG_MAX_LENGTH = 64

