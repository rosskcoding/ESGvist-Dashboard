from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

import asyncpg

from app.core.security import hash_password, verify_password


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@127.0.0.1:5432/esgvist_bp_proxy_case",
)
PROJECT_ID = int(os.getenv("PROJECT_ID", "6"))
SHARED_PASSWORD = os.getenv("COLLECTOR_PASSWORD", "Test1234")

# We keep the imported proxy dataset recognizable but expose a richer working
# queue in Collection: 18 not started, 18 in progress, rest complete.
NOT_STARTED_ASSIGNMENT_IDS = list(range(1, 19))


@dataclass(frozen=True)
class PartialScenario:
    assignment_id: int
    status: str
    clear_value: bool = False
    clear_evidence: bool = False
    review_comment: str | None = None


@dataclass(frozen=True)
class CollectorSpec:
    email: str
    full_name: str


COLLECTORS = [
    CollectorSpec("collector1@greentech.com", "Ivan Collector"),
    CollectorSpec("collector2@greentech.com", "Maria Data"),
    CollectorSpec("collector3@greentech.com", "Sofia Entry"),
]

REVIEWER_EMAIL = "reviewer@greentech.com"
IN_PROGRESS_ASSIGNMENT_IDS = list(range(19, 37))


def build_in_progress_scenarios() -> list[PartialScenario]:
    scenarios: list[PartialScenario] = []
    for index, assignment_id in enumerate(IN_PROGRESS_ASSIGNMENT_IDS):
        variant = index % 3
        if variant == 0:
            scenarios.append(
                PartialScenario(
                    assignment_id=assignment_id,
                    status="draft",
                    clear_value=True,
                    clear_evidence=True,
                )
            )
        elif variant == 1:
            scenarios.append(
                PartialScenario(
                    assignment_id=assignment_id,
                    status="draft",
                    clear_evidence=True,
                )
            )
        else:
            scenarios.append(
                PartialScenario(
                    assignment_id=assignment_id,
                    status="needs_revision",
                    clear_value=True,
                    review_comment="Needs updated imported figure before approval.",
                )
            )
    return scenarios


IN_PROGRESS_SCENARIOS = build_in_progress_scenarios()


async def fetch_assignment_rows(
    conn: asyncpg.Connection,
    assignment_ids: list[int],
) -> list[asyncpg.Record]:
    return await conn.fetch(
        """
        select
          ma.id as assignment_id,
          ma.shared_element_id,
          ma.entity_id,
          ma.facility_id,
          dp.id as data_point_id
        from metric_assignments ma
        left join data_points dp
          on dp.reporting_project_id = ma.reporting_project_id
         and dp.shared_element_id = ma.shared_element_id
         and coalesce(dp.entity_id, 0) = coalesce(ma.entity_id, 0)
         and coalesce(dp.facility_id, 0) = coalesce(ma.facility_id, 0)
        where ma.reporting_project_id = $1
          and ma.id = any($2::int[])
        order by ma.id
        """,
        PROJECT_ID,
        assignment_ids,
    )


async def ensure_user(
    conn: asyncpg.Connection,
    *,
    email: str,
    full_name: str,
    role: str,
    organization_id: int,
) -> int:
    user = await conn.fetchrow(
        """
        select id, password_hash, full_name, is_active
        from users
        where email = $1
        """,
        email,
    )

    if user is None:
        user_id = await conn.fetchval(
            """
            insert into users (
              email,
              password_hash,
              full_name,
              is_active,
              notification_prefs,
              totp_enabled
            )
            values ($1, $2, $3, true, $4::jsonb, false)
            returning id
            """,
            email,
            hash_password(SHARED_PASSWORD),
            full_name,
            '{"email": true, "in_app": true}',
        )
    else:
        user_id = user["id"]
        needs_password_update = not verify_password(SHARED_PASSWORD, user["password_hash"])
        if needs_password_update or user["full_name"] != full_name or not user["is_active"]:
            await conn.execute(
                """
                update users
                set
                  password_hash = $2,
                  full_name = $3,
                  is_active = true,
                  notification_prefs = $4::jsonb,
                  updated_at = now()
                where id = $1
                """,
                user_id,
                hash_password(SHARED_PASSWORD),
                full_name,
                '{"email": true, "in_app": true}',
            )

    existing_role = await conn.fetchrow(
        """
        select id, role
        from role_bindings
        where user_id = $1
          and scope_type = 'organization'
          and scope_id = $2
        """,
        user_id,
        organization_id,
    )
    if existing_role is None:
        await conn.execute(
            """
            insert into role_bindings (
              user_id,
              role,
              scope_type,
              scope_id,
              created_by
            )
            values ($1, $2, 'organization', $3, $1)
            """,
            user_id,
            role,
            organization_id,
        )
    elif existing_role["role"] != role:
        await conn.execute(
            """
            update role_bindings
            set role = $2, updated_at = now()
            where id = $1
            """,
            existing_role["id"],
            role,
        )

    return user_id


async def load_summary(conn: asyncpg.Connection) -> dict[str, int]:
    rows = await conn.fetch(
        """
        select
          case
            when dp.id is null and ma.status = 'completed' then 'complete'
            when dp.id is null and ma.status = 'in_progress' then 'partial'
            when dp.id is null then 'missing'
            when dp.status = 'approved' then 'complete'
            when dp.status in ('draft', 'submitted', 'in_review', 'needs_revision', 'rejected') then 'partial'
            else 'missing'
          end as collection_status,
          count(*)::int as count
        from metric_assignments ma
        left join data_points dp
          on dp.reporting_project_id = ma.reporting_project_id
         and dp.shared_element_id = ma.shared_element_id
         and coalesce(dp.entity_id, 0) = coalesce(ma.entity_id, 0)
         and coalesce(dp.facility_id, 0) = coalesce(ma.facility_id, 0)
        where ma.reporting_project_id = $1
        group by 1
        order by 1
        """,
        PROJECT_ID,
    )
    return {row["collection_status"]: row["count"] for row in rows}


async def main() -> None:
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        project = await conn.fetchrow(
            "select id, name, organization_id from reporting_projects where id = $1",
            PROJECT_ID,
        )
        if not project:
            raise RuntimeError(f"Project {PROJECT_ID} was not found")

        reviewer_id = await conn.fetchval(
            """
            select u.id
            from users u
            join role_bindings rb on rb.user_id = u.id
            where u.email = $1
              and rb.scope_type = 'organization'
              and rb.scope_id = $2
              and rb.role = 'reviewer'
            limit 1
            """,
            REVIEWER_EMAIL,
            project["organization_id"],
        )
        if reviewer_id is None:
            raise RuntimeError(
                f"Reviewer account {REVIEWER_EMAIL} with organization scope was not found"
            )

        collector_ids: list[int] = []
        for collector in COLLECTORS:
            collector_id = await ensure_user(
                conn,
                email=collector.email,
                full_name=collector.full_name,
                role="collector",
                organization_id=project["organization_id"],
            )
            collector_ids.append(collector_id)

        not_started_rows = await fetch_assignment_rows(conn, NOT_STARTED_ASSIGNMENT_IDS)
        partial_rows = await fetch_assignment_rows(
            conn,
            [scenario.assignment_id for scenario in IN_PROGRESS_SCENARIOS],
        )

        partial_by_assignment = {row["assignment_id"]: row for row in partial_rows}

        async with conn.transaction():
            # 1. Not started = no data point yet + assignment set back to assigned.
            not_started_dp_ids = [row["data_point_id"] for row in not_started_rows if row["data_point_id"]]
            if not_started_dp_ids:
                await conn.execute(
                    "delete from data_points where id = any($1::int[])",
                    not_started_dp_ids,
                )

            for index, assignment_id in enumerate(NOT_STARTED_ASSIGNMENT_IDS):
                collector_id = collector_ids[index // 6]
                await conn.execute(
                    """
                    update metric_assignments
                    set
                      status = 'assigned',
                      collector_id = $3,
                      reviewer_id = $4,
                      backup_collector_id = null,
                      updated_at = now()
                    where reporting_project_id = $1
                      and id = $2
                    """,
                    PROJECT_ID,
                    assignment_id,
                    collector_id,
                    reviewer_id,
                )

            # 2. In progress = editable workflow statuses + assigned responsible collectors.
            for index, scenario in enumerate(IN_PROGRESS_SCENARIOS):
                row = partial_by_assignment.get(scenario.assignment_id)
                if not row or not row["data_point_id"]:
                    continue

                collector_id = collector_ids[index // 6]
                await conn.execute(
                    """
                    update metric_assignments
                    set
                      status = 'in_progress',
                      collector_id = $3,
                      reviewer_id = $4,
                      backup_collector_id = null,
                      updated_at = now()
                    where reporting_project_id = $1
                      and id = $2
                    """,
                    PROJECT_ID,
                    scenario.assignment_id,
                    collector_id,
                    reviewer_id,
                )

                if scenario.clear_evidence:
                    await conn.execute(
                        "delete from data_point_evidences where data_point_id = $1",
                        row["data_point_id"],
                    )

                await conn.execute(
                    """
                    update data_points
                    set
                      status = $2,
                      numeric_value = case when $3::boolean then null else numeric_value end,
                      text_value = case when $3::boolean then null else text_value end,
                      review_comment = $4,
                      updated_at = now()
                    where id = $1
                    """,
                    row["data_point_id"],
                    scenario.status,
                    scenario.clear_value,
                    scenario.review_comment,
                )

            # 3. Everything else remains complete and can stay unassigned.
            await conn.execute(
                """
                update metric_assignments
                set
                  status = 'completed',
                  collector_id = null,
                  reviewer_id = null,
                  backup_collector_id = null,
                  updated_at = now()
                where reporting_project_id = $1
                  and id <> all($2::int[])
                  and id <> all($3::int[])
                """,
                PROJECT_ID,
                NOT_STARTED_ASSIGNMENT_IDS,
                [scenario.assignment_id for scenario in IN_PROGRESS_SCENARIOS],
            )
            await conn.execute(
                """
                update data_points
                set status = 'approved', review_comment = null, updated_at = now()
                where reporting_project_id = $1
                  and id <> all($2::int[])
                """,
                PROJECT_ID,
                [row["data_point_id"] for row in partial_rows if row["data_point_id"]],
            )

        print(
            {
                "project_id": PROJECT_ID,
                "project_name": project["name"],
                "not_started_assignments": NOT_STARTED_ASSIGNMENT_IDS,
                "in_progress_assignments": [scenario.assignment_id for scenario in IN_PROGRESS_SCENARIOS],
                "collectors": [
                    {"email": collector.email, "full_name": collector.full_name}
                    for collector in COLLECTORS
                ],
                "summary": await load_summary(conn),
            }
        )
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
