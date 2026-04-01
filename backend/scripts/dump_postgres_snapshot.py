from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Iterable
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings


def quote_ident(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def format_array(values: Iterable[object]) -> str:
    parts: list[str] = []
    for value in values:
        if value is None:
            parts.append("NULL")
        elif isinstance(value, (list, tuple)):
            parts.append(format_array(value))
        elif isinstance(value, bool):
            parts.append("TRUE" if value else "FALSE")
        elif isinstance(value, (int, float, Decimal)):
            parts.append(str(value))
        elif isinstance(value, (datetime, date, time)):
            parts.append(sql_string(value.isoformat()))
        elif isinstance(value, (dict, UUID)):
            parts.append(sql_string(json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, dict) else str(value)))
        else:
            parts.append(sql_string(str(value)))
    return "ARRAY[" + ", ".join(parts) + "]"


def format_literal(value: object, data_type: str, udt_name: str) -> str:
    if value is None:
        return "NULL"
    if data_type == "ARRAY" and isinstance(value, (list, tuple)):
        return format_array(value)
    if data_type in {"json", "jsonb"}:
        return f"{sql_string(json.dumps(value, ensure_ascii=False, sort_keys=True))}::{data_type}"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    if isinstance(value, UUID):
        return sql_string(str(value))
    if isinstance(value, datetime):
        return sql_string(value.isoformat(sep=" "))
    if isinstance(value, (date, time)):
        return sql_string(value.isoformat())
    if isinstance(value, bytes):
        return f"'\\\\x{value.hex()}'::bytea"
    return sql_string(str(value))


async def fetch_tables(conn) -> list[str]:
    return (
        await conn.execute(
            text(
                """
                select table_name
                from information_schema.tables
                where table_schema = 'public' and table_type = 'BASE TABLE'
                order by table_name
                """
            )
        )
    ).scalars().all()


async def fetch_columns(conn, table_name: str) -> list[tuple[str, str, str]]:
    rows = (
        await conn.execute(
            text(
                """
                select column_name, data_type, udt_name
                from information_schema.columns
                where table_schema = 'public' and table_name = :table_name
                order by ordinal_position
                """
            ),
            {"table_name": table_name},
        )
    ).all()
    return [(row.column_name, row.data_type, row.udt_name) for row in rows]


async def fetch_primary_key_columns(conn, table_name: str) -> list[str]:
    rows = (
        await conn.execute(
            text(
                """
                select a.attname as column_name
                from pg_index i
                join pg_attribute a
                  on a.attrelid = i.indrelid
                 and a.attnum = any(i.indkey)
                where i.indrelid = (:table_name)::regclass
                  and i.indisprimary
                order by array_position(i.indkey, a.attnum)
                """
            ),
            {"table_name": f"public.{table_name}"},
        )
    ).all()
    return [row.column_name for row in rows]


async def fetch_serial_columns(conn, table_name: str) -> list[tuple[str, str]]:
    rows = (
        await conn.execute(
            text(
                """
                select
                  c.column_name,
                  pg_get_serial_sequence(format('%I.%I', c.table_schema, c.table_name), c.column_name) as sequence_name
                from information_schema.columns c
                where c.table_schema = 'public'
                  and c.table_name = :table_name
                  and pg_get_serial_sequence(format('%I.%I', c.table_schema, c.table_name), c.column_name) is not null
                order by c.ordinal_position
                """
            ),
            {"table_name": table_name},
        )
    ).all()
    return [(row.column_name, row.sequence_name) for row in rows]


async def dump_database(output_path: Path) -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    try:
        async with engine.connect() as conn:
            tables = await fetch_tables(conn)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with output_path.open("w", encoding="utf-8") as fh:
                fh.write("-- ESGVist PostgreSQL data snapshot\n")
                fh.write("-- Generated by backend/scripts/dump_postgres_snapshot.py\n")
                fh.write("BEGIN;\n")
                fh.write("SET session_replication_role = replica;\n\n")

                truncate_targets = ", ".join(f"public.{quote_ident(table)}" for table in tables)
                fh.write(f"TRUNCATE TABLE {truncate_targets} RESTART IDENTITY CASCADE;\n\n")

                for table_name in tables:
                    columns = await fetch_columns(conn, table_name)
                    column_names = [column_name for column_name, _data_type, _udt_name in columns]
                    pk_columns = await fetch_primary_key_columns(conn, table_name)
                    order_columns = pk_columns or column_names[:1]
                    order_clause = ", ".join(quote_ident(column_name) for column_name in order_columns)

                    rows = (
                        await conn.execute(
                            text(
                                f"SELECT * FROM public.{quote_ident(table_name)} ORDER BY {order_clause}"
                            )
                        )
                    ).mappings().all()

                    if not rows:
                        continue

                    fh.write(f"-- Table: {table_name}\n")
                    insert_columns = ", ".join(quote_ident(column_name) for column_name in column_names)
                    for row in rows:
                        values_sql = ", ".join(
                            format_literal(row[column_name], data_type, udt_name)
                            for column_name, data_type, udt_name in columns
                        )
                        fh.write(
                            f"INSERT INTO public.{quote_ident(table_name)} ({insert_columns}) VALUES ({values_sql});\n"
                        )
                    fh.write("\n")

                for table_name in tables:
                    for column_name, sequence_name in await fetch_serial_columns(conn, table_name):
                        fh.write(
                            "SELECT setval("
                            f"{sql_string(sequence_name)}, "
                            f"COALESCE((SELECT MAX({quote_ident(column_name)}) FROM public.{quote_ident(table_name)}), 1), "
                            "true);\n"
                        )
                fh.write("\nSET session_replication_role = DEFAULT;\n")
                fh.write("COMMIT;\n")
    finally:
        await engine.dispose()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a PostgreSQL data snapshot SQL file.")
    parser.add_argument("output_path", type=Path, help="Path to write the SQL snapshot.")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    asyncio.run(dump_database(args.output_path))
    print(f"Wrote snapshot to {args.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
