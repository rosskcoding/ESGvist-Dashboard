#!/usr/bin/env python
from __future__ import annotations

import argparse
import asyncio
import json

from app.core.config import settings
from app.core.schema_runtime import (
    get_schema_status,
    stamp_database_async,
    upgrade_database_async,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage ESGvist database schema revisions.")
    parser.add_argument(
        "command",
        choices=["check", "current", "upgrade", "stamp-head"],
        help="Schema operation to perform.",
    )
    parser.add_argument(
        "--database-url",
        default=settings.database_url,
        help="Override DATABASE_URL for this command.",
    )
    return parser


async def _run(command: str, database_url: str) -> int:
    if command == "upgrade":
        await upgrade_database_async(database_url)
        status = await get_schema_status(database_url)
        print(
            json.dumps(
                {
                    "status": "upgraded",
                    "current": status.current_revisions,
                    "head": status.head_revisions,
                    "missing_core_tables": status.missing_core_tables,
                    "is_bootstrapped": status.is_bootstrapped,
                }
            )
        )
        return 0 if status.is_bootstrapped else 1

    if command == "stamp-head":
        await stamp_database_async(database_url)
        status = await get_schema_status(database_url)
        print(
            json.dumps(
                {
                    "status": "stamped",
                    "current": status.current_revisions,
                    "head": status.head_revisions,
                    "missing_core_tables": status.missing_core_tables,
                    "is_bootstrapped": status.is_bootstrapped,
                }
            )
        )
        return 0 if status.is_bootstrapped else 1

    status = await get_schema_status(database_url)
    payload = {
        "current": status.current_revisions,
        "head": status.head_revisions,
        "is_current": status.is_current,
        "version_table_present": status.version_table_present,
        "missing_core_tables": status.missing_core_tables,
        "is_bootstrapped": status.is_bootstrapped,
    }
    print(json.dumps(payload))
    if command == "check":
        return 0 if status.is_current and status.is_bootstrapped else 1
    return 0


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    return asyncio.run(_run(args.command, args.database_url))


if __name__ == "__main__":
    raise SystemExit(main())
