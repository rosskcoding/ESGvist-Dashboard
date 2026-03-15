"""
Section schemas.
"""

from uuid import UUID

from pydantic import Field

from .common import BaseSchema, TimestampSchema
from .enums import LocaleEnum


class SectionI18nBase(BaseSchema):
    """Base section i18n fields."""

    title: str = Field(min_length=1, max_length=240)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    summary: str | None = None


class SectionI18nCreate(SectionI18nBase):
    """Schema for creating section i18n."""

    locale: LocaleEnum


class SectionI18nUpdate(BaseSchema):
    """Schema for updating section i18n."""

    title: str | None = Field(default=None, min_length=1, max_length=240)
    slug: str | None = Field(default=None, min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    summary: str | None = None


class SectionI18nDTO(SectionI18nBase):
    """Section i18n data transfer object."""

    locale: LocaleEnum


class SectionBase(BaseSchema):
    """Base section fields."""

    order_index: int = Field(default=0, ge=0)
    parent_section_id: UUID | None = None

    # Structure fields for table of contents
    depth: int = Field(default=0, ge=0, le=3, description="Nesting level 0-3 (max 4 levels)")
    label_prefix: str | None = Field(default=None, max_length=20, description="Prefix before title: '1.', '09', 'A.'")
    label_suffix: str | None = Field(default=None, max_length=50, description="Suffix after title: '(p. 5)'")


class SectionCreate(SectionBase):
    """Schema for creating a section."""

    report_id: UUID
    i18n: list[SectionI18nCreate] = Field(
        min_length=1,
        description="At least one locale required",
    )


class SectionUpdate(BaseSchema):
    """Schema for updating a section."""

    order_index: int | None = Field(default=None, ge=0)
    parent_section_id: UUID | None = None

    # Structure fields
    depth: int | None = Field(default=None, ge=0, le=3)
    label_prefix: str | None = Field(default=None, max_length=20)
    label_suffix: str | None = Field(default=None, max_length=50)


class SectionDTO(SectionBase, TimestampSchema):
    """Section data transfer object (response)."""

    section_id: UUID
    report_id: UUID
    i18n: list[SectionI18nDTO] = []

    # Aggregated
    blocks_count: int | None = None


# Bulk reorder schemas
class SectionReorderItem(BaseSchema):
    """Single item in bulk reorder request."""

    section_id: UUID
    order_index: int = Field(ge=0)
    parent_section_id: UUID | None = None
    depth: int = Field(ge=0, le=3)


class BulkReorderRequest(BaseSchema):
    """Request for bulk section reorder."""

    report_id: UUID
    items: list[SectionReorderItem] = Field(
        min_length=1,
        description="List of sections with their new positions",
    )


