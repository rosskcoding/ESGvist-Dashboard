import importlib.util
import json
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.db.models import Base
from app.main import create_app

# alembic may not be fully installed in test environments
try:
    from app.core.schema_runtime import (
        ensure_database_schema,
        get_current_revisions,
        get_head_revisions,
        get_schema_status,
    )

    _alembic_available = True
except ImportError:
    _alembic_available = False

pytestmark = pytest.mark.skipif(
    not _alembic_available,
    reason="alembic not installed or broken",
)


def _load_db_schema_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "db_schema.py"
    spec = importlib.util.spec_from_file_location("db_schema_script", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _bootstrap_database(database_url: str) -> None:
    engine = create_async_engine(database_url, future=True)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_get_schema_status_reports_bootstrapped_unversioned_database(tmp_path):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'schema-status.db'}"
    await _bootstrap_database(database_url)

    status = await get_schema_status(database_url)

    assert status.version_table_present is False
    assert status.is_bootstrapped is True
    assert status.is_current is False
    assert status.current_revisions == ()
    assert status.head_revisions == get_head_revisions(database_url)


@pytest.mark.asyncio
async def test_db_schema_check_and_stamp_head_roundtrip(tmp_path, capsys):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'db-schema-roundtrip.db'}"
    await _bootstrap_database(database_url)
    db_schema = _load_db_schema_module()

    check_exit_code = await db_schema._run("check", database_url)
    check_payload = json.loads(capsys.readouterr().out.strip())

    assert check_exit_code == 1
    assert check_payload["is_current"] is False
    assert check_payload["is_bootstrapped"] is True
    assert check_payload["version_table_present"] is False

    stamp_exit_code = await db_schema._run("stamp-head", database_url)
    stamp_payload = json.loads(capsys.readouterr().out.strip())

    assert stamp_exit_code == 0
    assert stamp_payload["status"] == "stamped"
    assert stamp_payload["current"] == stamp_payload["head"]
    assert stamp_payload["is_bootstrapped"] is True

    current_exit_code = await db_schema._run("current", database_url)
    current_payload = json.loads(capsys.readouterr().out.strip())

    assert current_exit_code == 0
    assert current_payload["is_current"] is True
    assert current_payload["current"] == current_payload["head"]
    assert current_payload["version_table_present"] is True


@pytest.mark.asyncio
async def test_ensure_database_schema_rejects_unversioned_bootstrapped_database(tmp_path):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'ensure-rejects.db'}"
    await _bootstrap_database(database_url)

    with pytest.raises(RuntimeError, match="Database schema is not at Alembic head"):
        await ensure_database_schema(
            database_url,
            auto_upgrade=False,
            require_current=True,
        )


@pytest.mark.asyncio
async def test_create_app_lifespan_rejects_outdated_schema(tmp_path, monkeypatch):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'lifespan-rejects.db'}"
    await _bootstrap_database(database_url)
    monkeypatch.setattr(settings, "database_url", database_url)
    monkeypatch.setattr(settings, "db_auto_upgrade", False)
    monkeypatch.setattr(settings, "db_require_current_revision", True)

    app = create_app()

    with pytest.raises(RuntimeError, match="Database schema is not at Alembic head"):
        async with app.router.lifespan_context(app):
            pass


@pytest.mark.asyncio
async def test_create_app_lifespan_auto_upgrades_outdated_schema(tmp_path, monkeypatch):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'lifespan-upgrades.db'}"
    await _bootstrap_database(database_url)
    monkeypatch.setattr(settings, "database_url", database_url)
    monkeypatch.setattr(settings, "db_auto_upgrade", True)
    monkeypatch.setattr(settings, "db_require_current_revision", True)

    app = create_app()

    async with app.router.lifespan_context(app):
        status = await get_schema_status(database_url)
        current_revisions, version_table_present = await get_current_revisions(database_url)

    assert status.is_current is True
    assert status.is_bootstrapped is True
    assert version_table_present is True
    assert current_revisions == status.head_revisions


@pytest.mark.asyncio
async def test_ensure_database_schema_rejects_unbootstrapped_database(tmp_path):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'empty.db'}"
    engine = create_async_engine(database_url, future=True)
    try:
        async with engine.begin() as connection:
            await connection.execute(sa.text("SELECT 1"))
    finally:
        await engine.dispose()

    with pytest.raises(RuntimeError, match="missing required core tables"):
        await ensure_database_schema(
            database_url,
            auto_upgrade=True,
            require_current=True,
        )
