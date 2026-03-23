# ESGvist — Поспринтовый план реализации

**Версия:** 2.0
**Дата:** 2026-03-22
**Спринт:** 2 недели
**Команда (предварительно):** 2 backend (Python) + 2 frontend (TS) + 1 QA
**Velocity:** ~40 SP/sprint
**Стек:** FastAPI + SQLAlchemy 2.0 | Next.js + shadcn/ui | PostgreSQL + Redis

---

## Обзор фаз

```
Phase 1: MVP (Спринты 1–13)
  └── Auth, standards, data entry, workflow, review,
      completeness, evidence, notifications, export,
      org setup, company structure, boundary

Phase 2: Multi-Standard + Merge + AI (Спринты 14–19)
  └── IFRS S2, SASB, merge engine, delta, merge view,
      AI assistance layer, gate engine

Phase 3: Advanced (Спринты 20–22)
  └── Platform admin, webhooks, SSO, analytics, XBRL
```

| Phase | Спринты | Недели | SP |
|-------|---------|--------|-----|
| MVP | 1–13 | 26 | ~560 |
| Multi-Standard + AI | 14–19 | 12 | ~260 |
| Advanced | 20–22 | 6 | ~150 |
| **Итого** | **22** | **44** | **~970** |

---

## PHASE 1: MVP

---

### Sprint 1 — Foundation + Auth

**Цель:** Инфраструктура, CI/CD, auth, базовые модели, layered architecture

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | Инициализация проекта: monorepo (backend/ + frontend/ + packages/shared) | 3 |
| 2 | Docker Compose: PostgreSQL + MinIO + Redis + API + Web | 3 |
| 3 | SQLAlchemy 2.0 setup: ORM models + Alembic миграция для первых таблиц (users, organizations, role_bindings, audit_log, notifications) | 5 |
| 4 | Layered architecture: api/routes + schemas + services + repositories + policies + core | 3 |
| 5 | Auth module: register, login, JWT (access + refresh), passlib/bcrypt | 5 |
| 6 | Scope-aware auth: role_bindings model, X-Organization-Id header, RequestContext dependency | 5 |
| 7 | Middleware: exception handler (AppError → ErrorResponse), request_id, CORS | 3 |
| 8 | Audit service: базовый interceptor для логирования всех действий | 3 |

#### Frontend

| # | Task | SP |
|---|------|---|
| 9 | Инициализация Next.js + TypeScript + Tailwind + shadcn/ui | 3 |
| 10 | Layout: context topbar + sidebar (из mockup-v2) | 5 |
| 11 | Auth pages: login, token storage, protected routes, X-Organization-Id injection | 5 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T1.1 | Auth: register → login → get JWT → access protected route | Integration | 2 |
| T1.2 | Auth: invalid credentials → 401 | Integration | 1 |
| T1.3 | Auth: expired token → 401, refresh → new token | Integration | 1 |
| T1.4 | Error model: все endpoints возвращают ErrorResponse формат | Integration | 1 |
| T1.5 | Role binding: create platform_admin + tenant admin | Integration | 1 |
| T1.6 | Scope check: user with role in org_A → 403 for org_B | Integration | 1 |
| T1.7 | Audit log: login записывается в audit_log | Integration | 1 |
| T1.8 | Architecture: domain/ не импортирует fastapi/sqlalchemy | Unit | 1 |
| T1.9 | E2E: login flow в браузере | E2E | 2 |

**Итого Sprint 1:** ~54 SP

**DoD:**
- [ ] Проект запускается через `docker-compose up`
- [ ] Login/logout работает
- [ ] Scope-aware role_bindings (platform + tenant)
- [ ] Unified error format
- [ ] CI pipeline: ruff + mypy + pytest на каждый PR

---

### Sprint 2 — Standards Catalog

**Цель:** CRUD стандартов, секций, disclosure requirements

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | Миграция: standards, standard_sections, disclosure_requirements | 3 |
| 2 | Standard Service + Repository: CRUD /api/standards | 5 |
| 3 | Sections: CRUD /api/standards/:id/sections (рекурсивное дерево, CTE) | 5 |
| 4 | Disclosure Requirements: CRUD /api/standards/:id/disclosures | 5 |
| 5 | Policies: only admin can POST/PATCH standards | 2 |
| 6 | Деактивация стандарта: is_active = false, запрет удаления при наличии данных | 2 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T2.1 | CRUD standard: create → read → update → deactivate | Integration | 2 |
| T2.2 | Sections: создание дерева 3 уровня, GET возвращает иерархию | Integration | 2 |
| T2.3 | Disclosure: unique(standard_id, code) → 409 | Integration | 1 |
| T2.4 | Permissions: только admin может POST standards | Integration | 1 |
| T2.5 | Pagination: standards list с page/pageSize | Integration | 1 |

**Итого Sprint 2:** ~29 SP

---

### Sprint 3 — Requirement Items + Shared Elements

**Цель:** Атомарные требования + сквозной слой

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | Миграция: requirement_items, requirement_item_dependencies | 3 |
| 2 | RequirementItem CRUD: /api/disclosures/:id/items (с иерархией) | 5 |
| 3 | Dependencies: CRUD /api/items/:id/dependencies | 3 |
| 4 | Миграция: shared_elements, shared_element_dimensions | 2 |
| 5 | SharedElement CRUD: /api/shared-elements | 3 |
| 6 | Dimensions: CRUD /api/shared-elements/:id/dimensions | 2 |
| 7 | Валидация: item_type, value_type, granularity_rule, validation_rule (JSON) | 3 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T3.1-T3.8 | CRUD items, hierarchy, dependencies, shared elements, dimensions, permissions | Integration | 8 |

**Итого Sprint 3:** ~29 SP

---

### Sprint 4 — Mapping + Seed Data + Standards UI

**Цель:** Связь requirements ↔ shared elements, загрузка GRI, UI стандартов

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | Миграция: requirement_item_shared_elements | 2 |
| 2 | Mapping CRUD: /api/mappings (full/partial/derived) | 5 |
| 3 | Cross-standard query: /api/mappings/cross-standard | 3 |
| 4 | Seed: GRI 2021 — standard + sections + disclosures (~35) + items (~15 emissions) | 8 |
| 5 | Seed: shared_elements (~30) + mappings GRI → shared (~20) | 5 |

#### Frontend

| # | Task | SP |
|---|------|---|
| 6 | UI: /settings/standards — список стандартов (TanStack Table) | 3 |
| 7 | UI: дерево секций (рекурсивный компонент) | 5 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T4.1-T4.6 | Mapping CRUD, cross-standard, seed smoke, E2E standards | Integration + E2E | 8 |

**Итого Sprint 4:** ~39 SP

---

### Sprint 5 — Organization Setup + Company Structure

**Цель:** Onboarding wizard, company entities, ownership/control links

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | Расширение organizations: legal_name, country, industry, currency, setup_completed | 3 |
| 2 | Миграция: company_entities, ownership_links, control_links | 5 |
| 3 | Org Setup Workflow: POST /api/organizations/setup (создание tenant + root entity + default boundary) | 8 |
| 4 | Entity Service: CRUD /api/entities + /api/entities/tree (CTE) | 5 |
| 5 | Ownership links: CRUD + cycle detection + sum validation (≤100%) | 5 |
| 6 | Control links: CRUD + self-control check | 3 |
| 7 | Effective ownership calculation (graph traversal) | 5 |
| 8 | Миграция: user_invitations | 2 |

#### Frontend

| # | Task | SP |
|---|------|---|
| 9 | UI: Organization Setup Wizard (5 шагов) | 8 |
| 10 | UI: post-setup dashboard guidance («Create your first ESG report») | 2 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T5.1 | Org setup: создание org + root entity + default boundary | Integration | 2 |
| T5.2 | Ownership: cycle detection → 422 | Integration | 1 |
| T5.3 | Ownership: sum > 100% → 422 | Integration | 1 |
| T5.4 | Effective ownership: chain A→B→C calculated correctly | Integration | 2 |
| T5.5 | Invitation: create + accept flow | Integration | 1 |
| T5.6 | E2E: org setup wizard | E2E | 2 |

**Итого Sprint 5:** ~55 SP

---

### Sprint 6 — Boundary + Projects

**Цель:** Boundary definitions, memberships, projects, assignments

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | Миграция: boundary_definitions, boundary_memberships, boundary_snapshots | 3 |
| 2 | Boundary Service: CRUD + automatic membership calculation by rules | 5 |
| 3 | Boundary snapshot: create + lock + immutable constraint | 3 |
| 4 | Миграция: reporting_projects (+ boundary_definition_id, boundary_snapshot_id), reporting_project_standards | 3 |
| 5 | Project Service: CRUD /api/projects, project workflow (draft → active → review → published) | 5 |
| 6 | Миграция: metric_assignments (+ entity_id, facility_id, backup_collector_id) | 3 |
| 7 | Assignment Service: CRUD + bulk + collector ≠ reviewer validation | 5 |
| 8 | Apply boundary to project: PUT /api/projects/:id/boundary + preview | 5 |

#### Frontend

| # | Task | SP |
|---|------|---|
| 9 | UI: /settings/company-structure — дерево + React Flow визуализация | 8 |
| 10 | UI: создание проекта (name, period, standards, boundary selection) | 5 |
| 11 | UI: матрица назначений (shared_element × entity × collector × reviewer) | 8 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T6.1-T6.10 | Boundary CRUD, auto-membership, snapshot, project CRUD, assignment validation, tenant isolation | Integration | 10 |
| T6.11 | E2E: create project + select boundary + assignments | E2E | 3 |

**Итого Sprint 6:** ~66 SP (может разбить на 2)

---

### Sprint 7 — Data Entry + Evidence

**Цель:** Ввод данных, evidence (новая модель), file upload

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | Миграция: data_points (+ entity_id, facility_id), data_point_dimensions | 3 |
| 2 | Миграция: evidences, evidence_files, evidence_links, data_point_evidences, requirement_item_evidences | 3 |
| 3 | DataPoint Service: CRUD + field/record validation | 5 |
| 4 | Dimensions management при создании data_point | 3 |
| 5 | Evidence Service: CRUD + upload + link/unlink + requires_evidence check | 5 |
| 6 | File storage: MinIO integration (upload, download, pre-signed URLs) | 3 |
| 7 | Seed: methodologies + boundaries справочники | 2 |

#### Frontend

| # | Task | SP |
|---|------|---|
| 8 | UI: Wizard stepper component | 3 |
| 9 | UI: QN-1 — список назначенных метрик (с entity context, boundary badge) | 5 |
| 10 | UI: QN-2 — dynamic form (fields from requirement_items) | 8 |
| 11 | UI: evidence upload (drag-and-drop, file/link toggle) | 5 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T7.1-T7.8 | DataPoint CRUD, dimensions, validation, evidence CRUD, link/unlink, file upload, permissions | Integration | 8 |

**Итого Sprint 7:** ~53 SP

---

### Sprint 8 — Workflow Engine + Gate Engine

**Цель:** State machine, transitions, Gate Engine (централизованные проверки)

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | Gate Engine: GateEngine class + Gate ABC + GateResult | 5 |
| 2 | Data Gate: INVALID_DATA, INVALID_VALUE_TYPE | 3 |
| 3 | Evidence Gate: EVIDENCE_REQUIRED | 3 |
| 4 | Boundary Gate: OUT_OF_BOUNDARY | 3 |
| 5 | Workflow Gate: INVALID_WORKFLOW_TRANSITION, DATA_POINT_LOCKED, ROLE_NOT_ALLOWED | 5 |
| 6 | Review Gate: REVIEW_COMMENT_REQUIRED | 2 |
| 7 | Workflow Service: submit, approve, reject, request_revision, rollback (все через Gate Engine) | 8 |
| 8 | API: POST /api/gate-check (pre-flight) | 3 |
| 9 | Миграция: data_point_versions | 2 |
| 10 | Auto-versioning: при каждом status change → новая version | 3 |
| 11 | Миграция: comments (threaded, typed) + CRUD | 3 |

#### Frontend

| # | Task | SP |
|---|------|---|
| 12 | UI: QN-3 — preview + validation summary | 3 |
| 13 | UI: QN-4 — submit (с gate check → inline blockers) | 3 |
| 14 | UI: /validation — split panel (список + детали + boundary context) | 8 |
| 15 | UI: gate blocker modal (list of failed gates + warnings) | 3 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T8.1-T8.15 | All workflow transitions, gate checks, locking, rollback, versioning, comments, permissions | Integration | 15 |
| T8.16 | E2E: wizard → submit → gate check → review → approve | E2E | 3 |

**Итого Sprint 8:** ~72 SP (может разбить на 2)

---

### Sprint 9 — Completeness Engine

**Цель:** Расчёт покрытия, binding, boundary-aware completeness

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | Миграция: requirement_item_statuses, requirement_item_data_points, disclosure_requirement_statuses | 3 |
| 2 | Binding service: POST /api/data-points/:id/bind | 3 |
| 3 | Completeness Engine: calculateItemStatus (fields, dimensions, evidence, approval) | 8 |
| 4 | Completeness Engine: boundary-aware calculation (entity scope from snapshot) | 5 |
| 5 | Completeness Engine: aggregateDisclosureStatus (completion_percent) | 5 |
| 6 | Completeness Gate: REQUIREMENT_INCOMPLETE, PROJECT_INCOMPLETE | 3 |
| 7 | Event triggers: DataPointApproved/Rejected/Bound → recalculate | 5 |
| 8 | API: GET /api/projects/:id/completeness (by standard, by disclosure, by entity) | 3 |
| 9 | Performance: batch recalculation < 5s per project | 2 |

#### Frontend

| # | Task | SP |
|---|------|---|
| 10 | UI: Dashboard Overview — progress block (%, breakdown by status) | 5 |
| 11 | UI: category cards (Emissions 80%, Water 100%, etc.) | 3 |
| 12 | UI: Boundary Summary block on dashboard | 3 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T9.1-T9.12 | All completeness statuses, boundary-aware, disclosure aggregation, event triggers, performance | Integration | 12 |
| T9.13 | E2E: dashboard shows real completeness | E2E | 2 |

**Итого Sprint 9:** ~62 SP (может разбить на 2)

---

### Sprint 10 — Reuse Detection + Collection Table

**Цель:** Identity Rule, reuse UX, полная Collection таблица

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | ReuseDetector: Identity Rule (9 параметров включая entity_id, facility_id) | 5 |
| 2 | API: GET /api/data-points/find-reuse | 3 |
| 3 | Reuse transparency: reusedIn[] в response | 3 |
| 4 | Multi-bound edit warning | 2 |
| 5 | Outlier detection: deviation_threshold vs previous period | 3 |

#### Frontend

| # | Task | SP |
|---|------|---|
| 6 | UI: /collection — Data table (TanStack Table, status-first, entity column, boundary badge) | 8 |
| 7 | UI: filters (by entity, by boundary, by status, by standard) | 3 |
| 8 | UI: reuse suggestion dialog в wizard | 5 |
| 9 | UI: reuse badge + outlier badge | 3 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T10.1-T10.10 | Reuse matching, no-match cases, transparency, outlier flags, multi-bound warning | Integration | 10 |
| T10.11 | E2E: collection table + reuse dialog | E2E | 2 |

**Итого Sprint 10:** ~47 SP

---

### Sprint 11 — Notifications + SLA

**Цель:** In-app notifications, email, SLA breach detection

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | Notification Service: create notifications при workflow events | 5 |
| 2 | Notification Event Handlers: submitted → reviewer, rejected → collector, boundary_changed → esg_manager | 5 |
| 3 | API: GET /notifications, PATCH /read, POST /read-all, GET /unread-count | 3 |
| 4 | SLA breach detection: cron job (deadline -3d, +3d, +7d) | 3 |
| 5 | Email integration: send email for critical/important events | 5 |
| 6 | Deduplication + no self-notify rules | 2 |

#### Frontend

| # | Task | SP |
|---|------|---|
| 7 | UI: notification bell + dropdown в topbar | 3 |
| 8 | UI: Dashboard — Issues block (critical / needs review) | 5 |
| 9 | UI: Dashboard — Priority Tasks block (overdue first) | 3 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T11.1-T11.9 | Notification creation, delivery, SLA checks, email, dedup, mark read | Integration | 9 |
| T11.10 | E2E: notification appears after submit | E2E | 2 |

**Итого Sprint 11:** ~45 SP

---

### Sprint 12 — Batch Review + Evidence Repository

**Цель:** Batch approve/reject, evidence repository UI, review UX polish

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | Batch review: POST /api/review/batch-approve, /batch-reject (с summary preview) | 5 |
| 2 | Evidence repository: GET /api/evidences (filters: type, bound/unbound, date) | 3 |
| 3 | Review context enrichment: reuse count, boundary context, anomaly flags в right panel | 3 |

#### Frontend

| # | Task | SP |
|---|------|---|
| 4 | UI: batch approve в review UI (select multiple → summary → confirm) | 5 |
| 5 | UI: /evidence — Evidence repository (файлы, ссылки, bound/unbound фильтры) | 5 |
| 6 | UI: Review right panel — boundary context, evidence section, reuse impact | 5 |
| 7 | UI: review reason codes dropdown (OUT_OF_BOUNDARY, WRONG_CONSOLIDATION) | 2 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T12.1-T12.7 | Batch approve, batch reject (comment required), evidence filters, review context | Integration | 7 |
| T12.8 | E2E: batch approve flow | E2E | 2 |

**Итого Sprint 12:** ~37 SP

---

### Sprint 13 — Export + Audit + MVP Polish

**Цель:** Export, readiness check (с boundary validation), audit log, MVP complete

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | Readiness check: GET /api/projects/:id/export/readiness (blocking + warnings + boundary validation) | 5 |
| 2 | GRI Content Index generator | 5 |
| 3 | Export: PDF (weasyprint) + Excel (openpyxl) | 5 |
| 4 | Publish flow: project → published (lock all data, require boundary snapshot, audit) | 3 |
| 5 | Audit log: GET /api/audit-log (filters: entity_type, user, date range) | 3 |
| 6 | Project workflow Gate: BOUNDARY_NOT_LOCKED, UNRESOLVED_REVIEW, PROJECT_INCOMPLETE | 3 |

#### Frontend

| # | Task | SP |
|---|------|---|
| 7 | UI: /report — readiness check + boundary validation block | 5 |
| 8 | UI: export page (format selection, download) | 3 |
| 9 | UI: /audit — audit log viewer | 5 |
| 10 | UI: user management (/settings/users + role assignment) | 5 |
| 11 | UI: Dashboard polish (responsive, loading, empty states) | 3 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T13.1-T13.10 | Readiness check, export, publish flow (lock + snapshot required), audit filters | Integration | 10 |
| T13.11 | E2E: full MVP flow — project → data → review → approve → export → publish | E2E | 5 |

**Итого Sprint 13:** ~60 SP

**🏁 MVP COMPLETE — полный цикл с company structure, boundary, gate engine**

---

## PHASE 2: Multi-Standard + Merge + AI

---

### Sprint 14 — Multi-Standard Seed + Merge Engine

**Цель:** IFRS S2 + SASB данные, merge algorithm

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | Seed: IFRS S2 2023 — standard + sections + disclosures + items + mappings | 13 |
| 2 | Seed: SASB Oil&Gas — standard + disclosures + items + mappings | 8 |
| 3 | Merge Engine: 5-step algorithm (collect → group → classify → orphans → build) | 8 |
| 4 | API: GET /projects/:id/merge, /merge/coverage | 5 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T14.1-T14.7 | Merge 1/2/3 standards, common elements, orphans, coverage, performance | Integration | 10 |

**Итого Sprint 14:** ~44 SP

---

### Sprint 15 — Deltas + Add Standard + Merge View UI

**Цель:** Delta requirements, добавление стандарта, Merge View экран

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | Миграция: requirement_deltas, requirement_item_overrides | 3 |
| 2 | Delta/Override CRUD | 5 |
| 3 | Merge + deltas integration | 5 |
| 4 | Add standard flow: impact preview + auto-binding reuse | 8 |

#### Frontend

| # | Task | SP |
|---|------|---|
| 5 | UI: /merge — матрица element × standard (+ boundary scope layer) | 8 |
| 6 | UI: summary bar, filters, drill-down, +Δ popup | 5 |
| 7 | UI: impact preview modal (add standard) | 5 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T15.1-T15.7 | Deltas, overrides, add standard flow, auto-reuse, completeness recalc | Integration | 7 |
| T15.8 | E2E: merge view + add standard | E2E | 3 |

**Итого Sprint 15:** ~49 SP

---

### Sprint 16 — Impact Analysis + Versioning

**Цель:** Impact analysis для admin, versioning mappings

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | Impact analysis: изменение requirement_item / mapping → affected projects/data | 8 |
| 2 | Versioning: version, is_current, valid_from/valid_to для items, mappings, shared_elements | 5 |
| 3 | Historical query: published project uses versioned mappings | 5 |

#### Frontend

| # | Task | SP |
|---|------|---|
| 4 | UI: impact preview modal в admin pages | 5 |
| 5 | UI: version history viewer | 3 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T16.1-T16.5 | Impact analysis, versioning, historical query | Integration | 8 |

**Итого Sprint 16:** ~34 SP

---

### Sprint 17 — AI Assistance Layer (Phase 1)

**Цель:** AI Service, inline explain, contextual Q&A, AI Gate

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | AI Assistant Service: LLMClient (Claude API), prompt templates | 5 |
| 2 | AI Tools: get_requirement_details, get_completeness_details, get_boundary_decision, get_data_point_details | 8 |
| 3 | AI Gate: Context Gate + Permission Gate + Tool Access Gate + Prompt Gate | 8 |
| 4 | AI Gate: Output Gate + Action Gate + Rate Gate + Audit Gate | 5 |
| 5 | API: POST /api/ai/explain/field, /explain/completeness, /explain/boundary | 3 |
| 6 | API: POST /api/ai/ask + /ask/stream (SSE) | 3 |
| 7 | Миграция: ai_interactions table | 2 |
| 8 | AI logging: all interactions logged | 2 |

#### Frontend

| # | Task | SP |
|---|------|---|
| 9 | UI: ExplainButton (?) component + inline tooltip | 3 |
| 10 | UI: WhyLink component | 2 |
| 11 | UI: CopilotPanel (side panel + streaming) | 5 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T17.1-T17.8 | AI explain, ask, gate checks (role filtering, tool access, prompt sanitization, rate limit), logging | Integration | 8 |
| T17.9 | E2E: click ? → explanation appears | E2E | 2 |

**Итого Sprint 17:** ~56 SP

---

### Sprint 18 — AI Review Assistant + Evidence Guidance

**Цель:** Review assistant, evidence guidance, suggested actions

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | Review assist: POST /api/ai/review-assist (summary, anomalies, draft comment) | 5 |
| 2 | Evidence guidance: POST /api/ai/explain/evidence | 3 |
| 3 | AI Tool: get_anomaly_flags, get_evidence_requirements, get_review_context | 5 |
| 4 | Suggested actions: filter by role (Action Gate) | 3 |
| 5 | AI fallback: static help text when LLM unavailable | 2 |
| 6 | Caching: field explanations (24h TTL) | 2 |

#### Frontend

| # | Task | SP |
|---|------|---|
| 7 | UI: Review panel — AI summary + anomaly flags + draft comment | 5 |
| 8 | UI: SuggestedActions component (navigate buttons) | 3 |
| 9 | UI: AI fallback badge «AI temporarily unavailable» | 1 |
| 10 | UI: evidence guidance in wizard (inline) | 3 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T18.1-T18.5 | Review assist, evidence guidance, fallback, caching, role restrictions | Integration | 5 |
| T18.6 | E2E: reviewer sees AI summary + uses draft comment | E2E | 2 |

**Итого Sprint 18:** ~39 SP

---

### Sprint 19 — Phase 2 Polish + Integration Testing

**Цель:** Cross-standard reuse, Phase 2 полировка, regression

#### Tasks

| # | Task | SP |
|---|------|---|
| 1 | Cross-record consistency: scope1 + scope2 ≠ total → flag | 3 |
| 2 | Reuse across standards: enter for GRI → auto-reuse for IFRS | 3 |
| 3 | Dashboard: coverage per standard + boundary impact on completeness | 3 |
| 4 | Qualitative wizard: QL-1→QL-3 для narrative items | 5 |
| 5 | Bulk data import: CSV/Excel → data_points | 5 |
| 6 | Performance: merge + completeness caching | 3 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T19.1-T19.5 | Full multi-standard flow, reuse, cross-consistency, import | Integration | 10 |
| T19.6 | E2E: GRI+IFRS project → merge → AI explain → export | E2E | 5 |
| T19.7 | Regression: all Sprint 1-18 tests pass | Regression | 3 |

**Итого Sprint 19:** ~40 SP

---

## PHASE 3: Advanced

---

### Sprint 20 — Platform Admin + Webhooks

**Цель:** Platform admin UI, tenant management, outbound webhooks

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | Platform admin API: GET/POST/PATCH /api/platform/tenants | 5 |
| 2 | Tenant lifecycle: suspend / reactivate / archive | 3 |
| 3 | Platform admin UI data: tenant list, tenant details, user list | 3 |
| 4 | Webhook management: CRUD /api/webhooks | 5 |
| 5 | Webhook delivery: HMAC-SHA256 + retry + dead letter | 5 |
| 6 | Webhook events: 8 core events (data_point.*, project.*, evidence.*, boundary.*) | 3 |
| 7 | Webhook test: POST /api/webhooks/:id/test | 2 |

#### Frontend

| # | Task | SP |
|---|------|---|
| 8 | UI: /platform/tenants — tenant list + create + details | 5 |
| 9 | UI: webhook management page | 3 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T20.1-T20.7 | Platform admin CRUD, tenant lifecycle, webhook delivery, HMAC, retry | Integration | 7 |

**Итого Sprint 20:** ~41 SP

---

### Sprint 21 — SSO + Advanced Export

**Цель:** OAuth2/SAML, 2FA, XBRL, async export

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | OAuth2 integration | 8 |
| 2 | SAML 2.0 (optional) | 5 |
| 3 | 2FA: TOTP setup + verification | 3 |
| 4 | XBRL export | 8 |
| 5 | Async export queue (arq/Celery) | 5 |

#### Frontend

| # | Task | SP |
|---|------|---|
| 6 | UI: SSO login + 2FA setup | 5 |
| 7 | UI: XBRL option in export | 2 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T21.1-T21.4 | OAuth2, 2FA, XBRL, async export | Integration | 8 |

**Итого Sprint 21:** ~44 SP

---

### Sprint 22 — Analytics + Production Readiness

**Цель:** Analytics, load testing, security, deployment

#### Tasks

| # | Task | SP |
|---|------|---|
| 1 | Analytics: historical trend charts | 5 |
| 2 | Analytics: user activity, SLA compliance | 5 |
| 3 | Calculated data points: formula engine + derived values | 5 |
| 4 | Performance: load testing (50 concurrent users) | 3 |
| 5 | Security: penetration testing checklist | 3 |
| 6 | API docs: Swagger UI (auto from FastAPI) | 1 |
| 7 | Production deployment: Dockerfile, nginx, CI/CD | 5 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T22.1-T22.6 | Load test, security (SQLi, XSS, rate limit), full regression, full E2E journey | Performance + Security + Regression + E2E | 16 |

**Итого Sprint 22:** ~43 SP

---

## Сводка по тестам

| Тип | Количество | Описание |
|-----|-----------|----------|
| **Unit** | ~60 | Domain logic, validators, state machine, gate rules |
| **Integration** | ~160 | API endpoints + DB: CRUD, workflow, gates, permissions, AI |
| **E2E** | ~30 | Браузерные сценарии: login → wizard → review → merge → export |
| **Performance** | ~5 | Load testing, merge speed, completeness |
| **Security** | ~5 | SQLi, XSS, rate limiting, tenant isolation |
| **Regression** | ~3 | Full suite re-run at phase boundaries |
| **Total** | **~263** | |

### Тестовый стек

| Tool | Назначение |
|------|-----------|
| **pytest + pytest-asyncio** | Backend: unit + integration tests |
| **httpx (AsyncClient)** | Backend: HTTP endpoint testing |
| **Vitest** | Frontend: unit + integration tests |
| **SQLAlchemy + Alembic** | Test database (seeded per test suite) |
| **Playwright** | E2E browser tests |
| **k6 / Artillery** | Load/performance testing |
| **testcontainers-python** | Isolated PostgreSQL + MinIO + Redis per test run |

---

## Milestones

| Milestone | Sprint | Неделя | Критерий |
|-----------|--------|--------|----------|
| **Foundation Ready** | 1 | 2 | Auth + scope-aware roles + CI/CD |
| **Catalog Complete** | 4 | 8 | GRI loaded, mappings work |
| **Org + Structure Ready** | 5 | 10 | Onboarding wizard, company entities, ownership |
| **Boundary + Projects** | 6 | 12 | Boundary, projects, assignments with entity scope |
| **Data Entry MVP** | 8 | 16 | Wizard + workflow + gate engine + review |
| **Completeness** | 9 | 18 | Boundary-aware completeness |
| **MVP Complete** | 13 | 26 | Export + publish + full cycle with boundary |
| **Multi-Standard** | 15 | 30 | Merge View with 3 standards |
| **AI Enabled** | 18 | 36 | AI explain + review assist + copilot |
| **Phase 2 Complete** | 19 | 38 | Deltas, versioning, AI, regression pass |
| **Platform Ready** | 20 | 40 | Platform admin, webhooks |
| **Production Ready** | 22 | 44 | SSO, XBRL, analytics, load tested |

---

## Риски и митигации

| Риск | Вероятность | Impact | Митигация |
|------|------------|--------|-----------|
| Sprint 6 и 8 oversize (60-70 SP) | Высокая | Средний | Разбить каждый на 2 под-спринта |
| Seed data: декомпозиция стандартов | Высокая | Высокий | Начать с GRI Emissions (305), расширять постепенно |
| Gate Engine complexity | Средняя | Средний | Начать с 3-4 core gates, расширять итеративно |
| AI integration latency | Средняя | Средний | Caching + streaming + fallback |
| Merge Engine edge cases | Средняя | Высокий | Extensive integration tests |
| Company structure graph performance | Низкая | Средний | CTE optimization, limit depth |
| Boundary + completeness coupling | Средняя | Высокий | Clear interfaces, boundary-aware tests from Sprint 9 |
