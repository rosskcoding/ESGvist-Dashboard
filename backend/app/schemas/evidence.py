from datetime import datetime

from pydantic import BaseModel, Field, model_validator


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

    @model_validator(mode="after")
    def validate_type_specific_fields(self):
        if self.type == "link" and not (self.url and self.url.strip()):
            raise ValueError("url is required for link evidence")
        return self


class LinkedDataPointRequirementContextOut(BaseModel):
    requirement_item_id: int
    item_code: str | None = None
    item_name: str
    disclosure_code: str | None = None
    disclosure_title: str
    standard_code: str
    standard_name: str


class LinkedDataPointOut(BaseModel):
    data_point_id: int
    code: str
    label: str
    project_id: int | None = None
    project_name: str | None = None
    entity_name: str | None = None
    facility_name: str | None = None
    element_key: str | None = None
    owner_layer: str | None = None
    is_custom: bool = False
    requirement_contexts: list[LinkedDataPointRequirementContextOut] = Field(default_factory=list)


class LinkedRequirementItemOut(BaseModel):
    project_id: int | None = None
    project_name: str | None = None
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
