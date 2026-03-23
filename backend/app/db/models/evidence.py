from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin


class Evidence(Base, TimestampMixin):
    __tablename__ = "evidences"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String, nullable=False)  # file | link
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String, default="manual", nullable=False)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class EvidenceFile(Base):
    __tablename__ = "evidence_files"

    evidence_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("evidences.id", ondelete="CASCADE"), primary_key=True
    )
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    file_uri: Mapped[str] = mapped_column(String, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String, nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)


class EvidenceLink(Base):
    __tablename__ = "evidence_links"

    evidence_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("evidences.id", ondelete="CASCADE"), primary_key=True
    )
    url: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    access_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class DataPointEvidence(Base, TimestampMixin):
    __tablename__ = "data_point_evidences"

    id: Mapped[int] = mapped_column(primary_key=True)
    data_point_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("data_points.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evidence_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("evidences.id", ondelete="CASCADE"), nullable=False, index=True
    )
    linked_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("data_point_id", "evidence_id", name="uq_dp_evidence"),
    )
