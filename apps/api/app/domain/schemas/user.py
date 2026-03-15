"""
User schemas.
"""

import re
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, Field, field_validator

from .common import BaseSchema, TimestampSchema
from .company import UserCompanyDTO


def validate_email(v: str) -> str:
    """
    Validate email address.

    Accepts all valid email formats including test/dev domains (.test, .local, etc.)
    which are rejected by Pydantic's strict EmailStr validator.
    """
    if not v or "@" not in v:
        raise ValueError("Invalid email address")
    # Basic email validation - just check format
    if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v):
        raise ValueError("Invalid email address format")
    return v.lower()


# Custom email type that accepts test domains
Email = Annotated[str, AfterValidator(validate_email)]


class UserBase(BaseSchema):
    """Base user fields."""

    email: Email
    full_name: str = Field(min_length=1, max_length=200)
    locale_scopes: list[str] | None = Field(
        default=None,
        description="Locale restrictions. None = all locales.",
    )

    @field_validator("locale_scopes")
    @classmethod
    def validate_locale_scopes(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            valid_locales = {"ru", "en", "kk", "de", "fr", "ar", "es", "nl", "it"}
            invalid = set(v) - valid_locales
            if invalid:
                raise ValueError(f"Invalid locales: {invalid}")
        return v


class UserCreate(UserBase):
    """Schema for creating a user."""

    password: str = Field(min_length=12, max_length=128)
    is_superuser: bool = False

    @field_validator("password")
    @classmethod
    def validate_password_policy(cls, v: str) -> str:
        """
        Password policy (docs/product/spec/12_IAM.md):
        - min_length: 12
        - require uppercase, lowercase, digit, special
        """
        if len(v) < 12:
            raise ValueError("Password must be at least 12 characters long")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[^A-Za-z0-9]", v):
            raise ValueError("Password must contain at least one special character")
        return v


class UserUpdate(BaseSchema):
    """Schema for updating a user."""

    email: Email | None = None
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    locale_scopes: list[str] | None = None
    is_active: bool | None = None
    is_superuser: bool | None = None
    password: str | None = Field(default=None, min_length=12, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password_policy_optional(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return UserCreate.validate_password_policy(v)


class UserDTO(UserBase, TimestampSchema):
    """User data transfer object (response)."""

    user_id: UUID
    is_active: bool
    is_superuser: bool = False
    companies: list[UserCompanyDTO] = Field(default_factory=list)


class UserInDB(UserDTO):
    """User with password hash (internal use)."""

    password_hash: str
