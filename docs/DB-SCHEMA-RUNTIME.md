# DB Schema Runtime

`backend/scripts/db_schema.py` is the operational entrypoint for runtime revision control.

## Commands

- `python scripts/db_schema.py check`
  Fails if the database is not at Alembic `head` or if core tables are missing.
- `python scripts/db_schema.py current`
  Prints current/head revisions and bootstrap status.
- `python scripts/db_schema.py upgrade`
  Applies runtime revisions to the configured database.
- `python scripts/db_schema.py stamp-head`
  Marks a bootstrapped database as being at Alembic `head` without replaying revisions.

## Runtime Flags

- `DB_REQUIRE_CURRENT_REVISION=true`
  Refuse API startup when the database is behind `head`.
- `DB_AUTO_UPGRADE=true`
  Attempt runtime Alembic upgrade during API startup.

Both flags still require a bootstrapped base schema. If core tables such as `users`, `organizations`, or
`reporting_projects` are missing, startup will fail with a bootstrap error instead of silently creating them.

## Recommended Usage

- Local/dev with explicit control:
  `DB_REQUIRE_CURRENT_REVISION=false`, `DB_AUTO_UPGRADE=false`
- Staging/prod with strict gate:
  `DB_REQUIRE_CURRENT_REVISION=true`, `DB_AUTO_UPGRADE=false`
- Controlled auto-upgrade environments:
  `DB_REQUIRE_CURRENT_REVISION=true`, `DB_AUTO_UPGRADE=true`

## Smoke Check

`python scripts/schema_smoke.py` validates both operational paths:

- CLI flow: `check -> stamp-head -> current`
- API startup flow with `DB_AUTO_UPGRADE=true`

This smoke check is wired into backend CI.
