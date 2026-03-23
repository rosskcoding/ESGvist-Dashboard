from pydantic import BaseModel, Field


class DimensionIn(BaseModel):
    dimension_type: str
    dimension_value: str


class DataPointCreate(BaseModel):
    shared_element_id: int
    entity_id: int | None = None
    facility_id: int | None = None
    numeric_value: float | None = None
    text_value: str | None = None
    unit_code: str | None = None
    dimensions: list[DimensionIn] = []


class DataPointOut(BaseModel):
    id: int
    reporting_project_id: int
    shared_element_id: int
    entity_id: int | None
    facility_id: int | None = None
    status: str
    numeric_value: float | None
    text_value: str | None
    unit_code: str | None
    created_by: int | None

    model_config = {"from_attributes": True}


class DataPointListOut(BaseModel):
    items: list[DataPointOut]
    total: int
