from pydantic import BaseModel, Field


class MappingCreate(BaseModel):
    requirement_item_id: int
    shared_element_id: int
    mapping_type: str = Field(default="full", pattern=r"^(full|partial|derived)$")


class MappingOut(BaseModel):
    id: int
    requirement_item_id: int
    shared_element_id: int
    mapping_type: str

    model_config = {"from_attributes": True}


class MappingListOut(BaseModel):
    items: list[MappingOut]
    total: int


class CrossStandardElement(BaseModel):
    shared_element_id: int
    shared_element_code: str
    shared_element_name: str
    standards: list[str]
    mapping_count: int
