"""
Pydantic schemas for Template entities.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class TemplateBase(BaseModel):
    """Base template schema."""

    scope: Literal["block", "section", "report"]
    block_type: str | None = None
    name: str = Field(max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    template_json: dict = Field(default_factory=dict)
    is_system: bool = False


class TemplateCreate(TemplateBase):
    """Schema for creating a template."""

    pass


class TemplateUpdate(BaseModel):
    """Schema for updating a template."""

    name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    tags: list[str] | None = Field(default=None, max_length=20)
    template_json: dict | None = None
    is_active: bool | None = None


class TemplateDTO(TemplateBase):
    """Template data transfer object."""

    template_id: UUID
    is_active: bool
    created_at_utc: datetime
    updated_at_utc: datetime

    model_config = {"from_attributes": True}


class TemplateListItem(BaseModel):
    """Minimal template info for list views."""

    template_id: UUID
    scope: str
    block_type: str | None
    name: str
    description: str | None
    tags: list[str]
    is_system: bool

    model_config = {"from_attributes": True}


class ApplyTemplateRequest(BaseModel):
    """Request to create a block from a template."""

    template_id: UUID
    section_id: UUID
    report_id: UUID
    order_index: int = 0

    # Optional overrides for the template
    overrides: dict | None = Field(
        default=None,
        description="Overrides to apply to the template before creating the block",
    )




