from datetime import date, datetime

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
    created_at: datetime | None = None
    updated_at: datetime | None = None
    reporting_period_start: date | None = None
    reporting_period_end: date | None = None
    standard_codes: list[str] = Field(default_factory=list)
    completion_percentage: float = 0.0

    model_config = {"from_attributes": True}


class ProjectListOut(BaseModel):
    items: list[ProjectOut]
    total: int


class ProjectStandardAdd(BaseModel):
    standard_id: int
    is_base_standard: bool = False


class AssignmentCreate(BaseModel):
    shared_element_id: int | None = None
    shared_element_code: str | None = None
    shared_element_name: str | None = None
    entity_id: int | None = None
    facility_id: int | None = None
    consolidation_method: str | None = None
    collector_id: int | None = None
    reviewer_id: int | None = None
    backup_collector_id: int | None = None
    deadline: date | None = None
    escalation_after_days: int = Field(default=3, ge=1, le=365)


class AssignmentOut(BaseModel):
    id: int
    reporting_project_id: int
    shared_element_id: int
    entity_id: int | None
    facility_id: int | None = None
    collector_id: int | None
    reviewer_id: int | None
    backup_collector_id: int | None
    deadline: date | None
    escalation_after_days: int
    status: str

    model_config = {"from_attributes": True}


class AssignmentMatrixUserOut(BaseModel):
    id: int
    name: str
    email: str


class AssignmentMatrixEntityOut(BaseModel):
    id: int
    name: str
    code: str | None = None


class AssignmentMatrixRowOut(BaseModel):
    id: int
    shared_element_id: int
    shared_element_code: str
    shared_element_name: str
    entity_id: int | None = None
    entity_name: str | None = None
    facility_id: int | None = None
    facility_name: str | None = None
    boundary_included: bool
    consolidation_method: str
    collector_id: int | None = None
    collector_name: str | None = None
    reviewer_id: int | None = None
    reviewer_name: str | None = None
    backup_collector_id: int | None = None
    backup_collector_name: str | None = None
    deadline: date | None
    escalation_after_days: int
    sla_status: str
    days_overdue: int = 0
    days_until_deadline: int | None = None
    status: str
    created_at: str | None = None


class AssignmentMatrixOut(BaseModel):
    assignments: list[AssignmentMatrixRowOut]
    users: list[AssignmentMatrixUserOut]
    entities: list[AssignmentMatrixEntityOut]


class AssignmentInlineUpdate(BaseModel):
    id: int
    field: str
    value: str


class AssignmentBulkUpdate(BaseModel):
    ids: list[int]
    field: str
    value: str


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
    entity_count: int = 0

    model_config = {"from_attributes": True}


class BoundaryDefUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    boundary_type: str | None = Field(
        default=None,
        pattern=r"^(financial_reporting_default|financial_control|operational_control|equity_share|custom)$",
    )
    description: str | None = None
    is_default: bool | None = None


class BoundaryMembershipUpdate(BaseModel):
    entity_id: int
    included: bool = True
    inclusion_source: str = Field(default="manual", pattern=r"^(automatic|manual|override)$")
    consolidation_method: str | None = Field(
        default=None,
        pattern=r"^(full|proportional|equity_share)$",
    )
    inclusion_reason: str | None = None


class BoundaryMembershipReplaceRequest(BaseModel):
    memberships: list[BoundaryMembershipUpdate]


class BoundaryMembershipRowOut(BaseModel):
    id: int | None = None
    entity_id: int
    entity_name: str
    entity_type: str
    included: bool = False
    inclusion_source: str | None = None
    consolidation_method: str | None = None
    inclusion_reason: str | None = None
    explicit: bool = False


class BoundaryMembershipListOut(BaseModel):
    boundary_id: int
    boundary_name: str
    memberships: list[BoundaryMembershipRowOut]


class ProjectBoundaryOut(BaseModel):
    boundary_id: int | None = None
    boundary_name: str | None = None
    boundary_type: str | None = None
    snapshot_id: int | None = None
    snapshot_locked: bool = False
    snapshot_date: str | None = None
    snapshot_status: str = "not_created"
    snapshot_created_at: str | None = None
    entities_in_scope: int = 0
    excluded_entities: int = 0


class ProjectStandardSummaryOut(BaseModel):
    id: int
    standard_id: int
    standard_name: str
    code: str
    disclosure_count: int
    completion_percentage: float


class ProjectStandardSummaryListOut(BaseModel):
    items: list[ProjectStandardSummaryOut]


class ProjectAssignmentSummaryOut(BaseModel):
    id: int
    user_name: str
    email: str
    role: str
    assigned_disclosures: int
    completed: int


class ProjectAssignmentSummaryListOut(BaseModel):
    items: list[ProjectAssignmentSummaryOut]
