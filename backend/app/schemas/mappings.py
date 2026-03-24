from datetime import date

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
    version: int = 1
    is_current: bool = True
    valid_from: date | None = None
    valid_to: date | None = None

    model_config = {"from_attributes": True}


class MappingListOut(BaseModel):
    items: list[MappingOut]
    total: int


class MappingVersionListOut(BaseModel):
    items: list[MappingOut]
    total: int


class MappingDiffChange(BaseModel):
    field: str
    old_value: str | None
    new_value: str | None


class MappingDiffOut(BaseModel):
    v1: int
    v2: int
    changes: list[MappingDiffChange]


class CrossStandardElement(BaseModel):
    shared_element_id: int
    shared_element_code: str
    shared_element_name: str
    standards: list[str]
    mapping_count: int
