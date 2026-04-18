# ESGvist Dashboard

Monorepo for the ESGvist platform: ESG data collection, review, completeness tracking, evidence management, boundary modeling, and reporting workflows.

This repository contains:
- a FastAPI backend,
- a Next.js frontend,
- product and architecture documentation,
- demo, database snapshots, and Playwright regression artifacts.

The most detailed product specifications live under `docs/` and are primarily written in Russian.

## Repository Layout

- `backend/` - FastAPI application, Alembic migrations, services, repositories, tests, and helper scripts
- `frontend/` - Next.js application, UI components, Playwright suites, and frontend utilities
- `docs/` - architecture, technical specs, role-specific requirements, backlog, sprint plan, runtime notes
- `artifacts/` - demo materials, screen summaries, and generated regression outputs

## Canonical Database Snapshot

The repository keeps one canonical PostgreSQL SQL snapshot under `artifacts/db/`:

- `esgvist_snapshot_2026-04-17.sql` - the current primary application database (`esgvist`)

This snapshot is the publishable reference copy for local restore and environment sync.

## Quick Start

### Recommended: local frontend + local backend

Prerequisites:
- Python 3.11+
- Node.js 20+
- `pnpm`
- Docker Desktop or Docker Engine

1. Start infrastructure services:

```bash
cp .env.example backend/.env
docker compose up -d postgres redis minio
```

By default, local startup points the backend at the current primary database:

- `esgvist`
- DSN: `postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/esgvist`

If you switch databases for a one-off task, restore this value in `backend/.env` before the next normal app launch.

2. Start the backend on port `8001`:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

3. Start the frontend:

```bash
cd frontend
pnpm install
pnpm dev
```

Endpoints:
- App: `http://localhost:3000`
- API: `http://localhost:8001`
- Swagger UI: `http://localhost:8001/docs`
- Health: `http://localhost:8001/api/health`

### Alternative: Dockerized API + local frontend

`docker-compose.yml` exposes the API on port `8000`, while the frontend rewrite defaults to `8001`. If you use the Dockerized API, start the frontend with `API_PORT=8000`.

In this mode the API talks to:

- PostgreSQL at `postgres:5432`
- Redis at `redis:6379`
- MinIO at `minio:9000`

Evidence uploads use MinIO by default in the Dockerized API flow, so files survive API container restarts via the `minio_data` volume.

```bash
docker compose up --build api postgres redis minio
cd frontend
API_PORT=8000 pnpm dev
```

## Documentation Map

Start here:
- `docs/ARCHITECTURE.md` - system architecture, services, event flow, database, security, deployment
- `docs/SPEC-COVERAGE-MATRIX.md` - current implementation coverage vs. specs, known gaps, recommended completion order
- `docs/RUNTIME-CONFIG.md` - runtime safety rules and environment expectations
- `docs/DB-SCHEMA-RUNTIME.md` - schema runtime checks and migration-related notes

Core product specs:
- `docs/TZ-ESGvist-v1.md` - main product spec
- `docs/TZ-BackendArchitecture.md` - backend architecture contract
- `docs/TZ-PermissionMatrix.md` - role and permission matrix
- `docs/TZ-WorkflowGateMatrix.md` - workflow and gate rules
- `docs/TZ-NFR.md` - non-functional requirements
- `docs/ERROR-MODEL.md` - unified error model and permission policy

Role and module specs:
- `docs/TZ-Admin.md`
- `docs/TZ-ESGManager.md`
- `docs/TZ-Reviewer.md`
- `docs/TZ-User.md`
- `docs/TZ-PlatformAdmin.md`
- `docs/TZ-OrgSetup.md`
- `docs/TZ-CompanyStructure.md`
- `docs/TZ-BoundaryIntegration.md`
- `docs/TZ-Evidence.md`
- `docs/TZ-CustomDatasheet.md`
- `docs/TZ-CustomDatasheet-Implementation.md`
- `docs/TZ-Notifications.md`
- `docs/TZ-AIAssistance.md`

Planning and delivery:
- `docs/BACKLOG.md`
- `docs/SPRINT-PLAN.md`
- `docs/SCREENS-REGISTRY.md`

## Development Notes

- Backend settings are loaded from `.env`; for local development, copying the root `.env.example` to `backend/.env` is the safest default.
- In debug mode the API exposes Swagger at `/docs` and ReDoc at `/redoc`.
- The frontend proxies `/api/*` requests to `http://localhost:${API_PORT:-8001}/api/*`.
- Docker Compose currently covers infrastructure services and the API, but not the frontend app.

## Tests

Backend:

```bash
cd backend
pytest
ruff check .
```

Frontend:

```bash
cd frontend
pnpm lint
pnpm test:e2e:smoke-regression
pnpm test:e2e:guided-collection
pnpm test:e2e:framework-catalog
pnpm test:e2e:custom-datasheet
pnpm test:e2e:platform-flows
pnpm test:e2e:form-config-resync
pnpm test:e2e:notifications-support-mode
```

`pnpm test:e2e:smoke-regression` runs the current smoke pack:

- `guided-collection`
- `framework-catalog`
- `custom-datasheet`

Additional Playwright configs are available in `frontend/playwright*.config.ts`.

## Current State

The repository already has substantial documentation coverage. The fastest way to understand what is implemented today, what is only partial, and what remains open is `docs/SPEC-COVERAGE-MATRIX.md`.

This `README.md` is intended as a navigation entry point, not a replacement for the detailed specs in `docs/`.
