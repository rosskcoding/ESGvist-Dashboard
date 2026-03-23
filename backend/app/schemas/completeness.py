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

    model_config = {"from_attributes": True}


class CompletenessOut(BaseModel):
    project_id: int
    items: list[ItemStatusOut] = []
    overall_percent: float = 0
    overall_status: str = "missing"
