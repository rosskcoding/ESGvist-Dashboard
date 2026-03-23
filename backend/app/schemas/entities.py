from datetime import date

from pydantic import BaseModel, Field


class EntityCreate(BaseModel):
    parent_entity_id: int | None = None
    name: str = Field(min_length=1, max_length=500)
    code: str | None = None
    entity_type: str = Field(pattern=r"^(parent_company|legal_entity|branch|joint_venture|associate|facility|business_unit)$")
    country: str | None = None
    jurisdiction: str | None = None
    status: str = "active"
    valid_from: date | None = None
    valid_to: date | None = None


class EntityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=500)
    code: str | None = None
    country: str | None = None
    jurisdiction: str | None = None
    status: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None


class EntityOut(BaseModel):
    id: int
    organization_id: int
    parent_entity_id: int | None
    name: str
    code: str | None
    entity_type: str
    country: str | None
    jurisdiction: str | None
    status: str
    valid_from: date | None
    valid_to: date | None

    model_config = {"from_attributes": True}


class EntityListOut(BaseModel):
    items: list[EntityOut]
    total: int


class OwnershipLinkCreate(BaseModel):
    parent_entity_id: int
    child_entity_id: int
    ownership_percent: float = Field(ge=0, le=100)
    ownership_type: str = Field(default="direct", pattern=r"^(direct|indirect|beneficial)$")
    comment: str | None = None


class OwnershipLinkOut(BaseModel):
    id: int
    parent_entity_id: int
    child_entity_id: int
    ownership_percent: float
    ownership_type: str
    comment: str | None

    model_config = {"from_attributes": True}


class ControlLinkCreate(BaseModel):
    controlling_entity_id: int
    controlled_entity_id: int
    control_type: str = Field(pattern=r"^(financial_control|operational_control|management_control|significant_influence)$")
    is_controlled: bool = True
    rationale: str | None = None


class ControlLinkOut(BaseModel):
    id: int
    controlling_entity_id: int
    controlled_entity_id: int
    control_type: str
    is_controlled: bool
    rationale: str | None

    model_config = {"from_attributes": True}


class OrgSetupRequest(BaseModel):
    name: str = Field(min_length=1)
    country: str | None = None
    industry: str | None = None
    default_currency: str = "USD"
