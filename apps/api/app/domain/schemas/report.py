"""
Report schemas.
"""

from uuid import UUID

from pydantic import Field, field_validator, model_validator

from .common import BaseSchema, TimestampSchema
from .enums import LocaleEnum


class ReportBase(BaseSchema):
    """Base report fields."""

    year: int = Field(ge=2000, le=2100)
    title: str = Field(min_length=1, max_length=200)
    slug: str = Field(max_length=100, pattern=r"^[a-z0-9-]+$")
    source_locale: LocaleEnum = LocaleEnum.EN
    default_locale: LocaleEnum = LocaleEnum.EN
    enabled_locales: list[str] = Field(default=["en"])
    release_locales: list[str] = Field(default=["en"])
    theme_slug: str = Field(default="default", max_length=50)

    @field_validator("enabled_locales", "release_locales")
    @classmethod
    def validate_locales(cls, v: list[str]) -> list[str]:
        valid_locales = {"ru", "en", "kk", "de", "fr", "ar", "es", "nl", "it"}
        invalid = set(v) - valid_locales
        if invalid:
            raise ValueError(f"Invalid locales: {invalid}")
        return v

    @model_validator(mode="after")
    def validate_locale_constraints(self) -> "ReportBase":
        """Validate SYSTEM_REGISTRY invariants."""
        # source_locale ∈ enabled_locales
        if self.source_locale.value not in self.enabled_locales:
            raise ValueError(f"source_locale '{self.source_locale}' must be in enabled_locales")
        # default_locale ∈ enabled_locales
        if self.default_locale.value not in self.enabled_locales:
            raise ValueError(f"default_locale '{self.default_locale}' must be in enabled_locales")
        # release_locales ⊆ enabled_locales
        invalid_release = set(self.release_locales) - set(self.enabled_locales)
        if invalid_release:
            raise ValueError(f"release_locales {invalid_release} must be subset of enabled_locales")
        return self


class ReportCreate(BaseSchema):
    """Schema for creating a report."""

    year: int = Field(ge=2000, le=2100)
    title: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=100, pattern=r"^[a-z0-9-]+$")
    source_locale: LocaleEnum = LocaleEnum.EN
    default_locale: LocaleEnum = LocaleEnum.EN
    enabled_locales: list[str] = Field(default=["en"])
    # If omitted, we default to enabled_locales in validate_locale_constraints().
    release_locales: list[str] = Field(default_factory=list)
    theme_slug: str = Field(default="default", max_length=50)

    @field_validator("enabled_locales", "release_locales")
    @classmethod
    def validate_locales(cls, v: list[str]) -> list[str]:
        valid_locales = {"ru", "en", "kk", "de", "fr", "ar", "es", "nl", "it"}
        invalid = set(v) - valid_locales
        if invalid:
            raise ValueError(f"Invalid locales: {invalid}")
        return v

    @model_validator(mode="after")
    def validate_locale_constraints(self) -> "ReportCreate":
        """Validate SYSTEM_REGISTRY invariants."""
        # Default release_locales to enabled_locales when omitted.
        if not self.release_locales:
            self.release_locales = list(self.enabled_locales)
        if self.source_locale.value not in self.enabled_locales:
            raise ValueError(f"source_locale '{self.source_locale}' must be in enabled_locales")
        if self.default_locale.value not in self.enabled_locales:
            raise ValueError(f"default_locale '{self.default_locale}' must be in enabled_locales")
        invalid_release = set(self.release_locales) - set(self.enabled_locales)
        if invalid_release:
            raise ValueError(f"release_locales {invalid_release} must be subset of enabled_locales")
        return self


class ReportUpdate(BaseSchema):
    """Schema for updating a report."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=100, pattern=r"^[a-z0-9-]+$")
    source_locale: LocaleEnum | None = None
    default_locale: LocaleEnum | None = None
    enabled_locales: list[str] | None = None
    release_locales: list[str] | None = None
    theme_slug: str | None = Field(default=None, max_length=50)


class ReportDTO(ReportBase, TimestampSchema):
    """Report data transfer object (response)."""

    report_id: UUID
    company_id: UUID

    # Aggregated stats (optional, populated by service)
    sections_count: int | None = None
    blocks_count: int | None = None
