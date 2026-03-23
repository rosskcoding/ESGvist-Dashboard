from pydantic import BaseModel, Field


class RequirementItemCreate(BaseModel):
    parent_item_id: int | None = None
    item_code: str | None = None
    name: str = Field(min_length=1, max_length=500)
    description: str | None = None
    item_type: str = Field(pattern=r"^(metric|attribute|dimension|narrative|document)$")
    value_type: str = Field(pattern=r"^(number|text|boolean|date|enum|json)$")
    unit_code: str | None = None
    is_required: bool = True
    requires_evidence: bool = False
    cardinality_min: int = 0
    cardinality_max: int | None = None
    granularity_rule: dict | None = None
    validation_rule: dict | None = None
    sort_order: int = 0


class RequirementItemOut(BaseModel):
    id: int
    disclosure_requirement_id: int
    parent_item_id: int | None
    item_code: str | None
    name: str
    description: str | None
    item_type: str
    value_type: str
    unit_code: str | None
    is_required: bool
    requires_evidence: bool
    cardinality_min: int
    cardinality_max: int | None
    granularity_rule: dict | None
    validation_rule: dict | None
    sort_order: int

    model_config = {"from_attributes": True}


class RequirementItemListOut(BaseModel):
    items: list[RequirementItemOut]
    total: int


class DependencyCreate(BaseModel):
    depends_on_item_id: int
    dependency_type: str = Field(pattern=r"^(requires|excludes|conditional_on)$")
    condition_expression: dict | None = None


class DependencyOut(BaseModel):
    id: int
    requirement_item_id: int
    depends_on_item_id: int
    dependency_type: str
    condition_expression: dict | None

    model_config = {"from_attributes": True}
