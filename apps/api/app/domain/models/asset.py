"""
Asset and AssetLink models — SYSTEM_REGISTRY B6.

Extended for multi-tenant:
- company_id: tenant binding
- created_by: uploader user
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import AssetKind

if TYPE_CHECKING:
    from .block import Block
    from .company import Company
    from .user import User


class Asset(Base):
    """
    Asset entity — uploaded file (images/fonts/attachments).

    Invariants:
    - sha256 is stored for integrity
    - kind/mime must be in allowlist
    - company_id is required (tenant binding)
    """

    __tablename__ = "assets"

    asset_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    # Tenant binding
    company_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.company_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[AssetKind] = mapped_column(
        SQLEnum(AssetKind, name="asset_kind", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    storage_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # Relationships
    company: Mapped["Company"] = relationship(
        "Company",
        foreign_keys=[company_id],
    )
    uploader: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[created_by],
    )
    links: Mapped[list["AssetLink"]] = relationship(
        "AssetLink",
        back_populates="asset",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Asset {self.kind.value}: {self.filename}>"


class AssetLink(Base):
    """
    Many-to-many relationship between Block and Asset.
    """

    __tablename__ = "asset_links"

    block_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("blocks.block_id", ondelete="CASCADE"),
        primary_key=True,
    )
    asset_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("assets.asset_id", ondelete="CASCADE"),
        primary_key=True,
    )
    purpose: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="content",
        doc="Purpose: content, thumbnail, background, etc.",
    )

    # Relationships
    block: Mapped["Block"] = relationship(
        "Block",
        back_populates="asset_links",
    )
    asset: Mapped["Asset"] = relationship(
        "Asset",
        back_populates="links",
    )

    def __repr__(self) -> str:
        return f"<AssetLink {self.block_id} -> {self.asset_id}>"
