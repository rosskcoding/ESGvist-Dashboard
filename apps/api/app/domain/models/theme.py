"""
Theme model — design tokens storage.

Spec reference: 05_Theming_Styling.md Section 5.3.3
"""

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    pass


class Theme(Base, TimestampMixin):
    """
    Theme entity — design tokens for visual styling.

    Tokens are stored as JSONB and converted to CSS variables at render time.
    """

    __tablename__ = "themes"

    theme_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    slug: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        doc="URL-safe identifier (e.g. 'corporate-blue')",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Human-readable name",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    tokens_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        doc="Design tokens as {token_name: value}",
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Default theme for new reports",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        doc="Available for selection",
    )

    def __repr__(self) -> str:
        return f"<Theme {self.slug}: {self.name}>"

    def to_css(self) -> str:
        """Generate CSS variables from tokens."""
        if not self.tokens_json:
            return ""

        lines = [f":root[data-theme='{self.slug}'] {{"]
        for token, value in sorted(self.tokens_json.items()):
            # Ensure token name is valid CSS variable name
            css_var = token if token.startswith("--") else f"--{token}"
            lines.append(f"  {css_var}: {value};")
        lines.append("}")
        return "\n".join(lines)


# Default theme tokens (from spec 05_Theming_Styling.md Section 5.1.1)
DEFAULT_THEME_TOKENS = {
    # Colors
    "color-bg": "#ffffff",
    "color-surface": "#f8fafc",
    "color-text": "#1e293b",
    "color-muted": "#64748b",
    "color-border": "#e2e8f0",
    "color-accent": "#2563eb",
    "color-accent-contrast": "#ffffff",
    "color-positive": "#16a34a",
    "color-warning": "#d97706",
    "color-risk": "#dc2626",
    "color-link": "#2563eb",
    # Typography
    "font-sans": "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
    "font-serif": "'Georgia', serif",
    "font-mono": "'JetBrains Mono', monospace",
    "text-xs": "0.75rem",
    "text-sm": "0.875rem",
    "text-md": "1rem",
    "text-lg": "1.125rem",
    "text-xl": "1.5rem",
    "text-2xl": "2rem",
    "line-height-body": "1.6",
    "line-height-heading": "1.2",
    "font-weight-regular": "400",
    "font-weight-semibold": "600",
    "font-weight-bold": "700",
    # Layout
    "container-max-width": "1200px",
    "content-max-width": "70ch",
    "grid-gutter": "24px",
    # Radius
    "radius-sm": "4px",
    "radius-md": "8px",
    "radius-lg": "12px",
    # Shadows
    "shadow-sm": "0 1px 2px rgba(0, 0, 0, 0.05)",
    "shadow-md": "0 4px 6px rgba(0, 0, 0, 0.1)",
    # Spacing
    "space-1": "4px",
    "space-2": "8px",
    "space-3": "12px",
    "space-4": "16px",
    "space-5": "24px",
    "space-6": "32px",
    "space-7": "48px",
    "space-8": "64px",
    # Components
    "table-border-width": "1px",
    "table-row-gap": "12px",
    "chart-height-default": "320px",
    "kpi-card-min-width": "200px",
}

# Dark theme variant
DARK_THEME_TOKENS = {
    **DEFAULT_THEME_TOKENS,
    "color-bg": "#0f172a",
    "color-surface": "#1e293b",
    "color-text": "#f1f5f9",
    "color-muted": "#94a3b8",
    "color-border": "#334155",
    "color-accent": "#3b82f6",
    "color-accent-contrast": "#ffffff",
    "color-positive": "#22c55e",
    "color-warning": "#f59e0b",
    "color-risk": "#ef4444",
    "color-link": "#60a5fa",
}

# Corporate blue theme
CORPORATE_BLUE_TOKENS = {
    **DEFAULT_THEME_TOKENS,
    "color-accent": "#0066cc",
    "color-link": "#0066cc",
    "font-sans": "'Source Sans Pro', -apple-system, sans-serif",
}

