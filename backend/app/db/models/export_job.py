from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin


class ExportJob(Base, TimestampMixin):
    __tablename__ = "export_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reporting_project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("reporting_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_by_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    report_type: Mapped[str] = mapped_column(String, default="project_report", nullable=False)
    export_format: Mapped[str] = mapped_column(String, default="json", nullable=False)
    status: Mapped[str] = mapped_column(String, default="queued", nullable=False, index=True)
    content_type: Mapped[str | None] = mapped_column(String, nullable=True)
    artifact_name: Mapped[str | None] = mapped_column(String, nullable=True)
    artifact_encoding: Mapped[str | None] = mapped_column(String, nullable=True)
    artifact_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
