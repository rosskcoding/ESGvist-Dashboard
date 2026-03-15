"""
Dataset schemas for API requests/responses.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# === Column Schema ===

class ColumnSchema(BaseModel):
    """
    Dataset column definition.

    Used in schema_json.
    """

    key: str = Field(
        min_length=1,
        max_length=100,
        description="Column identifier (e.g., 'revenue', 'year')",
    )
    type: Literal["text", "number", "percent", "currency", "date"] = Field(
        default="text",
        description="Data type for parsing and formatting",
    )
    unit: str | None = Field(
        default=None,
        max_length=50,
        description="Unit of measurement (e.g., 'tCO2e', '₸', '%')",
    )
    format: dict | None = Field(
        default=None,
        description="Format options: {decimals?, currency_code?, date_format?}",
    )
    nullable: bool = Field(
        default=True,
        description="Can this column contain null values?",
    )


# === Dataset Schemas ===

class DatasetCreate(BaseModel):
    """Request schema for creating a dataset."""

    name: str = Field(
        min_length=1,
        max_length=200,
        description="Human-readable name",
    )
    description: str | None = Field(
        default=None,
        max_length=5000,
        description="Optional description",
    )
    schema_json: dict = Field(
        default_factory=lambda: {"columns": []},
        description="Column schema: {columns: [ColumnSchema, ...]}",
    )
    rows_json: list = Field(
        default_factory=list,
        max_length=10000,
        description="Array of rows: [[val1, val2, ...], ...]",
    )
    meta_json: dict = Field(
        default_factory=dict,
        description="Metadata: {source?, period?, currency?, notes?}",
    )

    @field_validator("schema_json")
    @classmethod
    def validate_schema(cls, v: dict) -> dict:
        """Validate schema_json structure."""
        if "columns" not in v:
            raise ValueError("schema_json must contain 'columns' key")
        if not isinstance(v["columns"], list):
            raise ValueError("schema_json.columns must be a list")
        # Validate each column
        for col in v["columns"]:
            ColumnSchema.model_validate(col)
        return v

    @field_validator("rows_json")
    @classmethod
    def validate_rows(cls, v: list) -> list:
        """Validate rows_json structure."""
        if not isinstance(v, list):
            raise ValueError("rows_json must be a list")
        for row in v:
            if not isinstance(row, list):
                raise ValueError("Each row must be a list")
        return v


class DatasetUpdate(BaseModel):
    """Request schema for updating a dataset."""

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    description: str | None = Field(
        default=None,
        max_length=5000,
    )
    schema_json: dict | None = Field(
        default=None,
        description="Column schema update",
    )
    rows_json: list | None = Field(
        default=None,
        max_length=10000,
        description="Data rows update",
    )
    meta_json: dict | None = Field(
        default=None,
        description="Metadata update",
    )

    @field_validator("schema_json")
    @classmethod
    def validate_schema(cls, v: dict | None) -> dict | None:
        """Validate schema_json if provided."""
        if v is None:
            return v
        if "columns" not in v:
            raise ValueError("schema_json must contain 'columns' key")
        for col in v["columns"]:
            ColumnSchema.model_validate(col)
        return v

    @field_validator("rows_json")
    @classmethod
    def validate_rows(cls, v: list | None) -> list | None:
        """Validate rows_json if provided."""
        if v is None:
            return v
        for row in v:
            if not isinstance(row, list):
                raise ValueError("Each row must be a list")
        return v


class DatasetResponse(BaseModel):
    """Response schema for dataset."""

    dataset_id: UUID
    company_id: UUID
    name: str
    description: str | None
    schema_json: dict
    rows_json: list
    meta_json: dict
    current_revision: int
    created_by: UUID | None
    updated_by: UUID | None
    is_deleted: bool
    created_at_utc: datetime
    updated_at_utc: datetime

    model_config = {"from_attributes": True}


class DatasetListItem(BaseModel):
    """Lightweight dataset item for list views."""

    dataset_id: UUID
    company_id: UUID
    name: str
    description: str | None
    current_revision: int
    row_count: int = Field(description="Number of rows")
    column_count: int = Field(description="Number of columns")
    created_at_utc: datetime
    updated_at_utc: datetime

    model_config = {"from_attributes": True}


# === Dataset Revision Schemas ===

class DatasetRevisionCreate(BaseModel):
    """Request schema for creating a revision snapshot."""

    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Why this revision is being created",
    )


class DatasetRevisionResponse(BaseModel):
    """Response schema for dataset revision."""

    revision_id: UUID
    dataset_id: UUID
    revision_number: int
    schema_json: dict
    rows_json: list
    meta_json: dict
    created_at_utc: datetime
    created_by: UUID | None
    reason: str | None

    model_config = {"from_attributes": True}


# === Import/Export Schemas ===

class DatasetImportPreview(BaseModel):
    """Preview result from CSV/XLSX import."""

    detected_columns: list[ColumnSchema] = Field(
        description="Auto-detected column schema",
    )
    preview_rows: list[list] = Field(
        max_length=50,
        description="First 50 rows for preview",
    )
    total_rows: int = Field(
        description="Total rows in file",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Warnings about data quality, parsing issues, etc.",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Errors that will prevent import",
    )


class DatasetImportConfirm(BaseModel):
    """Confirm import with optional schema adjustments."""

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    schema_json: dict = Field(
        description="Final column schema (can override detected)",
    )
    skip_rows: int = Field(
        default=0,
        ge=0,
        description="Number of rows to skip from start",
    )
    max_rows: int | None = Field(
        default=None,
        ge=1,
        description="Maximum rows to import (null = all)",
    )


class DatasetExportOptions(BaseModel):
    """Options for dataset export."""

    format: Literal["csv", "xlsx", "json"] = Field(
        default="csv",
        description="Export format",
    )
    include_metadata: bool = Field(
        default=True,
        description="Include meta_json in export (for JSON)",
    )
    revision_id: UUID | None = Field(
        default=None,
        description="Export specific revision (null = current)",
    )

