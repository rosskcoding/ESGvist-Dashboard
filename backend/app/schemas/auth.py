from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RoleBindingOut(BaseModel):
    id: int
    role: str
    scope_type: str
    scope_id: int | None

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    is_active: bool
    roles: list[RoleBindingOut] = []

    model_config = {"from_attributes": True}


class InvitationCreateRequest(BaseModel):
    email: EmailStr
    role: Literal["collector", "reviewer", "esg_manager", "admin", "auditor"]
    message: str | None = None


class OrgUserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: Literal["collector", "reviewer", "esg_manager", "admin", "auditor"]
    status: Literal["active", "inactive"]
    joined_date: str | None = None


class PendingInvitationOut(BaseModel):
    id: int
    email: str
    role: Literal["collector", "reviewer", "esg_manager", "admin", "auditor"]
    status: str
    invited_at: str | None = None
    invited_by: str
    expires_at: str | None = None


class OrganizationUsersOut(BaseModel):
    users: list[OrgUserOut]
    pending_invitations: list[PendingInvitationOut]


class UserRoleUpdateRequest(BaseModel):
    role: Literal["collector", "reviewer", "esg_manager", "admin", "auditor"]


class UserStatusUpdateRequest(BaseModel):
    status: Literal["active", "inactive"]


class UserRoleBindingCreateRequest(BaseModel):
    role: Literal["platform_admin", "admin", "esg_manager", "reviewer", "collector", "auditor"]
    scope_type: Literal["platform", "organization"]
    scope_id: int | None = None


class OrganizationAuthSettingsUpdate(BaseModel):
    allow_password_login: bool | None = None
    allow_sso_login: bool | None = None
    enforce_sso: bool | None = None


class OrganizationAuthSettingsOut(BaseModel):
    organization_id: int
    allow_password_login: bool
    allow_sso_login: bool
    enforce_sso: bool
    active_sso_provider_count: int
    sso_available: bool
