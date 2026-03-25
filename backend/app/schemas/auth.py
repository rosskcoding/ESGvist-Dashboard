from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    totp_code: str | None = None
    backup_code: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


class TokenResponse(BaseModel):
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    session_mode: Literal["cookie", "token"] = "token"


class AuthSessionOut(BaseModel):
    id: int
    created_at: datetime
    expires_at: datetime
    last_used_at: datetime | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    is_current: bool = False


class AuthSessionListOut(BaseModel):
    items: list[AuthSessionOut]
    total: int


class AuthSessionRevokeOut(BaseModel):
    session_id: int
    revoked: bool
    is_current: bool = False


class LogoutAllOut(BaseModel):
    revoked_sessions: int


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
    organization_name: str | None = None
    roles: list[RoleBindingOut] = []

    model_config = {"from_attributes": True}


class UserProfileUpdateRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


class InvitationCreateRequest(BaseModel):
    email: EmailStr
    role: Literal["collector", "reviewer", "esg_manager", "admin", "auditor"]
    message: str | None = None


class OrgUserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: Literal["collector", "reviewer", "esg_manager", "admin", "auditor"]
    roles: list[Literal["collector", "reviewer", "esg_manager", "admin", "auditor"]] = Field(
        default_factory=list
    )
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
    role: Literal[
        "platform_admin",
        "framework_admin",
        "admin",
        "esg_manager",
        "reviewer",
        "collector",
        "auditor",
    ]
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


class TwoFactorStatusOut(BaseModel):
    enabled: bool
    pending_setup: bool
    confirmed_at: str | None = None
    backup_codes_remaining: int = 0


class TwoFactorSetupOut(BaseModel):
    secret: str
    otpauth_uri: str
    backup_codes: list[str]


class TwoFactorEnableRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class TwoFactorDisableRequest(BaseModel):
    code: str | None = None
    backup_code: str | None = None


class OrganizationSettingsOut(BaseModel):
    id: int
    name: str
    legal_name: str | None = None
    registration_number: str | None = None
    country: str | None = None
    jurisdiction: str | None = None
    industry: str | None = None
    currency: str
    reporting_year: int | None = None
    default_standards: list[str] = Field(default_factory=list)
    consolidation_approach: str | None = None
    ghg_scope_approach: str | None = None
    logo_url: str | None = None
    default_boundary_id: int | None = None


class OrganizationSettingsUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=500)
    legal_name: str | None = None
    registration_number: str | None = None
    country: str | None = None
    jurisdiction: str | None = None
    industry: str | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=10)
    reporting_year: int | None = None
    default_standards: list[str] | None = None
    consolidation_approach: str | None = None
    ghg_scope_approach: str | None = None
    default_boundary_id: int | None = None
