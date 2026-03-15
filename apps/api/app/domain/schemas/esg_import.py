"""
ESG Fact bulk import schemas.

No new DB entities: preview/confirm are purely request/response objects.
"""

from typing import Literal

from pydantic import Field

from .common import BaseSchema


class EsgFactImportRowErrorDTO(BaseSchema):
    row_number: int = Field(ge=1)
    message: str = Field(min_length=1, max_length=2000)
    metric_code: str | None = None
    logical_key_hash: str | None = None


class EsgFactImportRowPreviewDTO(BaseSchema):
    row_number: int = Field(ge=1)
    action: Literal["create", "skip", "error"]
    message: str | None = None
    metric_code: str | None = None
    logical_key_hash: str | None = None


class EsgFactImportPreviewDTO(BaseSchema):
    total_rows: int = Field(ge=0)
    create_rows: int = Field(ge=0)
    skip_rows: int = Field(ge=0)
    error_rows: int = Field(ge=0)
    rows: list[EsgFactImportRowPreviewDTO] = Field(default_factory=list)
    errors: list[EsgFactImportRowErrorDTO] = Field(default_factory=list)


class EsgFactImportConfirmDTO(BaseSchema):
    total_rows: int = Field(ge=0)
    created: int = Field(ge=0)
    skipped: int = Field(ge=0)
    error_rows: int = Field(ge=0)
    errors: list[EsgFactImportRowErrorDTO] = Field(default_factory=list)

