from pydantic import BaseModel


class BindRequest(BaseModel):
    requirement_item_id: int
    data_point_id: int


class ItemStatusOut(BaseModel):
    requirement_item_id: int
    status: str
    status_reason: str | None = None

    model_config = {"from_attributes": True}


class DisclosureStatusOut(BaseModel):
    disclosure_requirement_id: int
    status: str
    completion_percent: float
    code: str | None = None
    title: str | None = None
    entity_breakdown: dict | None = None

    model_config = {"from_attributes": True}


class BoundaryContextOut(BaseModel):
    boundary_id: int | None = None
    boundary_name: str | None = None
    snapshot_date: str | None = None
    entities_in_scope: int = 0
    excluded_entities: int = 0
    snapshot_locked: bool = False
    entities_without_data: list[str] = []


class CompletenessOut(BaseModel):
    project_id: int
    standard_id: int | None = None
    items: list[ItemStatusOut] = []
    disclosures: list[DisclosureStatusOut] = []
    overall_percent: float = 0
    overall_status: str = "missing"
    boundary_context: BoundaryContextOut | None = None
