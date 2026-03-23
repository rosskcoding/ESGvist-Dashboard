from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, Field


class WebhookEndpointCreate(BaseModel):
    url: AnyHttpUrl
    events: list[str] = Field(min_length=1)
    secret: str | None = Field(default=None, min_length=8, max_length=255)
    is_active: bool = True


class WebhookEndpointUpdate(BaseModel):
    url: AnyHttpUrl | None = None
    events: list[str] | None = None
    secret: str | None = Field(default=None, min_length=8, max_length=255)
    is_active: bool | None = None


class WebhookEndpointOut(BaseModel):
    id: int
    url: str
    events: list[str]
    is_active: bool
    secret_last4: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class WebhookEndpointCreateOut(WebhookEndpointOut):
    secret: str


class WebhookListOut(BaseModel):
    items: list[WebhookEndpointOut]
    total: int


class WebhookDeliveryOut(BaseModel):
    id: int
    event_type: str
    payload: dict
    status: str
    http_status: int | None = None
    response_body: str | None = None
    attempt: int
    max_attempts: int
    next_retry_at: datetime | None = None
    created_at: datetime | None = None
    delivered_at: datetime | None = None


class WebhookDeliveryListOut(BaseModel):
    items: list[WebhookDeliveryOut]
    total: int


class WebhookTestOut(BaseModel):
    delivery: WebhookDeliveryOut
