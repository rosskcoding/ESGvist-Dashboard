from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, Field


class SSOProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    provider_type: str = Field(pattern=r"^(oauth2|saml2)$")
    auth_url: AnyHttpUrl
    issuer: str | None = None
    client_id: str = Field(min_length=1, max_length=255)
    client_secret: str | None = Field(default=None, min_length=1, max_length=255)
    redirect_uri: AnyHttpUrl | None = None
    entity_id: str | None = None
    is_active: bool = True
    auto_provision: bool = True
    default_role: str = Field(pattern=r"^(admin|esg_manager|reviewer|collector|auditor)$")


class SSOProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    auth_url: AnyHttpUrl | None = None
    issuer: str | None = None
    client_id: str | None = Field(default=None, min_length=1, max_length=255)
    client_secret: str | None = Field(default=None, min_length=1, max_length=255)
    redirect_uri: AnyHttpUrl | None = None
    entity_id: str | None = None
    is_active: bool | None = None
    auto_provision: bool | None = None
    default_role: str | None = Field(default=None, pattern=r"^(admin|esg_manager|reviewer|collector|auditor)$")


class SSOProviderOut(BaseModel):
    id: int
    name: str
    provider_type: str
    auth_url: str
    issuer: str | None = None
    client_id: str
    redirect_uri: str | None = None
    entity_id: str | None = None
    is_active: bool
    auto_provision: bool
    default_role: str
    secret_configured: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SSOProviderListOut(BaseModel):
    items: list[SSOProviderOut]
    total: int


class SSOProviderPublicOut(BaseModel):
    id: int
    name: str
    provider_type: str


class SSOProviderPublicListOut(BaseModel):
    items: list[SSOProviderPublicOut]
    total: int


class SSOStartRequest(BaseModel):
    organization_id: int


class SSOStartOut(BaseModel):
    provider_id: int
    organization_id: int
    provider_type: str
    state: str
    auth_url: str
    expires_at: datetime


class SSOCallbackRequest(BaseModel):
    state: str
    email: str
    full_name: str
    external_subject: str
