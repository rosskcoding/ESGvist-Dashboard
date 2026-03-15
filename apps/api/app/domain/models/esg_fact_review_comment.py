"""
ESG Fact Review Comments.

Lightweight discussion comments for ESG facts, used by the Review UI.

Design:
- Tenant-scoped via company_id.
- Anchored to logical_key_hash so comments survive restatements/versions.
- fact_id is stored as context (which specific version the comment was made on).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class EsgFactReviewComment(Base, TimestampMixin):
    __tablename__ = "esg_fact_review_comments"
    __table_args__ = (
        Index("ix_esg_fact_review_comments_company_logical", "company_id", "logical_key_hash"),
        Index("ix_esg_fact_review_comments_company_fact", "company_id", "fact_id"),
    )

    comment_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    company_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.company_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    logical_key_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        doc="Fact logical key group this comment belongs to",
    )

    fact_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("esg_facts.fact_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Specific fact version this comment was made against",
    )

    body_md: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Comment body (markdown/plaintext)",
    )

    created_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships (optional; kept for future use / admin tooling).
    fact = relationship("EsgFact")
    company = relationship("Company")
    author = relationship("User", foreign_keys=[created_by])

