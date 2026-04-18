from pydantic import BaseModel, Field


class DimensionIn(BaseModel):
    dimension_type: str
    dimension_value: str


class DimensionFlagsOut(BaseModel):
    scope: bool = False
    gas_type: bool = False
    category: bool = False


class DimensionValuesOut(BaseModel):
    scope: str | None = None
    gas_type: str | None = None
    category: str | None = None


class RelatedStandardOut(BaseModel):
    code: str
    name: str


class DataPointCreate(BaseModel):
    shared_element_id: int
    entity_id: int | None = None
    facility_id: int | None = None
    numeric_value: float | None = None
    text_value: str | None = None
    unit_code: str | None = None
    dimensions: list[DimensionIn] = []


class DataPointUpdate(BaseModel):
    numeric_value: float | None = None
    text_value: str | None = None
    unit_code: str | None = None
    methodology: str | None = None
    dimensions: list[DimensionIn] | None = None


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
    methodology: str | None = None
    created_by: int | None
    element_code: str | None = None
    element_name: str | None = None
    entity_name: str | None = None
    facility_name: str | None = None
    boundary_status: str | None = None
    consolidation_method: str | None = None
    standards: list[str] = Field(default_factory=list)
    related_standards: list[RelatedStandardOut] = Field(default_factory=list)
    reused_across_standards: bool = False
    collection_status: str | None = None
    element_type: str | None = None
    evidence_required: bool = False
    evidence_count: int = 0
    dimensions: DimensionFlagsOut = Field(default_factory=DimensionFlagsOut)
    dimension_values: DimensionValuesOut = Field(default_factory=DimensionValuesOut)
    unit_options: list[str] = Field(default_factory=list)
    methodology_options: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class DataPointListOut(BaseModel):
    items: list[DataPointOut]
    total: int
