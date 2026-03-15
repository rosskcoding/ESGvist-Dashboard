"""
Design settings schemas.

Spec reference: Design System -> Styled Blocks -> Multi-Page Static Export
"""

from typing import Literal

from pydantic import BaseModel, Field


class LayoutSettings(BaseModel):
    """Layout configuration for report rendering."""

    preset: Literal["sidebar", "topnav", "minimal"] = "sidebar"
    container_width: Literal["narrow", "default", "wide"] = "default"
    section_spacing: Literal["compact", "default", "airy"] = "default"
    show_toc: bool = True


class TypographySettings(BaseModel):
    """Typography configuration for report rendering."""

    font_family_body: str = "Inter"
    font_family_heading: str = "Inter"
    font_family_mono: str = "JetBrains Mono"
    base_font_size: int = Field(default=16, ge=14, le=20)
    heading_scale: Literal["compact", "default", "large"] = "default"


class ReportDesignSettings(BaseModel):
    """
    Full design settings structure stored in Report.design_json.

    This schema represents the complete design configuration including:
    - Theme selection
    - Font mode (portable vs web)
    - Default package mode for export
    - Layout settings
    - Typography settings
    - Block type presets (default style per block type)
    - Block overrides (per-block style exceptions)
    """

    theme_slug: str = "default"
    font_mode: Literal["portable", "web"] = "web"
    package_mode_default: Literal["portable", "interactive"] = "portable"
    layout: LayoutSettings = Field(default_factory=LayoutSettings)
    typography: TypographySettings = Field(default_factory=TypographySettings)
    block_type_presets: dict[str, str] = Field(
        default_factory=lambda: {
            "text": "default",
            "kpi_cards": "cards",
            "table": "striped",
            "chart": "default",
            "quote": "accent",
            "image": "default",
            "downloads": "default",
            "accordion": "default",
            "timeline": "default",
        }
    )
    block_overrides: dict[str, str] = Field(
        default_factory=dict,
        description="Per-block preset overrides: {block_uuid: preset_name}",
    )


class ReportDesignUpdate(BaseModel):
    """Partial update schema for design settings."""

    theme_slug: str | None = None
    font_mode: Literal["portable", "web"] | None = None
    package_mode_default: Literal["portable", "interactive"] | None = None
    layout: LayoutSettings | None = None
    typography: TypographySettings | None = None
    block_type_presets: dict[str, str] | None = None
    block_overrides: dict[str, str] | None = None


class PresetInfo(BaseModel):
    """Information about a single preset."""

    name: str
    description: str | None = None


class BlockTypePresets(BaseModel):
    """Available presets for a block type."""

    block_type: str
    presets: list[str]
    default: str


class PresetsResponse(BaseModel):
    """Response containing all available presets."""

    presets: dict[str, list[str]]
    defaults: dict[str, str]




