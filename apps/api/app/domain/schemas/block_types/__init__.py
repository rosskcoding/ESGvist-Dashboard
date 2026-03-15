"""
Block Type Registry.

Maps BlockType enum to corresponding data and i18n schemas.
Provides runtime validation for block content.

Spec reference: 04_Content_Model.md Section 4.3
"""

from typing import Any

from pydantic import BaseModel

from app.domain.models.enums import BlockType

from .base import BlockDataSchema, BlockI18nSchema, EmptyDataSchema
from .chart import ChartBlockData, ChartBlockI18n
from .esg import (
    CaseStudyBlockData,
    CaseStudyBlockI18n,
    InitiativeBlockData,
    InitiativeBlockI18n,
    MaterialityMatrixBlockData,
    MaterialityMatrixBlockI18n,
    PolicyBlockData,
    PolicyBlockI18n,
    ROIItemBlockData,
    ROIItemBlockI18n,
    StakeholderEngagementBlockData,
    StakeholderEngagementBlockI18n,
    TargetProgressBlockData,
    TargetProgressBlockI18n,
)
from .image import ImageBlockData, ImageBlockI18n, InfographicBlockData, InfographicBlockI18n
from .kpi import (
    KPICardsBlockData,
    KPICardsBlockI18n,
    KPIGridBlockData,
    KPIGridBlockI18n,
    MetricContextBlockData,
    MetricContextBlockI18n,
)
from .misc import (
    AccordionBlockData,
    AccordionBlockI18n,
    CalloutBlockData,
    CalloutBlockI18n,
    CrossLinksBlockData,
    CrossLinksBlockI18n,
    CustomEmbedBlockData,
    CustomEmbedBlockI18n,
    DownloadsBlockData,
    DownloadsBlockI18n,
    QuoteBlockData,
    QuoteBlockI18n,
    ReferencesBlockData,
    ReferencesBlockI18n,
    TimelineBlockData,
    TimelineBlockI18n,
    TOCBlockData,
    TOCBlockI18n,
)
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


# Re-export all schemas
__all__ = [
    # Base
    "BlockDataSchema",
    "BlockI18nSchema",
    "EmptyDataSchema",
    # Text
    "TextBlockData",
    "TextBlockI18n",
    "IntroBlockData",
    "IntroBlockI18n",
    # KPI
    "KPICardsBlockData",
    "KPICardsBlockI18n",
    "KPIGridBlockData",
    "KPIGridBlockI18n",
    "MetricContextBlockData",
    "MetricContextBlockI18n",
    # Table
    "TableBuilderData",
    "TableBuilderI18n",
    "TableAdvancedData",
    "TableAdvancedI18n",
    "TableCustomData",
    "TableCustomI18n",
    "TableImageData",
    "TableImageI18n",
    # Image
    "ImageBlockData",
    "ImageBlockI18n",
    "InfographicBlockData",
    "InfographicBlockI18n",
    # Chart
    "ChartBlockData",
    "ChartBlockI18n",
    # Misc
    "QuoteBlockData",
    "QuoteBlockI18n",
    "CalloutBlockData",
    "CalloutBlockI18n",
    "DownloadsBlockData",
    "DownloadsBlockI18n",
    "ReferencesBlockData",
    "ReferencesBlockI18n",
    "CrossLinksBlockData",
    "CrossLinksBlockI18n",
    "AccordionBlockData",
    "AccordionBlockI18n",
    "TimelineBlockData",
    "TimelineBlockI18n",
    "TOCBlockData",
    "TOCBlockI18n",
    "CustomEmbedBlockData",
    "CustomEmbedBlockI18n",
    # Video
    "VideoBlockData",
    "VideoBlockI18n",
    # ESG
    "MaterialityMatrixBlockData",
    "MaterialityMatrixBlockI18n",
    "ROIItemBlockData",
    "ROIItemBlockI18n",
    "PolicyBlockData",
    "PolicyBlockI18n",
    "TargetProgressBlockData",
    "TargetProgressBlockI18n",
    "CaseStudyBlockData",
    "CaseStudyBlockI18n",
    "InitiativeBlockData",
    "InitiativeBlockI18n",
    "StakeholderEngagementBlockData",
    "StakeholderEngagementBlockI18n",
    # Registry
    "BLOCK_TYPE_REGISTRY",
    "get_data_schema",
    "get_i18n_schema",
    "validate_block_data",
    "validate_block_i18n",
    "BlockSchemaNotFoundError",
]


class BlockSchemaNotFoundError(Exception):
    """Raised when schema for block type is not found."""

    def __init__(self, block_type: str, schema_kind: str = "data"):
        self.block_type = block_type
        self.schema_kind = schema_kind
        super().__init__(f"No {schema_kind} schema found for block type: {block_type}")


class BlockTypeSchemas:
    """Container for block type schemas."""

    def __init__(
        self,
        data_schema: type[BlockDataSchema],
        i18n_schema: type[BlockI18nSchema],
        requires_qa: bool = False,
    ):
        self.data_schema = data_schema
        self.i18n_schema = i18n_schema
        self.requires_qa = requires_qa


# Block Type Registry
# Maps BlockType enum values to their schemas
BLOCK_TYPE_REGISTRY: dict[str, BlockTypeSchemas] = {
    # Text blocks
    BlockType.TEXT.value: BlockTypeSchemas(TextBlockData, TextBlockI18n),
    "intro": BlockTypeSchemas(IntroBlockData, IntroBlockI18n),
    # KPI blocks
    BlockType.KPI_CARDS.value: BlockTypeSchemas(KPICardsBlockData, KPICardsBlockI18n),
    "kpi_grid": BlockTypeSchemas(KPIGridBlockData, KPIGridBlockI18n),
    "metric_context": BlockTypeSchemas(MetricContextBlockData, MetricContextBlockI18n),
    # Table (uses builder by default, mode in data_json determines actual schema)
    BlockType.TABLE.value: BlockTypeSchemas(TableBuilderData, TableBuilderI18n),
    # Image
    BlockType.IMAGE.value: BlockTypeSchemas(ImageBlockData, ImageBlockI18n),
    "infographic": BlockTypeSchemas(InfographicBlockData, InfographicBlockI18n),
    # Chart
    BlockType.CHART.value: BlockTypeSchemas(ChartBlockData, ChartBlockI18n),
    # Quote & Callout
    BlockType.QUOTE.value: BlockTypeSchemas(QuoteBlockData, QuoteBlockI18n),
    "callout": BlockTypeSchemas(CalloutBlockData, CalloutBlockI18n),
    # Downloads & References
    BlockType.DOWNLOADS.value: BlockTypeSchemas(DownloadsBlockData, DownloadsBlockI18n),
    "references": BlockTypeSchemas(ReferencesBlockData, ReferencesBlockI18n),
    "cross_links": BlockTypeSchemas(CrossLinksBlockData, CrossLinksBlockI18n),
    # Interactive
    BlockType.ACCORDION.value: BlockTypeSchemas(AccordionBlockData, AccordionBlockI18n),
    BlockType.TIMELINE.value: BlockTypeSchemas(TimelineBlockData, TimelineBlockI18n),
    "toc": BlockTypeSchemas(TOCBlockData, TOCBlockI18n),
    # Video
    BlockType.VIDEO.value: BlockTypeSchemas(VideoBlockData, VideoBlockI18n),
    # Custom (always requires QA)
    BlockType.CUSTOM.value: BlockTypeSchemas(
        CustomEmbedBlockData, CustomEmbedBlockI18n, requires_qa=True
    ),
    # ESG-specific
    "materiality_matrix": BlockTypeSchemas(
        MaterialityMatrixBlockData, MaterialityMatrixBlockI18n
    ),
    "roi_item": BlockTypeSchemas(ROIItemBlockData, ROIItemBlockI18n),
    "policy": BlockTypeSchemas(PolicyBlockData, PolicyBlockI18n),
    "target_progress": BlockTypeSchemas(TargetProgressBlockData, TargetProgressBlockI18n),
    "case_study": BlockTypeSchemas(CaseStudyBlockData, CaseStudyBlockI18n),
    "initiative": BlockTypeSchemas(InitiativeBlockData, InitiativeBlockI18n),
    "stakeholder_engagement": BlockTypeSchemas(
        StakeholderEngagementBlockData, StakeholderEngagementBlockI18n
    ),
}


def get_data_schema(block_type: str | BlockType) -> type[BlockDataSchema]:
    """
    Get data_json schema for a block type.

    Args:
        block_type: Block type enum or string value

    Returns:
        Pydantic model class for data_json validation

    Raises:
        BlockSchemaNotFoundError: If block type not in registry
    """
    type_key = block_type.value if isinstance(block_type, BlockType) else block_type

    if type_key not in BLOCK_TYPE_REGISTRY:
        raise BlockSchemaNotFoundError(type_key, "data")

    return BLOCK_TYPE_REGISTRY[type_key].data_schema


def get_i18n_schema(block_type: str | BlockType) -> type[BlockI18nSchema]:
    """
    Get fields_json schema for a block type.

    Args:
        block_type: Block type enum or string value

    Returns:
        Pydantic model class for fields_json validation

    Raises:
        BlockSchemaNotFoundError: If block type not in registry
    """
    type_key = block_type.value if isinstance(block_type, BlockType) else block_type

    if type_key not in BLOCK_TYPE_REGISTRY:
        raise BlockSchemaNotFoundError(type_key, "i18n")

    return BLOCK_TYPE_REGISTRY[type_key].i18n_schema


def validate_block_data(block_type: str | BlockType, data_json: dict[str, Any]) -> BaseModel:
    """
    Validate data_json against type-specific schema.

    Args:
        block_type: Block type
        data_json: Data to validate

    Returns:
        Validated Pydantic model instance

    Raises:
        BlockSchemaNotFoundError: If block type not in registry
        ValidationError: If data doesn't match schema
    """
    schema = get_data_schema(block_type)

    # Special handling for table blocks with mode
    if (
        block_type == BlockType.TABLE or block_type == "table"
    ) and "mode" in data_json:
        mode = data_json.get("mode", "builder")
        if mode == "advanced":
            schema = TableAdvancedData
        elif mode == "custom":
            schema = TableCustomData
        elif mode == "image":
            schema = TableImageData
        # else: builder (default)

    return schema.model_validate(data_json)


def validate_block_i18n(block_type: str | BlockType, fields_json: dict[str, Any]) -> BaseModel:
    """
    Validate fields_json against type-specific i18n schema.

    Args:
        block_type: Block type
        fields_json: Localized fields to validate

    Returns:
        Validated Pydantic model instance

    Raises:
        BlockSchemaNotFoundError: If block type not in registry
        ValidationError: If data doesn't match schema
    """
    schema = get_i18n_schema(block_type)
    return schema.model_validate(fields_json)


def requires_qa_review(block_type: str | BlockType, data_json: dict[str, Any] | None = None) -> bool:
    """
    Check if a block type requires QA review.

    Args:
        block_type: Block type
        data_json: Optional data to check for custom content

    Returns:
        True if QA review is required
    """
    type_key = block_type.value if isinstance(block_type, BlockType) else block_type

    if type_key not in BLOCK_TYPE_REGISTRY:
        return True  # Unknown types always require QA

    if BLOCK_TYPE_REGISTRY[type_key].requires_qa:
        return True

    # Table with custom mode requires QA
    if type_key == "table" and data_json and data_json.get("mode") == "custom":
        return True

    return False

