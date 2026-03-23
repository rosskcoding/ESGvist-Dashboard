from datetime import datetime

from pydantic import BaseModel, Field


class EvidenceCreate(BaseModel):
    type: str = Field(pattern=r"^(file|link)$")
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    source_type: str = "manual"
    # file fields
    file_name: str | None = None
    file_uri: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    # link fields
    url: str | None = None
    label: str | None = None


class LinkedDataPointOut(BaseModel):
    data_point_id: int
    code: str
    label: str


class LinkedRequirementItemOut(BaseModel):
    requirement_item_id: int
    code: str
    description: str


class EvidenceOut(BaseModel):
    id: int
    organization_id: int
    type: str
    title: str
    description: str | None
    source_type: str
    created_by: int | None
    created_by_name: str | None = None
    created_at: datetime
    upload_date: datetime | None = None
    url: str | None = None
    file_name: str | None = None
    file_size: int | None = None
    mime_type: str | None = None
    binding_status: str = "unbound"
    linked_data_points: list[LinkedDataPointOut] = Field(default_factory=list)
    linked_requirement_items: list[LinkedRequirementItemOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class EvidenceListOut(BaseModel):
    items: list[EvidenceOut]
    total: int


class EvidenceLinkRequest(BaseModel):
    evidence_id: int
