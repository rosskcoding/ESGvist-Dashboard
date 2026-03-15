"""
ESG Fact evidence items.

Evidence items are attached to ESG facts and can be:
- file: reference to an uploaded Asset
- link: external URL
- note: markdown note

This is separate from report EvidenceItem (which is report/section/block scoped).
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class EsgFactEvidenceType(str, Enum):
    FILE = "file"
    LINK = "link"
    NOTE = "note"


class EsgFactEvidenceItem(Base, TimestampMixin):
    __tablename__ = "esg_fact_evidence_items"
    __table_args__ = (
        Index("ix_esg_fact_evidence_company_fact", "company_id", "fact_id"),
        # Ensure the payload matches the evidence type and doesn't mix fields.
        CheckConstraint(
            "("
            "type = 'file' AND asset_id IS NOT NULL AND url IS NULL AND note_md IS NULL"
            ") OR ("
            "type = 'link' AND url IS NOT NULL AND asset_id IS NULL AND note_md IS NULL"
            ") OR ("
            "type = 'note' AND note_md IS NOT NULL AND asset_id IS NULL AND url IS NULL"
            ")",
            name="ck_esg_fact_evidence_type_payload",
        ),
    )

    evidence_id: Mapped[UUID] = mapped_column(
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
    fact_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("esg_facts.fact_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[EsgFactEvidenceType] = mapped_column(
        SQLEnum(
            EsgFactEvidenceType,
            native_enum=False,
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Optional metadata (assignment + provenance).
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    owner_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    asset_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("assets.asset_id", ondelete="SET NULL"),
        nullable=True,
    )
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    note_md: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    company = relationship("Company")
    fact = relationship("EsgFact")
    asset = relationship("Asset")

    def __repr__(self) -> str:
        return f"<EsgFactEvidenceItem {self.evidence_id} type={self.type.value} fact={self.fact_id}>"
