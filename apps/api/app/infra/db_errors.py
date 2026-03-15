"""
Helpers for extracting Postgres error details from SQLAlchemy exceptions.

We keep these utilities small and dependency-free so they can be used in:
- global FastAPI exception handlers
- request-level retry logic (e.g. version-number races)
"""

from __future__ import annotations

import re

from sqlalchemy.exc import IntegrityError


def pg_sqlstate(exc: IntegrityError) -> str | None:
    """Return Postgres SQLSTATE if available (e.g. 23505 for unique violation)."""
    orig = getattr(exc, "orig", None)
    return getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)


def pg_constraint_name(exc: IntegrityError) -> str | None:
    """Return the violated constraint/index name, when discoverable."""
    orig = getattr(exc, "orig", None)

    name = getattr(orig, "constraint_name", None)
    if isinstance(name, str) and name.strip():
        return name.strip()

    # Fallback: asyncpg and other DBAPIs embed the constraint name in the error message.
    msg = str(orig) if orig is not None else str(exc)
    m = re.search(r'constraint\s+"([^"]+)"', msg, flags=re.IGNORECASE)
    if m:
        return m.group(1)
    return None

