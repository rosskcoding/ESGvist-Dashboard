from __future__ import annotations

import asyncio
import os

import asyncpg


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@127.0.0.1:5432/esgvist",
).replace("+asyncpg", "")
PROJECT_ID = int(os.getenv("PROJECT_ID", "6"))


STANDARD_DEFS = {
    "GRI 306": {
        "name": "Waste 2020",
    },
    "GRI 303": {
        "name": "Water and Effluents 2018",
    },
    "ESRS E2": {
        "name": "Pollution",
    },
    "ESRS E3": {
        "name": "Water and marine resources",
    },
}


FRAMEWORK_MAPPINGS = [
    {
        "shared_code": "BPDS_ENVIRONMENT_SPILLS_LOSS_OF_PRIMARY_CONTAINMENT",
        "frameworks": [
            {
                "standard_code": "GRI 306",
                "disclosure_code": "306-3",
                "disclosure_title": "Significant spills",
            },
            {
                "standard_code": "ESRS E2",
                "disclosure_code": "E2-4",
                "disclosure_title": "Pollution incidents and emergency events",
            },
        ],
    },
    {
        "shared_code": "BPDS_ENVIRONMENT_SPILLS_OIL_SPILLS_NUMBER_1BBL",
        "frameworks": [
            {
                "standard_code": "GRI 306",
                "disclosure_code": "306-3",
                "disclosure_title": "Significant spills",
            },
            {
                "standard_code": "ESRS E2",
                "disclosure_code": "E2-4",
                "disclosure_title": "Pollution incidents and emergency events",
            },
        ],
    },
    {
        "shared_code": "BPDS_ENVIRONMENT_SPILLS_OIL_SPILLS_VOLUME",
        "frameworks": [
            {
                "standard_code": "GRI 306",
                "disclosure_code": "306-3",
                "disclosure_title": "Significant spills",
            },
            {
                "standard_code": "ESRS E2",
                "disclosure_code": "E2-4",
                "disclosure_title": "Pollution incidents and emergency events",
            },
        ],
    },
    {
        "shared_code": "BPDS_ENVIRONMENT_WATER_TOTAL_FRESHWATER_WITHDRAWAL",
        "frameworks": [
            {
                "standard_code": "GRI 303",
                "disclosure_code": "303-3",
                "disclosure_title": "Water withdrawal",
            },
            {
                "standard_code": "ESRS E3",
                "disclosure_code": "E3-4",
                "disclosure_title": "Water withdrawal and consumption",
            },
        ],
    },
    {
        "shared_code": "BPDS_ENVIRONMENT_WATER_TOTAL_FRESHWATER_WITHDRAWAL_EXPLORATION_PRODUCTION_AND_LNG",
        "frameworks": [
            {
                "standard_code": "GRI 303",
                "disclosure_code": "303-3",
                "disclosure_title": "Water withdrawal",
            },
            {
                "standard_code": "ESRS E3",
                "disclosure_code": "E3-4",
                "disclosure_title": "Water withdrawal and consumption",
            },
        ],
    },
]


async def ensure_standard(conn: asyncpg.Connection, code: str, name: str) -> int:
    existing = await conn.fetchrow(
        """
        select id
        from standards
        where code = $1
        """,
        code,
    )
    if existing:
        return existing["id"]

    return await conn.fetchval(
        """
        insert into standards (code, name, is_active)
        values ($1, $2, true)
        returning id
        """,
        code,
        name,
    )


async def ensure_project_standard(
    conn: asyncpg.Connection,
    *,
    project_id: int,
    standard_id: int,
) -> None:
    existing = await conn.fetchval(
        """
        select id
        from reporting_project_standards
        where reporting_project_id = $1
          and standard_id = $2
        """,
        project_id,
        standard_id,
    )
    if existing:
        return

    await conn.execute(
        """
        insert into reporting_project_standards (
          reporting_project_id,
          standard_id,
          is_base_standard
        )
        values ($1, $2, false)
        """,
        project_id,
        standard_id,
    )


async def ensure_disclosure_requirement(
    conn: asyncpg.Connection,
    *,
    standard_id: int,
    code: str,
    title: str,
) -> int:
    existing = await conn.fetchrow(
        """
        select id
        from disclosure_requirements
        where standard_id = $1
          and code = $2
        """,
        standard_id,
        code,
    )
    if existing:
        return existing["id"]

    max_sort_order = await conn.fetchval(
        """
        select coalesce(max(sort_order), 0)
        from disclosure_requirements
        where standard_id = $1
        """,
        standard_id,
    )

    return await conn.fetchval(
        """
        insert into disclosure_requirements (
          standard_id,
          section_id,
          code,
          title,
          description,
          requirement_type,
          mandatory_level,
          applicability_rule,
          sort_order
        )
        values ($1, null, $2, $3, $4, 'quantitative', 'mandatory', null, $5)
        returning id
        """,
        standard_id,
        code,
        title,
        f"Demo framework mapping for {title}",
        max_sort_order + 1,
    )


async def fetch_import_item_source(
    conn: asyncpg.Connection,
    *,
    shared_code: str,
) -> asyncpg.Record:
    row = await conn.fetchrow(
        """
        select
          se.id as shared_element_id,
          se.name as shared_element_name,
          coalesce(ri.value_type, se.default_value_type, 'number') as value_type,
          ri.unit_code,
          ri.requires_evidence
        from shared_elements se
        left join requirement_items ri
          on ri.item_code = se.code
        where se.code = $1
        order by ri.id nulls last
        limit 1
        """,
        shared_code,
    )
    if row is None:
        raise RuntimeError(f"Shared element not found for code: {shared_code}")
    return row


async def ensure_requirement_item(
    conn: asyncpg.Connection,
    *,
    disclosure_requirement_id: int,
    shared_code: str,
    shared_name: str,
    value_type: str,
    unit_code: str | None,
    requires_evidence: bool,
) -> int:
    existing = await conn.fetchrow(
        """
        select id
        from requirement_items
        where disclosure_requirement_id = $1
          and item_code = $2
        """,
        disclosure_requirement_id,
        shared_code,
    )
    if existing:
        return existing["id"]

    max_sort_order = await conn.fetchval(
        """
        select coalesce(max(sort_order), 0)
        from requirement_items
        where disclosure_requirement_id = $1
        """,
        disclosure_requirement_id,
    )

    return await conn.fetchval(
        """
        insert into requirement_items (
          disclosure_requirement_id,
          parent_item_id,
          item_code,
          name,
          description,
          item_type,
          value_type,
          unit_code,
          is_required,
          requires_evidence,
          cardinality_min,
          cardinality_max,
          granularity_rule,
          validation_rule,
          sort_order,
          version,
          is_current,
          valid_from,
          valid_to
        )
        values (
          $1,
          null,
          $2,
          $3,
          $4,
          'metric',
          $5,
          $6,
          true,
          $7,
          1,
          1,
          null,
          null,
          $8,
          1,
          true,
          null,
          null
        )
        returning id
        """,
        disclosure_requirement_id,
        shared_code,
        shared_name,
        shared_name,
        value_type,
        unit_code,
        requires_evidence,
        max_sort_order + 1,
    )


async def ensure_mapping(
    conn: asyncpg.Connection,
    *,
    requirement_item_id: int,
    shared_element_id: int,
) -> None:
    existing = await conn.fetchval(
        """
        select id
        from requirement_item_shared_elements
        where requirement_item_id = $1
          and shared_element_id = $2
          and version = 1
        """,
        requirement_item_id,
        shared_element_id,
    )
    if existing:
        return

    await conn.execute(
        """
        insert into requirement_item_shared_elements (
          requirement_item_id,
          shared_element_id,
          mapping_type,
          version,
          is_current,
          valid_from,
          valid_to
        )
        values ($1, $2, 'full', 1, true, null, null)
        """,
        requirement_item_id,
        shared_element_id,
    )


async def main() -> None:
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        for mapping in FRAMEWORK_MAPPINGS:
            source = await fetch_import_item_source(conn, shared_code=mapping["shared_code"])

            for framework in mapping["frameworks"]:
                standard_id = await ensure_standard(
                    conn,
                    code=framework["standard_code"],
                    name=STANDARD_DEFS[framework["standard_code"]]["name"],
                )
                await ensure_project_standard(
                    conn,
                    project_id=PROJECT_ID,
                    standard_id=standard_id,
                )
                disclosure_requirement_id = await ensure_disclosure_requirement(
                    conn,
                    standard_id=standard_id,
                    code=framework["disclosure_code"],
                    title=framework["disclosure_title"],
                )
                requirement_item_id = await ensure_requirement_item(
                    conn,
                    disclosure_requirement_id=disclosure_requirement_id,
                    shared_code=mapping["shared_code"],
                    shared_name=source["shared_element_name"],
                    value_type=source["value_type"],
                    unit_code=source["unit_code"],
                    requires_evidence=bool(source["requires_evidence"]),
                )
                await ensure_mapping(
                    conn,
                    requirement_item_id=requirement_item_id,
                    shared_element_id=source["shared_element_id"],
                )

        print("Seeded framework examples for BP proxy project.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
