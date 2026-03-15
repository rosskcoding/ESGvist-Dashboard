"""
Base classes for block type schemas.

Spec reference: 04_Content_Model.md Section 4.0
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BlockDataSchema(BaseModel):
    """
    Base class for block data_json schemas.

    data_json contains NON-localized structural data:
    - Numbers, values, configurations
    - Asset references (UUIDs)
    - Layout/structure settings

    IMPORTANT: Localized text MUST NOT be stored here.

    schema_version is used for backward-compatible migrations.
    """

    schema_version: int = Field(
        default=1,
        ge=1,
        description="Schema version for migration support",
    )

    model_config = ConfigDict(
        extra="allow",  # Allow unknown fields for forward compatibility
        str_strip_whitespace=True,
    )


class BlockI18nSchema(BaseModel):
    """
    Base class for block fields_json schemas (in BlockI18n).

    fields_json contains localized fields:
    - Text content (body_html, labels, captions)
    - Translated descriptions
    - Per-locale notes
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class EmptyDataSchema(BlockDataSchema):
    """Schema for blocks with no data_json (all content is localized)."""

    pass


# Common field constraints from SYSTEM_REGISTRY
TITLE_MAX_LENGTH = 240
CAPTION_MAX_LENGTH = 600
BODY_HTML_MAX_LENGTH = 50000
TAGS_MAX_COUNT = 50
TAG_MAX_LENGTH = 64

