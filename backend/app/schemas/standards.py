from datetime import date

from pydantic import BaseModel, Field


# --- Standard ---
class StandardCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=500)
    version: str | None = None
    jurisdiction: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None


class StandardUpdate(BaseModel):
    name: str | None = None
    version: str | None = None
    jurisdiction: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    is_active: bool | None = None


class StandardOut(BaseModel):
    id: int
    code: str
    name: str
    version: str | None
    jurisdiction: str | None
    effective_from: date | None
    effective_to: date | None
    is_active: bool
    family_code: str
    family_name: str
    catalog_group_code: str
    catalog_group_name: str
    is_attachable: bool

    model_config = {"from_attributes": True}


class StandardListOut(BaseModel):
    items: list[StandardOut]
    total: int


# --- Section ---
class SectionCreate(BaseModel):
    parent_section_id: int | None = None
    code: str | None = None
    title: str = Field(min_length=1, max_length=500)
    sort_order: int = 0


class SectionOut(BaseModel):
    id: int
    standard_id: int
    parent_section_id: int | None
    code: str | None
    title: str
    sort_order: int
    children: list["SectionOut"] = []

    model_config = {"from_attributes": True}


# --- Disclosure ---
class DisclosureCreate(BaseModel):
    section_id: int | None = None
    code: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    requirement_type: str = Field(pattern=r"^(quantitative|qualitative|mixed)$")
    mandatory_level: str = Field(pattern=r"^(mandatory|conditional|optional)$")
    applicability_rule: dict | None = None
    sort_order: int = 0


class DisclosureOut(BaseModel):
    id: int
    standard_id: int
    section_id: int | None
    code: str
    title: str
    description: str | None
    requirement_type: str
    mandatory_level: str
    applicability_rule: dict | None
    sort_order: int

    model_config = {"from_attributes": True}


class DisclosureListOut(BaseModel):
    items: list[DisclosureOut]
    total: int
