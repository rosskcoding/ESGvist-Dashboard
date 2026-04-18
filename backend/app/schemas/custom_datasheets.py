from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

CustomDatasheetStatus = Literal["draft", "active", "archived"]
CustomDatasheetItemSourceType = Literal["framework", "existing_custom", "new_custom"]
CustomDatasheetCategory = Literal[
    "environmental",
    "social",
    "governance",
    "business_operations",
    "other",
]
CustomDatasheetCollectionScope = Literal["project", "entity", "facility"]


class CustomDatasheetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    status: CustomDatasheetStatus = "draft"


class CustomDatasheetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: CustomDatasheetStatus | None = None


class CustomDatasheetItemCreate(BaseModel):
    shared_element_id: int
    assignment_id: int | None = None
    source_type: Literal["framework", "existing_custom"]
    category: CustomDatasheetCategory
    display_group: str | None = Field(default=None, max_length=255)
    label_override: str | None = Field(default=None, max_length=255)
    help_text: str | None = None
    collection_scope: CustomDatasheetCollectionScope
    entity_id: int | None = None
    facility_id: int | None = None
    is_required: bool = True
    sort_order: int = 0


class CustomDatasheetCreateCustomMetric(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    concept_domain: str | None = Field(default=None, max_length=100)
    default_value_type: Literal["number", "text", "boolean", "date", "enum", "document"] | None = None
    default_unit_code: str | None = Field(default=None, max_length=50)
    category: CustomDatasheetCategory
    display_group: str | None = Field(default=None, max_length=255)
    label_override: str | None = Field(default=None, max_length=255)
    help_text: str | None = None
    collection_scope: CustomDatasheetCollectionScope
    entity_id: int | None = None
    facility_id: int | None = None
    is_required: bool = True
    sort_order: int = 0


class CustomDatasheetItemUpdate(BaseModel):
    category: CustomDatasheetCategory | None = None
    display_group: str | None = Field(default=None, max_length=255)
    label_override: str | None = Field(default=None, max_length=255)
    help_text: str | None = None
    assignment_id: int | None = None
    collection_scope: CustomDatasheetCollectionScope | None = None
    entity_id: int | None = None
    facility_id: int | None = None
    is_required: bool | None = None
    sort_order: int | None = None
    status: Literal["active", "archived"] | None = None


class CustomDatasheetItemOut(BaseModel):
    id: int
    shared_element_id: int
    shared_element_code: str | None = None
    shared_element_name: str | None = None
    shared_element_key: str | None = None
    owner_layer: str | None = None
    assignment_id: int | None = None
    source_type: str
    category: str
    display_group: str | None = None
    label_override: str | None = None
    help_text: str | None = None
    collection_scope: str
    entity_id: int | None = None
    entity_name: str | None = None
    facility_id: int | None = None
    facility_name: str | None = None
    is_required: bool
    sort_order: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CustomDatasheetOut(BaseModel):
    id: int
    reporting_project_id: int
    name: str
    description: str | None = None
    status: str
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime
    item_count: int = 0
    framework_item_count: int = 0
    custom_item_count: int = 0

    model_config = {"from_attributes": True}


class CustomDatasheetDetailOut(CustomDatasheetOut):
    items: list[CustomDatasheetItemOut] = Field(default_factory=list)


class CustomDatasheetListOut(BaseModel):
    items: list[CustomDatasheetOut]
    total: int


class CustomDatasheetOptionSearchOut(BaseModel):
    shared_element_id: int
    shared_element_code: str
    shared_element_name: str
    shared_element_key: str | None = None
    owner_layer: str
    source_type: Literal["framework", "existing_custom"]
    concept_domain: str | None = None
    default_value_type: str | None = None
    default_unit_code: str | None = None
    suggested_category: CustomDatasheetCategory
    standard_id: int | None = None
    standard_code: str | None = None
    standard_name: str | None = None
    disclosure_id: int | None = None
    disclosure_code: str | None = None
    disclosure_title: str | None = None
    requirement_item_id: int | None = None
    requirement_item_code: str | None = None
    requirement_item_name: str | None = None


class CustomDatasheetOptionSearchListOut(BaseModel):
    items: list[CustomDatasheetOptionSearchOut]
    total: int
