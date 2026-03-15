"""
Unit tests for Postgres error helpers.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from app.infra.db_errors import pg_constraint_name, pg_sqlstate


class _Orig(Exception):
    pass


def test_pg_sqlstate_prefers_orig_sqlstate() -> None:
    orig = _Orig("boom")
    orig.sqlstate = "23505"  # type: ignore[attr-defined]
    exc = IntegrityError("stmt", {}, orig)
    assert pg_sqlstate(exc) == "23505"


def test_pg_constraint_name_uses_orig_constraint_name() -> None:
    orig = _Orig("boom")
    orig.constraint_name = "uq_test_constraint"  # type: ignore[attr-defined]
    exc = IntegrityError("stmt", {}, orig)
    assert pg_constraint_name(exc) == "uq_test_constraint"


def test_pg_constraint_name_parses_from_message() -> None:
    orig = _Orig('duplicate key value violates unique constraint "uq_esg_metrics_company_code"')
    exc = IntegrityError("stmt", {}, orig)
    assert pg_constraint_name(exc) == "uq_esg_metrics_company_code"

