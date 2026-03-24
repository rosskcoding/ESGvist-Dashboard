from datetime import datetime

from pydantic import BaseModel, Field


class CalculationRuleCreate(BaseModel):
    output_element_id: int
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    formula: dict
    input_element_ids: list[int]
    is_active: bool = True


class CalculationRuleOut(BaseModel):
    id: int
    organization_id: int
    output_element_id: int
    name: str
    description: str | None
    formula: dict
    input_element_ids: list[int]
    is_active: bool
    created_by: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CalculationRuleListOut(BaseModel):
    items: list[CalculationRuleOut]
    total: int


class RecalculateResult(BaseModel):
    recalculated: int
    errors: list[str] = Field(default_factory=list)
