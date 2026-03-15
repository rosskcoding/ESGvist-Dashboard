"""
Centralized exception handlers for the FastAPI app.

Keep handlers conservative: return useful, user-facing messages without leaking
raw database internals.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api.errors import CompanyContextRequiredError
from app.infra.db_errors import pg_constraint_name, pg_sqlstate

# Postgres SQLSTATE codes (common ones we care about).
_PG_UNIQUE_VIOLATION = "23505"
_PG_FOREIGN_KEY_VIOLATION = "23503"
_PG_NOT_NULL_VIOLATION = "23502"
_PG_CHECK_VIOLATION = "23514"


def _pg_sqlstate(exc: IntegrityError) -> str | None:
    return pg_sqlstate(exc)


def _pg_constraint_name(exc: IntegrityError) -> str | None:
    return pg_constraint_name(exc)


# Known unique constraints / indexes mapped to user-facing messages.
_UNIQUE_CONFLICT_MESSAGES: dict[str, str] = {
    # ESG dimensions + metrics
    "uq_esg_metrics_company_code": "Metric code already exists",
    "uq_esg_entities_company_code": "Entity code already exists",
    "uq_esg_locations_company_code": "Location code already exists",
    "uq_esg_segments_company_code": "Segment code already exists",
    # ESG facts
    "uq_esg_facts_company_logical_version": "Fact version conflict. Please retry.",
    "uq_esg_facts_company_published_logical_key": "A published fact already exists for this logical key",
}


async def integrity_error_handler(_request: Request, exc: IntegrityError) -> JSONResponse:
    """
    Translate DB integrity errors into user-facing API errors.

    This improves UX for forms (metrics/dimensions) and provides stable 409/422
    responses instead of leaking raw DB errors.
    """

    sqlstate = _pg_sqlstate(exc)
    constraint = _pg_constraint_name(exc)

    detail: str
    code: str
    http_status: int

    if sqlstate == _PG_UNIQUE_VIOLATION:
        http_status = status.HTTP_409_CONFLICT
        code = "unique_violation"
        detail = _UNIQUE_CONFLICT_MESSAGES.get(constraint or "", "Conflict: duplicate value")
    elif sqlstate == _PG_FOREIGN_KEY_VIOLATION:
        http_status = status.HTTP_409_CONFLICT
        code = "foreign_key_violation"
        detail = "Conflict: invalid reference"
    elif sqlstate == _PG_NOT_NULL_VIOLATION:
        http_status = status.HTTP_422_UNPROCESSABLE_ENTITY
        code = "not_null_violation"
        detail = "Validation failed: missing required value"
    elif sqlstate == _PG_CHECK_VIOLATION:
        http_status = status.HTTP_422_UNPROCESSABLE_ENTITY
        code = "check_violation"
        detail = "Validation failed"
    else:
        # Conservative fallback: still treat as conflict, but avoid leaking details.
        http_status = status.HTTP_409_CONFLICT
        code = "integrity_error"
        detail = "Conflict"

    # Minimal structured payload; keep the public surface stable.
    payload: dict[str, Any] = {"detail": detail}
    # Include machine-readable info for debugging/clients without exposing raw DB text.
    payload["error"] = {"code": code, "constraint": constraint, "sqlstate": sqlstate}
    return JSONResponse(status_code=http_status, content=payload)


async def company_context_required_handler(_request: Request, exc: CompanyContextRequiredError) -> JSONResponse:
    """
    Contract:
    {
      "error": "company_context_required",
      "message": "Provide company_id",
      "hint": "Add ?company_id=...",
      "companies": [{"id":"...","name":"..."}]
    }
    """
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "error": "company_context_required",
            "message": "Provide company_id",
            "hint": "Add ?company_id=...",
            "companies": [{"id": str(c.id), "name": c.name} for c in (exc.companies or [])],
        },
    )
