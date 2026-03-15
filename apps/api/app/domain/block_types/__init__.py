"""
Block Type Registry and Validation.

Central registry for block type schemas and validation.

Spec reference: 04_Content_Model.md
"""

from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.domain.models.enums import BlockType

from .base import BlockDataSchema, BlockI18nSchema
from .chart import ChartBlockData, ChartBlockI18n
from .custom import (
    AccordionBlockData,
    AccordionBlockI18n,
    CustomBlockData,
    CustomBlockI18n,
    TimelineBlockData,
    TimelineBlockI18n,
)
from .downloads import (
    CrossLinksBlockData,
    CrossLinksBlockI18n,
    DownloadsBlockData,
    DownloadsBlockI18n,
    ReferencesBlockData,
    ReferencesBlockI18n,
)
from .image import GalleryBlockData, GalleryBlockI18n, ImageBlockData, ImageBlockI18n
from .kpi import KPICardsBlockData, KPICardsBlockI18n, KPIGridBlockData, KPIGridBlockI18n
from .quote import CalloutBlockData, CalloutBlockI18n, QuoteBlockData, QuoteBlockI18n
from .table import (
    TableAdvancedData,
    TableAdvancedI18n,
    TableBuilderData,
    TableBuilderI18n,
    TableCustomData,
    TableCustomI18n,
    TableImageData,
    TableImageI18n,
)
from .text import IntroBlockData, IntroBlockI18n, TextBlockData, TextBlockI18n
from .video import VideoBlockData, VideoBlockI18n

__all__ = [
    # Registry functions
    "get_data_schema",
    "get_i18n_schema",
    "validate_block_data",
    "validate_block_i18n",
    "get_block_type_info",
    "BlockTypeInfo",
    # Re-exports for convenience
    "BlockDataSchema",
    "BlockI18nSchema",
]


class BlockTypeInfo:
    """Information about a block type."""

    def __init__(
        self,
        type_: BlockType,
        data_schema: type[BlockDataSchema],
        i18n_schema: type[BlockI18nSchema],
        *,
        requires_qa: bool = False,
        has_variants: bool = False,
        description: str = "",
    ):
        self.type = type_
        self.data_schema = data_schema
        self.i18n_schema = i18n_schema
        self.requires_qa = requires_qa
        self.has_variants = has_variants
        self.description = description


# === Block Type Registry ===

_BLOCK_TYPE_REGISTRY: dict[BlockType, BlockTypeInfo] = {
    # Text blocks
    BlockType.TEXT: BlockTypeInfo(
        BlockType.TEXT,
        TextBlockData,
        TextBlockI18n,
        description="Rich text content",
    ),
    # KPI blocks
    BlockType.KPI_CARDS: BlockTypeInfo(
        BlockType.KPI_CARDS,
        KPICardsBlockData,
        KPICardsBlockI18n,
        description="KPI indicator cards",
    ),
    # Table block (uses mode-based sub-schemas)
    BlockType.TABLE: BlockTypeInfo(
        BlockType.TABLE,
        TableBuilderData,  # Default mode
        TableBuilderI18n,
        has_variants=True,
        description="Data table (4 modes)",
    ),
    # Chart block
    BlockType.CHART: BlockTypeInfo(
        BlockType.CHART,
        ChartBlockData,
        ChartBlockI18n,
        description="Data visualization",
    ),
    # Image block
    BlockType.IMAGE: BlockTypeInfo(
        BlockType.IMAGE,
        ImageBlockData,
        ImageBlockI18n,
        description="Image or infographic",
    ),
    # Quote block
    BlockType.QUOTE: BlockTypeInfo(
        BlockType.QUOTE,
        QuoteBlockData,
        QuoteBlockI18n,
        description="Blockquote with attribution",
    ),
    # Downloads block
    BlockType.DOWNLOADS: BlockTypeInfo(
        BlockType.DOWNLOADS,
        DownloadsBlockData,
        DownloadsBlockI18n,
        description="Downloadable files",
    ),
    # Accordion block
    BlockType.ACCORDION: BlockTypeInfo(
        BlockType.ACCORDION,
        AccordionBlockData,
        AccordionBlockI18n,
        description="Expandable sections",
    ),
    # Timeline block
    BlockType.TIMELINE: BlockTypeInfo(
        BlockType.TIMELINE,
        TimelineBlockData,
        TimelineBlockI18n,
        description="Chronological events",
    ),
    # Video block
    BlockType.VIDEO: BlockTypeInfo(
        BlockType.VIDEO,
        VideoBlockData,
        VideoBlockI18n,
        description="Video embed (YouTube/Vimeo/self-hosted)",
    ),
    # Custom block
    BlockType.CUSTOM: BlockTypeInfo(
        BlockType.CUSTOM,
        CustomBlockData,
        CustomBlockI18n,
        requires_qa=True,
        description="Custom HTML embed",
    ),
}

# Extended types (not in base enum, but used in specs)
_EXTENDED_TYPES: dict[str, BlockTypeInfo] = {
    "intro": BlockTypeInfo(
        BlockType.TEXT,  # Variant of text
        IntroBlockData,
        IntroBlockI18n,
        description="Intro/lead paragraph",
    ),
    "callout": BlockTypeInfo(
        BlockType.TEXT,  # Variant of text
        CalloutBlockData,
        CalloutBlockI18n,
        description="Highlighted callout box",
    ),
    "kpi_grid": BlockTypeInfo(
        BlockType.KPI_CARDS,  # Variant
        KPIGridBlockData,
        KPIGridBlockI18n,
        description="KPI grid table",
    ),
    "gallery": BlockTypeInfo(
        BlockType.IMAGE,  # Variant
        GalleryBlockData,
        GalleryBlockI18n,
        description="Image gallery",
    ),
    "references": BlockTypeInfo(
        BlockType.DOWNLOADS,  # Related
        ReferencesBlockData,
        ReferencesBlockI18n,
        description="Footnotes and references",
    ),
    "cross_links": BlockTypeInfo(
        BlockType.DOWNLOADS,  # Related
        CrossLinksBlockData,
        CrossLinksBlockI18n,
        description="Internal cross-links",
    ),
}

# Table mode → schema mapping
_TABLE_MODE_SCHEMAS: dict[str, tuple[type[BlockDataSchema], type[BlockI18nSchema]]] = {
    "builder": (TableBuilderData, TableBuilderI18n),
    "advanced": (TableAdvancedData, TableAdvancedI18n),
    "custom": (TableCustomData, TableCustomI18n),
    "image": (TableImageData, TableImageI18n),
}


def get_block_type_info(block_type: BlockType | str) -> BlockTypeInfo | None:
    """Get type info for a block type."""
    if isinstance(block_type, str):
        # Check extended types first
        if block_type in _EXTENDED_TYPES:
            return _EXTENDED_TYPES[block_type]
        try:
            block_type = BlockType(block_type)
        except ValueError:
            return None

    return _BLOCK_TYPE_REGISTRY.get(block_type)


def get_data_schema(
    block_type: BlockType | str,
    data_json: dict | None = None,
) -> type[BlockDataSchema]:
    """
    Get the data schema for a block type.

    For table blocks, uses 'mode' field in data_json to determine schema.
    """
    if isinstance(block_type, str):
        if block_type in _EXTENDED_TYPES:
            return _EXTENDED_TYPES[block_type].data_schema
        block_type = BlockType(block_type)

    # Special handling for table blocks (mode-based)
    if block_type == BlockType.TABLE and data_json:
        mode = data_json.get("mode", "builder")
        if mode in _TABLE_MODE_SCHEMAS:
            return _TABLE_MODE_SCHEMAS[mode][0]

    info = _BLOCK_TYPE_REGISTRY.get(block_type)
    if not info:
        raise ValueError(f"Unknown block type: {block_type}")

    return info.data_schema


def get_i18n_schema(
    block_type: BlockType | str,
    data_json: dict | None = None,
) -> type[BlockI18nSchema]:
    """
    Get the i18n schema for a block type.

    For table blocks, uses 'mode' field in data_json to determine schema.
    """
    if isinstance(block_type, str):
        if block_type in _EXTENDED_TYPES:
            return _EXTENDED_TYPES[block_type].i18n_schema
        block_type = BlockType(block_type)

    # Special handling for table blocks (mode-based)
    if block_type == BlockType.TABLE and data_json:
        mode = data_json.get("mode", "builder")
        if mode in _TABLE_MODE_SCHEMAS:
            return _TABLE_MODE_SCHEMAS[mode][1]

    info = _BLOCK_TYPE_REGISTRY.get(block_type)
    if not info:
        raise ValueError(f"Unknown block type: {block_type}")

    return info.i18n_schema


class BlockValidationError(Exception):
    """Block validation error with structured details."""

    def __init__(self, message: str, errors: list[dict] | None = None):
        super().__init__(message)
        self.message = message
        self.errors = errors or []


def validate_block_data(
    block_type: BlockType | str,
    data_json: dict,
    *,
    raise_on_error: bool = True,
) -> tuple[bool, list[dict]]:
    """
    Validate data_json against the type-specific schema.

    Args:
        block_type: The block type
        data_json: The data to validate
        raise_on_error: If True, raises BlockValidationError on failure

    Returns:
        Tuple of (is_valid, errors)
    """
    try:
        schema = get_data_schema(block_type, data_json)
        schema.model_validate(data_json)
        return True, []
    except ValidationError as e:
        errors = [
            {
                "loc": list(err["loc"]),
                "msg": err["msg"],
                "type": err["type"],
            }
            for err in e.errors()
        ]
        if raise_on_error:
            raise BlockValidationError(
                f"Invalid data_json for block type {block_type}",
                errors=errors,
            )
        return False, errors
    except ValueError as e:
        error = {"loc": [], "msg": str(e), "type": "value_error"}
        if raise_on_error:
            raise BlockValidationError(str(e), errors=[error])
        return False, [error]


def validate_block_i18n(
    block_type: BlockType | str,
    fields_json: dict,
    data_json: dict | None = None,
    *,
    raise_on_error: bool = True,
) -> tuple[bool, list[dict]]:
    """
    Validate fields_json against the type-specific i18n schema.

    Args:
        block_type: The block type
        fields_json: The i18n fields to validate
        data_json: Optional data_json (for table mode detection)
        raise_on_error: If True, raises BlockValidationError on failure

    Returns:
        Tuple of (is_valid, errors)
    """
    try:
        schema = get_i18n_schema(block_type, data_json)
        schema.model_validate(fields_json)
        return True, []
    except ValidationError as e:
        errors = [
            {
                "loc": list(err["loc"]),
                "msg": err["msg"],
                "type": err["type"],
            }
            for err in e.errors()
        ]
        if raise_on_error:
            raise BlockValidationError(
                f"Invalid fields_json for block type {block_type}",
                errors=errors,
            )
        return False, errors
    except ValueError as e:
        error = {"loc": [], "msg": str(e), "type": "value_error"}
        if raise_on_error:
            raise BlockValidationError(str(e), errors=[error])
        return False, [error]


def requires_qa_flag(block_type: BlockType | str, data_json: dict | None = None) -> bool:
    """
    Check if a block type requires QA flag.

    Custom blocks and table custom mode always require QA.
    """
    if isinstance(block_type, str):
        if block_type in _EXTENDED_TYPES:
            return _EXTENDED_TYPES[block_type].requires_qa
        try:
            block_type = BlockType(block_type)
        except ValueError:
            return False

    # Table custom mode
    if block_type == BlockType.TABLE and data_json:
        if data_json.get("mode") == "custom":
            return True

    info = _BLOCK_TYPE_REGISTRY.get(block_type)
    return info.requires_qa if info else False

