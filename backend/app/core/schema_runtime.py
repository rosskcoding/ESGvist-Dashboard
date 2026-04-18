from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.ext.asyncio import create_async_engine


BACKEND_DIR = Path(__file__).resolve().parents[2]
ALEMBIC_INI_PATH = BACKEND_DIR / "alembic.ini"
ALEMBIC_SCRIPT_PATH = BACKEND_DIR / "alembic"
REQUIRED_CORE_TABLES = (
    "users",
    "organizations",
    "role_bindings",
    "standards",
    "shared_elements",
    "reporting_projects",
)


@dataclass(frozen=True)
class SchemaStatus:
    current_revisions: tuple[str, ...]
    head_revisions: tuple[str, ...]
    version_table_present: bool
    missing_core_tables: tuple[str, ...] = ()

    @property
    def is_current(self) -> bool:
        return self.current_revisions == self.head_revisions

    @property
    def is_bootstrapped(self) -> bool:
        return not self.missing_core_tables


def _build_alembic_config(database_url: str) -> Config:
    config = Config(str(ALEMBIC_INI_PATH))
    config.set_main_option("script_location", str(ALEMBIC_SCRIPT_PATH))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def get_head_revisions(database_url: str) -> tuple[str, ...]:
    script = ScriptDirectory.from_config(_build_alembic_config(database_url))
    return tuple(sorted(script.get_heads()))


async def get_current_revisions(database_url: str) -> tuple[tuple[str, ...], bool]:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            def _load_revisions(sync_connection):
                inspector = sa.inspect(sync_connection)
                if "alembic_version" not in inspector.get_table_names():
                    return tuple(), False
                rows = sync_connection.execute(sa.text("SELECT version_num FROM alembic_version")).fetchall()
                return tuple(sorted(row[0] for row in rows if row[0])), True

            return await connection.run_sync(_load_revisions)
    finally:
        await engine.dispose()


async def get_schema_status(database_url: str) -> SchemaStatus:
    current_revisions, version_table_present = await get_current_revisions(database_url)
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            def _load_missing_core_tables(sync_connection):
                table_names = set(sa.inspect(sync_connection).get_table_names())
                return tuple(sorted(table for table in REQUIRED_CORE_TABLES if table not in table_names))

            missing_core_tables = await connection.run_sync(_load_missing_core_tables)
    finally:
        await engine.dispose()

    return SchemaStatus(
        current_revisions=current_revisions,
        head_revisions=get_head_revisions(database_url),
        version_table_present=version_table_present,
        missing_core_tables=missing_core_tables,
    )


def upgrade_database(database_url: str, revision: str = "heads") -> None:
    command.upgrade(_build_alembic_config(database_url), revision)


def stamp_database(database_url: str, revision: str = "heads") -> None:
    command.stamp(_build_alembic_config(database_url), revision)


async def upgrade_database_async(database_url: str, revision: str = "heads") -> None:
    await asyncio.to_thread(upgrade_database, database_url, revision)


async def stamp_database_async(database_url: str, revision: str = "heads") -> None:
    await asyncio.to_thread(stamp_database, database_url, revision)


async def ensure_database_schema(
    database_url: str,
    *,
    auto_upgrade: bool,
    require_current: bool,
) -> SchemaStatus | None:
    if not auto_upgrade and not require_current:
        return None

    status = await get_schema_status(database_url)
    if not status.is_bootstrapped:
        missing_tables = ", ".join(status.missing_core_tables)
        raise RuntimeError(
            "Database is missing required core tables. "
            f"Missing={missing_tables}. Bootstrap the base schema before applying runtime revisions."
        )
    if status.is_current:
        return status

    if auto_upgrade:
        await upgrade_database_async(database_url)
        status = await get_schema_status(database_url)
        if status.is_current:
            return status
        raise RuntimeError(
            "Database schema is still behind Alembic head after auto-upgrade. "
            f"Current={status.current_revisions or ('<none>',)} Head={status.head_revisions or ('<none>',)}"
        )

    if require_current:
        current = ", ".join(status.current_revisions) if status.current_revisions else "<none>"
        head = ", ".join(status.head_revisions) if status.head_revisions else "<none>"
        raise RuntimeError(
            "Database schema is not at Alembic head. "
            f"Current={current}; Head={head}. Run `python scripts/db_schema.py upgrade`."
        )

    return status
