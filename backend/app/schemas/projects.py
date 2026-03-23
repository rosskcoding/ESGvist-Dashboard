from datetime import date

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1)
    reporting_year: int | None = None
    deadline: date | None = None


class ProjectOut(BaseModel):
    id: int
    organization_id: int
    name: str
    status: str
    reporting_year: int | None
    deadline: date | None
    boundary_definition_id: int | None

    model_config = {"from_attributes": True}


class ProjectListOut(BaseModel):
    items: list[ProjectOut]
    total: int


class ProjectStandardAdd(BaseModel):
    standard_id: int
    is_base_standard: bool = False


class AssignmentCreate(BaseModel):
    shared_element_id: int
    entity_id: int | None = None
    collector_id: int | None = None
    reviewer_id: int | None = None
    deadline: date | None = None


class AssignmentOut(BaseModel):
    id: int
    reporting_project_id: int
    shared_element_id: int
    entity_id: int | None
    collector_id: int | None
    reviewer_id: int | None
    deadline: date | None
    status: str

    model_config = {"from_attributes": True}


class BoundaryDefCreate(BaseModel):
    name: str = Field(min_length=1)
    boundary_type: str = Field(
        default="financial_reporting_default",
        pattern=r"^(financial_reporting_default|financial_control|operational_control|equity_share|custom)$",
    )
    description: str | None = None
    is_default: bool = False


class BoundaryDefOut(BaseModel):
    id: int
    organization_id: int
    name: str
    boundary_type: str
    description: str | None
    is_default: bool

    model_config = {"from_attributes": True}
