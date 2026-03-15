/**
 * Design system types for Report styling and export configuration.
 * 
 * Mirrors backend schemas from apps/api/app/domain/schemas/design.py
 */

export type LayoutPreset = "sidebar" | "topnav" | "minimal";
export type ContainerWidth = "narrow" | "default" | "wide";
export type SectionSpacing = "compact" | "default" | "airy";
export type HeadingScale = "compact" | "default" | "large";
export type FontMode = "portable" | "web";
export type PackageMode = "portable" | "interactive";

export interface LayoutSettings {
  preset: LayoutPreset;
  container_width: ContainerWidth;
  section_spacing: SectionSpacing;
  show_toc: boolean;
}

export interface TypographySettings {
  font_family_body: string;
  font_family_heading: string;
  font_family_mono: string;
  base_font_size: number;
  heading_scale: HeadingScale;
}

export interface ReportDesignSettings {
  theme_slug: string;
  font_mode: FontMode;
  package_mode_default: PackageMode;
  layout: LayoutSettings;
  typography: TypographySettings;
  block_type_presets: Record<string, string>;
  block_overrides: Record<string, string>;
}

export interface ReportDesignUpdate {
  theme_slug?: string;
  font_mode?: FontMode;
  package_mode_default?: PackageMode;
  layout?: LayoutSettings;
  typography?: TypographySettings;
  block_type_presets?: Record<string, string>;
  block_overrides?: Record<string, string>;
}

export interface PresetInfo {
  name: string;
  description?: string;
}

export interface BlockTypePresets {
  block_type: string;
  presets: string[];
  default: string;
}

export interface PresetsResponse {
  presets: Record<string, string[]>;
  defaults: Record<string, string>;
}

export interface BlockPresetInfo {
  block_id: string;
  block_type: string;
  preset: string;
  source: "block_override" | "type_preset" | "system_default";
}

// Default values matching backend
export const DEFAULT_LAYOUT_SETTINGS: LayoutSettings = {
  preset: "sidebar",
  container_width: "default",
  section_spacing: "default",
  show_toc: true,
};

export const DEFAULT_TYPOGRAPHY_SETTINGS: TypographySettings = {
  font_family_body: "Inter",
  font_family_heading: "Inter",
  font_family_mono: "JetBrains Mono",
  base_font_size: 16,
  heading_scale: "default",
};

export const DEFAULT_DESIGN_SETTINGS: ReportDesignSettings = {
  theme_slug: "default",
  font_mode: "web",
  package_mode_default: "portable",
  layout: DEFAULT_LAYOUT_SETTINGS,
  typography: DEFAULT_TYPOGRAPHY_SETTINGS,
  block_type_presets: {
    text: "default",
    kpi_cards: "cards",
    table: "striped",
    chart: "default",
    quote: "accent",
    image: "default",
    downloads: "default",
    accordion: "default",
    timeline: "default",
  },
  block_overrides: {},
};




