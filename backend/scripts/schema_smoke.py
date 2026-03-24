#!/usr/bin/env python
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.core.schema_runtime import get_schema_status
from app.db.models import Base

BACKEND_DIR = Path(__file__).resolve().parents[1]


async def _bootstrap_database(database_url: str) -> None:
    engine = create_async_engine(database_url, future=True)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()


def _run_cli(command: str, database_url: str) -> tuple[int, dict]:
    completed = subprocess.run(
        [sys.executable, "scripts/db_schema.py", command, "--database-url", database_url],
        cwd=BACKEND_DIR,
        text=True,
        capture_output=True,
        check=False,
    )
    if not completed.stdout.strip():
        raise RuntimeError(
            f"db_schema.py {command} returned no JSON payload. "
            f"stderr={completed.stderr.strip() or '<empty>'}"
        )
    return completed.returncode, json.loads(completed.stdout.strip())


async def _exercise_cli(database_url: str) -> None:
    check_exit_code, check_payload = _run_cli("check", database_url)
    if check_exit_code != 1:
        raise RuntimeError(f"Expected `check` to fail on unversioned DB, got {check_exit_code}")
    if not check_payload["is_bootstrapped"] or check_payload["is_current"]:
        raise RuntimeError(f"Unexpected `check` payload: {check_payload}")

    stamp_exit_code, stamp_payload = _run_cli("stamp-head", database_url)
    if stamp_exit_code != 0:
        raise RuntimeError(f"`stamp-head` failed with code {stamp_exit_code}: {stamp_payload}")
    if stamp_payload["current"] != stamp_payload["head"]:
        raise RuntimeError(f"`stamp-head` did not reach head: {stamp_payload}")

    current_exit_code, current_payload = _run_cli("current", database_url)
    if current_exit_code != 0:
        raise RuntimeError(f"`current` failed with code {current_exit_code}: {current_payload}")
    if not current_payload["is_current"] or current_payload["current"] != current_payload["head"]:
        raise RuntimeError(f"Unexpected `current` payload: {current_payload}")


async def _exercise_lifespan_auto_upgrade(database_url: str) -> None:
    previous_database_url = settings.database_url
    previous_auto_upgrade = settings.db_auto_upgrade
    previous_require_current = settings.db_require_current_revision
    previous_debug = settings.debug
    try:
        settings.database_url = database_url
        settings.db_auto_upgrade = True
        settings.db_require_current_revision = True
        settings.debug = False
        from app.main import create_app

        app = create_app()
        async with app.router.lifespan_context(app):
            status = await get_schema_status(database_url)
        if not status.is_current or not status.is_bootstrapped:
            raise RuntimeError(f"Startup auto-upgrade left schema stale: {status}")
    finally:
        settings.database_url = previous_database_url
        settings.db_auto_upgrade = previous_auto_upgrade
        settings.db_require_current_revision = previous_require_current
        settings.debug = previous_debug


async def _main() -> int:
    with tempfile.TemporaryDirectory(prefix="esgvist-schema-smoke-") as tmpdir:
        cli_database_url = f"sqlite+aiosqlite:///{Path(tmpdir) / 'cli-smoke.db'}"
        await _bootstrap_database(cli_database_url)
        await _exercise_cli(cli_database_url)

        lifespan_database_url = f"sqlite+aiosqlite:///{Path(tmpdir) / 'lifespan-smoke.db'}"
        await _bootstrap_database(lifespan_database_url)
        await _exercise_lifespan_auto_upgrade(lifespan_database_url)

        status = await get_schema_status(lifespan_database_url)
        print(
            json.dumps(
                {
                    "status": "ok",
                    "cli_database_url": cli_database_url,
                    "lifespan_database_url": lifespan_database_url,
                    "current": status.current_revisions,
                    "head": status.head_revisions,
                    "is_bootstrapped": status.is_bootstrapped,
                }
            )
        )
    return 0


def main() -> int:
    return asyncio.run(_main())


if __name__ == "__main__":
    raise SystemExit(main())
