"""
Block schemas.
"""

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from .common import BaseSchema, TimestampSchema
from .enums import BlockTypeEnum, BlockVariantEnum, ContentStatusEnum, LocaleEnum


class BlockI18nBase(BaseSchema):
    """Base block i18n fields."""

    status: ContentStatusEnum = ContentStatusEnum.DRAFT
    qa_flags_by_locale: list[str] = Field(default_factory=list)
    fields_json: dict = Field(default_factory=dict)
    custom_html_sanitized: str | None = None
    custom_css_validated: str | None = None


class BlockI18nCreate(BlockI18nBase):
    """Schema for creating block i18n."""

    locale: LocaleEnum


class BlockI18nUpdate(BaseSchema):
    """Schema for updating block i18n."""

    status: ContentStatusEnum | None = None
    qa_flags_by_locale: list[str] | None = None
    fields_json: dict | None = None
    custom_html_sanitized: str | None = None
    custom_css_validated: str | None = None


class BlockI18nDTO(BlockI18nBase):
    """Block i18n data transfer object."""

    locale: LocaleEnum
    last_approved_at_utc: datetime | None = None


class BlockBase(BaseSchema):
    """Base block fields."""

    type: BlockTypeEnum
    variant: BlockVariantEnum = BlockVariantEnum.DEFAULT
    order_index: int = Field(default=0, ge=0)
    data_json: dict = Field(
        default_factory=dict,
        description="NON-localized data only",
    )
    qa_flags_global: list[str] = Field(default_factory=list)
    custom_override_enabled: bool = False

    @field_validator("data_json")
    @classmethod
    def validate_no_inline_locale_maps(cls, v: dict) -> dict:
        """
        SYSTEM_REGISTRY.md Section F.3:
        - Forbidden: storing {ru,en,kk} maps inline in Block.data_json
        """

        def contains_locale_map(obj: object) -> bool:
            locales = {"ru", "en", "kk", "de", "fr", "ar", "es", "nl", "it"}
            if isinstance(obj, dict):
                keys = set(obj.keys())
                # Locale map if all keys are locale codes (any non-empty subset)
                if keys and keys.issubset(locales):
                    return True
                return any(contains_locale_map(vv) for vv in obj.values())
            if isinstance(obj, list):
                return any(contains_locale_map(item) for item in obj)
            return False

        if contains_locale_map(v):
            raise ValueError(
                "Forbidden inline locale map in Block.data_json. "
                "Store localized fields in BlockI18n.fields_json instead."
            )
        return v

    @model_validator(mode="after")
    def ensure_custom_flag(self) -> "BlockBase":
        """
        SYSTEM_REGISTRY.md invariant:
        If custom_override_enabled=true then CUSTOM ∈ qa_flags_global
        """
        if self.custom_override_enabled and "CUSTOM" not in self.qa_flags_global:
            self.qa_flags_global.append("CUSTOM")
        return self


class BlockCreate(BlockBase):
    """Schema for creating a block."""

    report_id: UUID
    section_id: UUID
    i18n: list[BlockI18nCreate] = Field(default_factory=list)


class BlockUpdate(BaseSchema):
    """Schema for updating a block."""

    variant: BlockVariantEnum | None = None
    order_index: int | None = Field(default=None, ge=0)
    data_json: dict | None = None
    qa_flags_global: list[str] | None = None
    custom_override_enabled: bool | None = None

    @field_validator("data_json")
    @classmethod
    def validate_no_inline_locale_maps(cls, v: dict | None) -> dict | None:
        """
        Enforce SYSTEM_REGISTRY.md Section F.3 for updates too.

        - Forbidden: storing {ru,en,kk} maps inline in Block.data_json
        """
        if v is None:
            return v
        return BlockBase.validate_no_inline_locale_maps(v)

    # For optimistic locking
    expected_version: int | None = Field(
        default=None,
        description="Expected version for optimistic locking",
    )

    @model_validator(mode="after")
    def validate_custom_flag_consistency(self) -> "BlockUpdate":
        """
        If update explicitly enables custom_override_enabled and qa_flags_global is provided,
        ensure it contains CUSTOM (SYSTEM_REGISTRY invariant).
        """
        if (
            self.custom_override_enabled is True
            and self.qa_flags_global is not None
            and "CUSTOM" not in self.qa_flags_global
        ):
            self.qa_flags_global.append("CUSTOM")
        return self


class BlockDTO(BlockBase, TimestampSchema):
    """Block data transfer object (response)."""

    block_id: UUID
    report_id: UUID
    section_id: UUID
    version: int
    owner_user_id: UUID | None = None
    i18n: list[BlockI18nDTO] = []


class BlockReorderRequest(BaseSchema):
    """Request to reorder blocks."""

    block_ids: list[UUID] = Field(
        min_length=1,
        description="Block IDs in new order",
    )
