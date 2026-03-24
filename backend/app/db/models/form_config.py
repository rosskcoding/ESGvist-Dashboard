from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin


class FormConfiguration(Base, TimestampMixin):
    __tablename__ = "form_configurations"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("reporting_projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    config: Mapped[dict] = mapped_column(JSON, nullable=False)
    # config structure:
    # {
    #   "steps": [
    #     {
    #       "id": "step-1",
    #       "title": "General Information",
    #       "fields": [
    #         {"shared_element_id": 5, "visible": true, "required": true,
    #          "help_text": "...", "order": 1, "tooltip": "..."}
    #       ]
    #     }
    #   ]
    # }
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
