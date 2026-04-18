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
    default_collector_user_id: int | None = None
    default_reviewer_user_id: int | None = None


class EntityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=500)
    code: str | None = None
    country: str | None = None
    jurisdiction: str | None = None
    status: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    default_collector_user_id: int | None = None
    default_reviewer_user_id: int | None = None


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
    default_collector_user_id: int | None = None
    default_reviewer_user_id: int | None = None

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


class OrgSetupSubsidiary(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    entity_type: str = Field(
        default="legal_entity",
        pattern=r"^(legal_entity|branch|joint_venture|associate|facility|business_unit)$",
    )
    country: str | None = None
    jurisdiction: str | None = None
    ownership_percent: float = Field(default=100, ge=0, le=100)


class OrgSetupInviteUser(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: str = Field(pattern=r"^(admin|esg_manager|reviewer|collector|auditor)$")


class OrgSetupRequest(BaseModel):
    name: str = Field(min_length=1)
    legal_name: str | None = None
    registration_number: str | None = None
    country: str | None = None
    jurisdiction: str | None = None
    industry: str | None = None
    default_currency: str = "USD"
    reporting_year: int | None = None
    standards: list[str] = Field(default_factory=list)
    boundary_type: str = Field(
        default="financial_reporting_default",
        pattern=r"^(financial_reporting_default|financial_control|operational_control|equity_share|custom)$",
    )
    consolidation_approach: str | None = Field(
        default=None,
        pattern=r"^(financial_control|operational_control|equity_share)$",
    )
    ghg_scope_approach: str | None = Field(
        default=None,
        pattern=r"^(location_based|market_based)$",
    )
    subsidiaries: list[OrgSetupSubsidiary] = Field(default_factory=list)
    invite_users: list[OrgSetupInviteUser] = Field(default_factory=list)
