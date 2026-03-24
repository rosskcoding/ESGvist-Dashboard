from datetime import datetime

from pydantic import BaseModel, Field


class FormFieldSchema(BaseModel):
    shared_element_id: int
    requirement_item_id: int | None = None
    assignment_id: int | None = None
    entity_id: int | None = None
    facility_id: int | None = None
    visible: bool = True
    required: bool = False
    help_text: str | None = None
    tooltip: str | None = None
    order: int = 0


class FormStepSchema(BaseModel):
    id: str
    title: str
    fields: list[FormFieldSchema] = Field(default_factory=list)


class FormConfigCreate(BaseModel):
    project_id: int | None = None
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    config: dict
    is_active: bool = True


class FormConfigUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    config: dict | None = None
    is_active: bool | None = None


class FormConfigOut(BaseModel):
    id: int
    organization_id: int
    project_id: int | None
    name: str
    description: str | None
    config: dict
    is_active: bool
    created_by: int | None
    created_at: datetime
    updated_at: datetime | None = None
    resolved_for_project_id: int | None = None
    resolution_scope: str | None = None
    health: "FormConfigHealthOut | None" = None

    model_config = {"from_attributes": True}


class FormConfigListOut(BaseModel):
    items: list[FormConfigOut]
    total: int


class FormConfigHealthIssueOut(BaseModel):
    code: str
    message: str
    affected_fields: int = 0


class FormConfigHealthOut(BaseModel):
    status: str
    is_stale: bool = False
    target_project_id: int | None = None
    field_count: int = 0
    assignment_scoped_fields: int = 0
    context_scoped_fields: int = 0
    issue_count: int = 0
    issues: list[FormConfigHealthIssueOut] = Field(default_factory=list)
    latest_assignment_updated_at: datetime | None = None
    latest_boundary_updated_at: datetime | None = None


FormConfigOut.model_rebuild()
