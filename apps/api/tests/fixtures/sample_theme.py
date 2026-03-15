"""
Sample theme fixtures for testing.

Theme definitions used to validate CSS variables and theming.
"""

# ============================================================================
# THEME: Corporate Blue (Default)
# ============================================================================

THEME_CORPORATE_BLUE = {
    "slug": "corporate-blue",
    "name": {"en": "Corporate Blue"},
    "tokens": {
        # --- Colors ---
        "color-primary": "#1e40af",
        "color-primary-light": "#3b82f6",
        "color-primary-dark": "#1e3a8a",
        "color-secondary": "#64748b",
        "color-secondary-light": "#94a3b8",
        "color-secondary-dark": "#475569",
        "color-accent": "#f59e0b",
        "color-accent-light": "#fbbf24",
        "color-accent-dark": "#d97706",
        "color-success": "#22c55e",
        "color-warning": "#f59e0b",
        "color-error": "#ef4444",
        "color-info": "#3b82f6",
        "color-background": "#ffffff",
        "color-surface": "#f8fafc",
        "color-surface-elevated": "#ffffff",
        "color-text-primary": "#0f172a",
        "color-text-secondary": "#475569",
        "color-text-muted": "#94a3b8",
        "color-text-inverse": "#ffffff",
        "color-border": "#e2e8f0",
        "color-border-light": "#f1f5f9",
        "color-divider": "#e2e8f0",
        # --- Typography ---
        "font-family-heading": "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
        "font-family-body": "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
        "font-family-mono": "'JetBrains Mono', 'Fira Code', monospace",
        "font-size-xs": "0.75rem",
        "font-size-sm": "0.875rem",
        "font-size-base": "1rem",
        "font-size-lg": "1.125rem",
        "font-size-xl": "1.25rem",
        "font-size-2xl": "1.5rem",
        "font-size-3xl": "1.875rem",
        "font-size-4xl": "2.25rem",
        "font-weight-normal": "400",
        "font-weight-medium": "500",
        "font-weight-semibold": "600",
        "font-weight-bold": "700",
        "line-height-tight": "1.25",
        "line-height-normal": "1.5",
        "line-height-relaxed": "1.75",
        # --- Spacing ---
        "spacing-xs": "0.25rem",
        "spacing-sm": "0.5rem",
        "spacing-md": "1rem",
        "spacing-lg": "1.5rem",
        "spacing-xl": "2rem",
        "spacing-2xl": "3rem",
        "spacing-3xl": "4rem",
        # --- Layout ---
        "max-width-content": "1200px",
        "max-width-text": "720px",
        "sidebar-width": "280px",
        "header-height": "64px",
        # --- Borders ---
        "border-radius-sm": "4px",
        "border-radius-md": "8px",
        "border-radius-lg": "12px",
        "border-radius-xl": "16px",
        "border-radius-full": "9999px",
        "border-width": "1px",
        "border-width-thick": "2px",
        # --- Shadows ---
        "shadow-sm": "0 1px 2px rgba(0, 0, 0, 0.05)",
        "shadow-md": "0 4px 6px rgba(0, 0, 0, 0.1)",
        "shadow-lg": "0 10px 15px rgba(0, 0, 0, 0.1)",
        "shadow-xl": "0 20px 25px rgba(0, 0, 0, 0.15)",
        # --- Transitions ---
        "transition-fast": "150ms ease",
        "transition-base": "200ms ease",
        "transition-slow": "300ms ease",
        # --- Z-Index ---
        "z-dropdown": "100",
        "z-sticky": "200",
        "z-modal": "300",
        "z-tooltip": "400",
    },
}

# ============================================================================
# THEME: Green Sustainability
# ============================================================================

THEME_GREEN_SUSTAINABILITY = {
    "slug": "green-sustainability",
    "name": {"en": "Green Sustainability"},
    "tokens": {
        # --- Colors (green-focused) ---
        "color-primary": "#059669",
        "color-primary-light": "#10b981",
        "color-primary-dark": "#047857",
        "color-secondary": "#64748b",
        "color-secondary-light": "#94a3b8",
        "color-secondary-dark": "#475569",
        "color-accent": "#0d9488",
        "color-accent-light": "#14b8a6",
        "color-accent-dark": "#0f766e",
        "color-success": "#22c55e",
        "color-warning": "#f59e0b",
        "color-error": "#ef4444",
        "color-info": "#06b6d4",
        "color-background": "#f0fdf4",
        "color-surface": "#ffffff",
        "color-surface-elevated": "#ffffff",
        "color-text-primary": "#14532d",
        "color-text-secondary": "#166534",
        "color-text-muted": "#4ade80",
        "color-text-inverse": "#ffffff",
        "color-border": "#bbf7d0",
        "color-border-light": "#dcfce7",
        "color-divider": "#bbf7d0",
        # --- Typography (same) ---
        "font-family-heading": "'Inter', sans-serif",
        "font-family-body": "'Inter', sans-serif",
        "font-family-mono": "'JetBrains Mono', monospace",
        "font-size-base": "1rem",
        "font-weight-normal": "400",
        "font-weight-semibold": "600",
        "line-height-normal": "1.5",
        # --- Other tokens inherit from default ---
    },
}

# ============================================================================
# THEME: Dark Mode
# ============================================================================

THEME_DARK_MODE = {
    "slug": "dark-mode",
    "name": {"en": "Dark Mode"},
    "tokens": {
        # --- Colors (dark) ---
        "color-primary": "#60a5fa",
        "color-primary-light": "#93c5fd",
        "color-primary-dark": "#3b82f6",
        "color-secondary": "#94a3b8",
        "color-secondary-light": "#cbd5e1",
        "color-secondary-dark": "#64748b",
        "color-accent": "#fbbf24",
        "color-accent-light": "#fcd34d",
        "color-accent-dark": "#f59e0b",
        "color-success": "#4ade80",
        "color-warning": "#fbbf24",
        "color-error": "#f87171",
        "color-info": "#38bdf8",
        "color-background": "#0f172a",
        "color-surface": "#1e293b",
        "color-surface-elevated": "#334155",
        "color-text-primary": "#f8fafc",
        "color-text-secondary": "#cbd5e1",
        "color-text-muted": "#64748b",
        "color-text-inverse": "#0f172a",
        "color-border": "#334155",
        "color-border-light": "#475569",
        "color-divider": "#334155",
        # --- Shadows (darker) ---
        "shadow-sm": "0 1px 2px rgba(0, 0, 0, 0.3)",
        "shadow-md": "0 4px 6px rgba(0, 0, 0, 0.4)",
        "shadow-lg": "0 10px 15px rgba(0, 0, 0, 0.5)",
        "shadow-xl": "0 20px 25px rgba(0, 0, 0, 0.6)",
    },
}

# ============================================================================
# ALL THEMES
# ============================================================================

ALL_THEMES = [
    THEME_CORPORATE_BLUE,
    THEME_GREEN_SUSTAINABILITY,
    THEME_DARK_MODE,
]

DEFAULT_THEME_SLUG = "corporate-blue"


def generate_css_variables(theme: dict) -> str:
    """Generate CSS custom properties from theme tokens."""
    lines = [":root {"]
    for key, value in theme["tokens"].items():
        css_var = f"  --{key}: {value};"
        lines.append(css_var)
    lines.append("}")
    return "\n".join(lines)

