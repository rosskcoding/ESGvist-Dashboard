"""
Theme schemas for API.

Spec reference: 05_Theming_Styling.md
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ThemeBase(BaseModel):
    """Base theme fields."""

    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    tokens_json: dict[str, str] = Field(default_factory=dict)
    is_active: bool = True


class ThemeCreate(ThemeBase):
    """Schema for creating a theme."""

    slug: str = Field(
        min_length=2,
        max_length=50,
        pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$",
        description="URL-safe slug (lowercase, hyphens allowed)",
    )
    is_default: bool = False

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if "--" in v:
            raise ValueError("Slug cannot contain consecutive hyphens")
        return v.lower()


class ThemeUpdate(BaseModel):
    """Schema for updating a theme."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    tokens_json: dict[str, str] | None = None
    is_active: bool | None = None
    is_default: bool | None = None


class ThemeDTO(ThemeBase):
    """Theme data transfer object."""

    theme_id: UUID
    slug: str
    is_default: bool
    created_at_utc: datetime
    updated_at_utc: datetime

    model_config = ConfigDict(from_attributes=True)


class ThemeListDTO(BaseModel):
    """Simplified theme for list views."""

    theme_id: UUID
    slug: str
    name: str
    is_default: bool
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class ThemeCSSResponse(BaseModel):
    """Response containing generated CSS."""

    slug: str
    css: str




