from pydantic import BaseModel, Field


class SharedElementCreate(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=500)
    description: str | None = None
    concept_domain: str | None = None
    default_value_type: str | None = None
    default_unit_code: str | None = None


class SharedElementOut(BaseModel):
    id: int
    code: str
    name: str
    description: str | None
    concept_domain: str | None
    default_value_type: str | None
    default_unit_code: str | None
    dimensions: list["DimensionOut"] = []

    model_config = {"from_attributes": True}


class SharedElementListOut(BaseModel):
    items: list[SharedElementOut]
    total: int


class DimensionCreate(BaseModel):
    dimension_type: str = Field(min_length=1, max_length=50)
    is_required: bool = False


class DimensionOut(BaseModel):
    id: int
    shared_element_id: int
    dimension_type: str
    is_required: bool

    model_config = {"from_attributes": True}
