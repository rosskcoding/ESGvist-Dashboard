"""
Template models for block, section, and report templates.

Templates provide pre-configured structures for common report components.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import String, Text, Boolean, DateTime
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

if TYPE_CHECKING:
    pass


class Template(Base):
    """
    Reusable template for blocks, sections, or reports.

    Templates store pre-configured data structures that can be
    used as starting points when creating new content.
    """

    __tablename__ = "templates"

    template_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Template scope: block, section, or report
    scope: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )

    # Block type (for block templates only)
    block_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )

    # Template metadata
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Tags for categorization
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String(64)),
        default=list,
        server_default="{}",
    )

    # Template content (JSON structure matching block/section/report schema)
    template_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    # System template (built-in vs user-created)
    is_system: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
    )

    # Active flag (for soft disable)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
    )

    # Timestamps
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Template {self.name} ({self.scope})>"


# Template scope constants
TEMPLATE_SCOPE_BLOCK = "block"
TEMPLATE_SCOPE_SECTION = "section"
TEMPLATE_SCOPE_REPORT = "report"

VALID_TEMPLATE_SCOPES = [
    TEMPLATE_SCOPE_BLOCK,
    TEMPLATE_SCOPE_SECTION,
    TEMPLATE_SCOPE_REPORT,
]

