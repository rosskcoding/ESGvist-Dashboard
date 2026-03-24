from pydantic import BaseModel, Field


class ExplainRequest(BaseModel):
    requirement_item_id: int | None = None
    project_id: int | None = None
    entity_id: int | None = None
    disclosure_id: int | None = None


class ExplainEvidenceRequest(BaseModel):
    requirement_item_id: int
    project_id: int | None = None


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    screen: str | None = None
    context: dict | None = None


class SuggestedAction(BaseModel):
    label: str
    action_type: str
    target: str
    description: str | None = None


class Reference(BaseModel):
    title: str
    source: str
    url: str | None = None


class AIResponse(BaseModel):
    text: str
    reasons: list[str] | None = None
    next_actions: list[SuggestedAction] | None = None
    references: list[Reference] | None = None
    confidence: str = "high"
    provider: str | None = None


class ReviewAssistResponse(BaseModel):
    summary: str
    anomalies: list[str]
    missing_evidence: list[str]
    draft_comment: str | None = None
    reuse_impact: str | None = None
    provider: str | None = None


class AIStatusOut(BaseModel):
    enabled: bool
    configured_provider: str
    effective_provider: str
    model: str
    fallback_model: str
    capabilities: list[str]
