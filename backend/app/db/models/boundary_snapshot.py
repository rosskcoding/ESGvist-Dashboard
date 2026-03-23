from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base


class BoundarySnapshot(Base):
    __tablename__ = "boundary_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    reporting_project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("reporting_projects.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    boundary_definition_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("boundary_definitions.id", ondelete="RESTRICT"), nullable=False
    )
    snapshot_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
