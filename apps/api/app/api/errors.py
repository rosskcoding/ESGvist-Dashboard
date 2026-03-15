"""
API-level domain errors (non-HTTPException) that get translated by exception handlers.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CompanySummary:
    id: UUID
    name: str


@dataclass
class CompanyContextRequiredError(Exception):
    """
    Raised when the request is company-scoped but the user context is ambiguous
    (e.g. more than one active membership and no company_id provided).
    """

    companies: list[CompanySummary]
