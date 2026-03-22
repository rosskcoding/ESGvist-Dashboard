# ESGvist — Поспринтовый план реализации

**Версия:** 1.0
**Дата:** 2026-03-22
**Спринт:** 2 недели
**Команда (предварительно):** 2 backend + 2 frontend + 1 QA
**Velocity:** ~40 SP/sprint

---

## Обзор фаз

```
Phase 1: MVP (Спринты 1–11)
  └── Один стандарт (GRI), полный workflow, completeness, export

Phase 2: Multi-Standard + Merge (Спринты 12–16)
  └── IFRS S2, SASB, merge engine, delta, merge view

Phase 3: Advanced (Спринты 17–19)
  └── Webhooks, SSO, analytics, XBRL
```

| Phase | Спринты | Недели | SP |
|-------|---------|--------|-----|
| MVP | 1–11 | 22 | ~440 |
| Multi-Standard | 12–16 | 10 | ~200 |
| Advanced | 17–19 | 6 | ~120 |
| **Итого** | **19** | **38** | **~760** |

---

## PHASE 1: MVP

---

### Sprint 1 — Foundation + Auth

**Цель:** Инфраструктура, CI/CD, auth, базовые модели

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | Инициализация проекта: monorepo (apps/api + apps/web + packages/shared) | 3 |
| 2 | Docker Compose: PostgreSQL + MinIO + API + Web | 3 |
| 3 | Prisma setup: schema.prisma с первыми 5 таблицами (users, organizations, reporting_periods, audit_log, notifications) | 5 |
| 4 | Auth module: register, login, JWT (access + refresh), bcrypt | 5 |
| 5 | Middleware: auth guard, role guard, error handler, request ID | 5 |
| 6 | Unified error model: ErrorResponse, error codes enum, HTTP status mapping | 3 |
| 7 | Audit service: базовый interceptor для логирования всех действий | 3 |

#### Frontend

| # | Task | SP |
|---|------|---|
| 8 | Инициализация Next.js + TypeScript + Tailwind | 3 |
| 9 | Layout: context topbar + sidebar (из mockup-v2) | 5 |
| 10 | Auth pages: login, token storage, protected routes | 5 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T1.1 | Auth: register → login → get JWT → access protected route | Integration | 2 |
| T1.2 | Auth: invalid credentials → 401 | Integration | 1 |
| T1.3 | Auth: expired token → 401, refresh → new token | Integration | 1 |
| T1.4 | Error model: все endpoints возвращают ErrorResponse формат | Integration | 1 |
| T1.5 | Role guard: collector → admin endpoint → 403 | Integration | 1 |
| T1.6 | Audit log: login записывается в audit_log | Integration | 1 |
| T1.7 | E2E: login flow в браузере | E2E | 2 |

**Итого Sprint 1:** ~49 SP

**Definition of Done:**
- [ ] Проект запускается через `docker-compose up`
- [ ] Login/logout работает
- [ ] JWT auth на всех endpoints
- [ ] Unified error format на всех ошибках
- [ ] Audit log записывает login
- [ ] CI pipeline: lint + test на каждый PR

---

### Sprint 2 — Standards Catalog (Backend)

**Цель:** CRUD стандартов, секций, disclosure requirements

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | Миграция: таблицы standards, standard_sections, disclosure_requirements | 3 |
| 2 | Standard Service: CRUD /api/standards | 5 |
| 3 | Sections: CRUD /api/standards/:id/sections (рекурсивное дерево) | 5 |
| 4 | Disclosure Requirements: CRUD /api/standards/:id/disclosures | 5 |
| 5 | Валидация: unique(standard_id, code), applicability_rule JSON schema | 3 |
| 6 | Деактивация стандарта: is_active = false, запрет удаления при наличии данных | 2 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T2.1 | CRUD standard: create → read → update → deactivate | Integration | 2 |
| T2.2 | Standard: нельзя создать duplicate code | Integration | 1 |
| T2.3 | Sections: создание дерева 3 уровня, GET возвращает иерархию | Integration | 2 |
| T2.4 | Disclosure: unique(standard_id, code) → 409 при дубле | Integration | 1 |
| T2.5 | Disclosure: applicability_rule сохраняется и читается как JSON | Integration | 1 |
| T2.6 | Standard: нельзя удалить, если есть disclosures → 409 | Integration | 1 |
| T2.7 | Permissions: только admin может POST/PATCH standards | Integration | 1 |
| T2.8 | Pagination: standards list с page/pageSize | Integration | 1 |

**Итого Sprint 2:** ~39 SP

**DoD:**
- [ ] GRI standard создаётся через API
- [ ] Дерево секций строится рекурсивно
- [ ] Disclosure requirements с mandatory_level
- [ ] Все ошибки в формате ErrorResponse
- [ ] 100% тестовое покрытие CRUD операций

---

### Sprint 3 — Requirement Items + Shared Elements

**Цель:** Атомарные требования + сквозной слой

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | Миграция: requirement_items, requirement_item_dependencies | 3 |
| 2 | RequirementItem CRUD: /api/disclosures/:id/items (с иерархией parent_item_id) | 5 |
| 3 | Dependencies: CRUD /api/items/:id/dependencies (requires/excludes/conditional_on) | 3 |
| 4 | Миграция: shared_elements, shared_element_dimensions | 2 |
| 5 | SharedElement CRUD: /api/shared-elements | 3 |
| 6 | Dimensions: CRUD /api/shared-elements/:id/dimensions | 2 |
| 7 | Валидация: item_type enum, value_type enum, granularity_rule/validation_rule JSON | 3 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T3.1 | RequirementItem: create с type=metric, value_type=number, unit_code=tCO2e | Integration | 1 |
| T3.2 | RequirementItem: иерархия parent_item_id (2 уровня) | Integration | 2 |
| T3.3 | RequirementItem: validation_rule и granularity_rule сохраняются как JSON | Integration | 1 |
| T3.4 | Dependencies: создание requires + excludes | Integration | 1 |
| T3.5 | Dependencies: unique(item_id, depends_on_id, type) | Integration | 1 |
| T3.6 | SharedElement: unique code | Integration | 1 |
| T3.7 | SharedElement dimensions: unique(shared_element_id, dimension_type) | Integration | 1 |
| T3.8 | Permissions: только admin | Integration | 1 |

**Итого Sprint 3:** ~30 SP

**DoD:**
- [ ] Disclosure разбивается на requirement_items
- [ ] Иерархия items работает
- [ ] Dependencies между items
- [ ] Shared elements + dimensions
- [ ] JSON rules сохраняются и валидируются

---

### Sprint 4 — Mapping + Seed Data

**Цель:** Связь requirements ↔ shared elements, загрузка GRI

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | Миграция: requirement_item_shared_elements | 2 |
| 2 | Mapping CRUD: /api/mappings (full/partial/derived) | 5 |
| 3 | Query: /api/mappings/cross-standard — shared elements в нескольких стандартах | 3 |
| 4 | Seed: GRI 2021 — standard + sections (~10) | 3 |
| 5 | Seed: GRI 2021 — disclosure_requirements (~35) | 5 |
| 6 | Seed: GRI 2021 — requirement_items для Emissions (305-1, 305-2, 305-3) ~15 items | 5 |
| 7 | Seed: shared_elements (~30 для emissions, energy, water) | 3 |
| 8 | Seed: mappings GRI → shared_elements (~20) | 3 |

#### Frontend

| # | Task | SP |
|---|------|---|
| 9 | UI: /settings/standards — список стандартов (таблица) | 3 |
| 10 | UI: дерево секций (рекурсивный компонент, expand/collapse) | 5 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T4.1 | Mapping: create full mapping item → shared_element | Integration | 1 |
| T4.2 | Mapping: один shared_element → N items из разных стандартов | Integration | 2 |
| T4.3 | Mapping: unique(requirement_item_id, shared_element_id) | Integration | 1 |
| T4.4 | Cross-standard query: возвращает shared_elements с 2+ стандартами | Integration | 2 |
| T4.5 | Seed: GRI загружен, 35 disclosures, ~15 items для emissions | Smoke | 1 |
| T4.6 | E2E: стандарты видны в UI, дерево раскрывается | E2E | 2 |

**Итого Sprint 4:** ~46 SP

**DoD:**
- [ ] Mapping requirement → shared element работает
- [ ] Cross-standard query
- [ ] GRI 2021 полностью загружен (standard + sections + disclosures + items + mappings)
- [ ] UI: список стандартов и дерево секций

---

### Sprint 5 — Projects + Assignments

**Цель:** Проекты отчётности, назначение метрик

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | Миграция: reporting_projects, reporting_project_standards | 2 |
| 2 | Project CRUD: /api/projects (create, read, update) | 5 |
| 3 | Project standards: PUT /api/projects/:id/standards (выбор стандартов) | 3 |
| 4 | Project workflow: draft → in_progress → review → published | 3 |
| 5 | Миграция: metric_assignments (с backup_collector_id, escalation_after_days) | 2 |
| 6 | Assignments CRUD: /api/projects/:id/assignments | 5 |
| 7 | Bulk assignments: POST /api/projects/:id/assignments/bulk | 3 |
| 8 | Валидация: collector ≠ reviewer, tenant isolation | 2 |

#### Frontend

| # | Task | SP |
|---|------|---|
| 9 | UI: создание проекта (name, period, standards selection) | 5 |
| 10 | UI: матрица назначений (shared_element × collector × reviewer × deadline) | 8 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T5.1 | Project: create → выбрать GRI → статус draft | Integration | 2 |
| T5.2 | Project workflow: draft → in_progress (стандарты выбраны) | Integration | 1 |
| T5.3 | Project workflow: нельзя published без completeness | Integration | 1 |
| T5.4 | Assignment: create с collector + reviewer | Integration | 1 |
| T5.5 | Assignment: collector == reviewer → 409 ASSIGNMENT_ROLE_CONFLICT | Integration | 1 |
| T5.6 | Assignment: без назначения (null collector) → status=pending | Integration | 1 |
| T5.7 | Bulk assignment: 5 элементов за 1 запрос | Integration | 1 |
| T5.8 | Tenant isolation: user из org_A не видит project org_B | Integration | 1 |
| T5.9 | E2E: создание проекта + назначение в матрице | E2E | 2 |

**Итого Sprint 5:** ~49 SP

**DoD:**
- [ ] Проект создаётся с выбором стандартов
- [ ] Workflow проекта работает
- [ ] Назначения метрик (single + bulk)
- [ ] Constraint: collector ≠ reviewer
- [ ] Tenant isolation

---

### Sprint 6 — Data Entry (Backend + Wizard начало)

**Цель:** Ввод данных, draft/submit, evidence upload

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | Миграция: data_points, data_point_dimensions, methodologies, boundaries, source_records, attachments | 5 |
| 2 | DataPoint CRUD: /api/projects/:id/data-points | 5 |
| 3 | Dimensions: управление разрезами при создании/обновлении data_point | 3 |
| 4 | Field-level validation: type check, min/max, required fields | 3 |
| 5 | Record-level validation: required dimensions (из granularity_rule) | 3 |
| 6 | Attachments: upload + bind to data_point or requirement_item | 5 |
| 7 | File storage integration: MinIO (S3-compatible) | 3 |
| 8 | Seed: methodologies (GHG Protocol, Location-based, Market-based) + boundaries | 2 |

#### Frontend

| # | Task | SP |
|---|------|---|
| 9 | UI: компонент Wizard (stepper + навигация) | 5 |
| 10 | UI: QN-1 — список назначенных метрик (с статусами) | 3 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T6.1 | DataPoint: create draft с numeric_value + unit_code | Integration | 1 |
| T6.2 | DataPoint: create с dimensions (scope=Scope1, gas=CO2) | Integration | 1 |
| T6.3 | DataPoint: validation error — missing required unit_code | Integration | 1 |
| T6.4 | DataPoint: validation error — missing required dimension | Integration | 1 |
| T6.5 | Attachment: upload file → bind to data_point | Integration | 2 |
| T6.6 | Attachment: file stored in MinIO, URI valid | Integration | 1 |
| T6.7 | Permissions: collector видит только свои assigned data points | Integration | 1 |
| T6.8 | Permissions: collector не может создать data_point для чужого assignment | Integration | 1 |

**Итого Sprint 6:** ~46 SP

**DoD:**
- [ ] DataPoint создаётся с dimensions
- [ ] Field + record level validation
- [ ] Файлы загружаются в MinIO
- [ ] Collector видит только свои данные
- [ ] Wizard начат (stepper + QN-1)

---

### Sprint 7 — Workflow Engine + Review

**Цель:** Полный workflow, review UI

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | Workflow Service: state machine (transition rules, role checks) | 5 |
| 2 | API: POST /submit, /approve, /reject, /request-revision | 5 |
| 3 | Миграция: data_point_versions | 2 |
| 4 | Auto-versioning: при каждом изменении value → новая version | 3 |
| 5 | Locking: read-only для submitted/in_review/approved | 3 |
| 6 | Rollback: approved → draft (esg_manager only, с comment + audit) | 2 |
| 7 | Миграция: comments (threaded, typed) | 2 |
| 8 | Comments CRUD: /api/comments + resolve | 3 |

#### Frontend

| # | Task | SP |
|---|------|---|
| 9 | UI: QN-2 — форма ввода (dynamic fields из requirement_items) | 8 |
| 10 | UI: QN-3 — preview + validation summary | 3 |
| 11 | UI: QN-4 — submit (draft / send to review) | 3 |
| 12 | UI: /validation — split panel (список + детали) | 5 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T7.1 | Workflow: draft → submitted (collector) | Integration | 1 |
| T7.2 | Workflow: submitted → in_review (auto, reviewer assigned) | Integration | 1 |
| T7.3 | Workflow: in_review → approved (reviewer) | Integration | 1 |
| T7.4 | Workflow: in_review → rejected (reviewer, comment required) | Integration | 1 |
| T7.5 | Workflow: rejected → 422 if no comment | Integration | 1 |
| T7.6 | Workflow: submitted → draft — 422 INVALID_WORKFLOW_TRANSITION | Integration | 1 |
| T7.7 | Locking: PATCH data_point in submitted → 422 DATA_POINT_LOCKED | Integration | 1 |
| T7.8 | Rollback: approved → draft by esg_manager (audit log записан) | Integration | 1 |
| T7.9 | Rollback: approved → draft by collector → 403 | Integration | 1 |
| T7.10 | Versioning: 3 changes → 3 versions in data_point_versions | Integration | 1 |
| T7.11 | Comments: create thread → reply → resolve | Integration | 1 |
| T7.12 | E2E: wizard QN-1→QN-4 → submit | E2E | 2 |
| T7.13 | E2E: reviewer opens split panel → approve | E2E | 2 |

**Итого Sprint 7:** ~56 SP

**DoD:**
- [ ] Полный workflow draft→submit→review→approve/reject
- [ ] Locking работает
- [ ] Versioning при каждом изменении
- [ ] Comments с threading
- [ ] Wizard QN-1→QN-4 работает
- [ ] Review split panel работает

---

### Sprint 8 — Completeness Engine

**Цель:** Автоматический расчёт статусов покрытия

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | Миграция: requirement_item_statuses, requirement_item_data_points, disclosure_requirement_statuses | 3 |
| 2 | Binding service: POST /api/data-points/:id/bind — привязка data_point к requirement_item | 3 |
| 3 | CompletenessEngine: calculateItemStatus (required fields, dimensions, evidence, approval) | 8 |
| 4 | CompletenessEngine: aggregateDisclosureStatus (completion_percent, missing_summary) | 5 |
| 5 | Event triggers: DataPointUpdated → recalculate, DataPointApproved → recalculate | 5 |
| 6 | API: GET /api/projects/:id/completeness (by standard, by disclosure) | 3 |
| 7 | Performance: batch recalculation < 5s per project | 2 |

#### Frontend

| # | Task | SP |
|---|------|---|
| 8 | UI: Dashboard Overview — progress block (из mockup-v2: 68%, breakdown) | 5 |
| 9 | UI: category cards (Emissions 80%, Water 100%, etc.) | 5 |
| 10 | UI: fast scan summary (missing / in_progress / in_review / submitted) | 3 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T8.1 | Status: no data → missing | Integration | 1 |
| T8.2 | Status: data exists, not approved → partial | Integration | 1 |
| T8.3 | Status: data approved, all dimensions → complete | Integration | 1 |
| T8.4 | Status: data approved, missing dimension → partial | Integration | 1 |
| T8.5 | Status: item_type=document, no attachment → partial | Integration | 1 |
| T8.6 | Disclosure: all items complete → disclosure complete, 100% | Integration | 1 |
| T8.7 | Disclosure: 2/3 complete → partial, 66.7% | Integration | 1 |
| T8.8 | Trigger: approve data_point → status recalculated automatically | Integration | 2 |
| T8.9 | Trigger: reject data_point → status becomes partial | Integration | 1 |
| T8.10 | Overall score: mandatory disclosures only | Integration | 1 |
| T8.11 | Performance: 100 items recalculate < 5 seconds | Performance | 2 |
| T8.12 | E2E: dashboard shows real completeness data | E2E | 2 |

**Итого Sprint 8:** ~55 SP

**DoD:**
- [ ] Completeness Engine рассчитывает item + disclosure statuses
- [ ] Автоматический пересчёт при изменении данных
- [ ] Binding data_point → requirement_item
- [ ] Dashboard показывает реальные данные
- [ ] Performance < 5s на проект

---

### Sprint 9 — Reuse Detection + Data Table

**Цель:** Identity Rule, reuse UX, Collection таблица

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | ReuseDetector: поиск по Identity Rule (7 параметров) | 5 |
| 2 | API: GET /api/data-points/:id/reuse-candidates | 3 |
| 3 | Reuse transparency: reusedIn[] в DataPoint response (список disclosures) | 3 |
| 4 | Locking warning: при PATCH multi-bound data_point — warning в response header | 2 |
| 5 | Outlier detection: deviation_threshold check vs previous period | 3 |

#### Frontend

| # | Task | SP |
|---|------|---|
| 6 | UI: /collection — Data table (status-first, filters, actions) | 8 |
| 7 | UI: fast scan summary над таблицей (кликабельные stat-блоки) | 3 |
| 8 | UI: reuse suggestion dialog в wizard | 5 |
| 9 | UI: reuse badge на полях (используется в N стандартах) | 3 |
| 10 | UI: outlier badge + tooltip | 2 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T9.1 | Reuse: same 7 params → reuse candidate found | Integration | 2 |
| T9.2 | Reuse: different unit → no match | Integration | 1 |
| T9.3 | Reuse: different methodology → no match | Integration | 1 |
| T9.4 | Reuse: different dimensions → no match | Integration | 1 |
| T9.5 | Reuse transparency: data_point.reusedIn = [GRI 305-1, ...] | Integration | 1 |
| T9.6 | Outlier: value differs >40% → outlier flag | Integration | 1 |
| T9.7 | Outlier: value differs <40% → no flag | Integration | 1 |
| T9.8 | Multi-bound edit: warning in response when editing shared data | Integration | 1 |
| T9.9 | E2E: collection table with filters, actions | E2E | 2 |
| T9.10 | E2E: reuse dialog appears when entering duplicate data | E2E | 2 |

**Итого Sprint 9:** ~48 SP

**DoD:**
- [ ] Identity Rule reuse работает
- [ ] Reuse transparency (reusedIn[])
- [ ] Outlier detection
- [ ] Collection table полностью функциональна
- [ ] Reuse dialog в wizard

---

### Sprint 10 — Notifications + Evidence Repository + Issues

**Цель:** Уведомления, хранилище файлов, issues block

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | Notification Service: create notifications при workflow events | 5 |
| 2 | API: GET /api/notifications, PATCH /read, POST /read-all | 3 |
| 3 | SLA breach detection: cron job (deadline -3d, +3d, +7d) | 3 |
| 4 | Email integration: отправка email при critical events (submit, reject, deadline) | 5 |
| 5 | Batch review: POST /api/review/batch-approve, /batch-reject | 3 |

#### Frontend

| # | Task | SP |
|---|------|---|
| 6 | UI: notification bell + dropdown в topbar | 3 |
| 7 | UI: /evidence — Evidence repository (файлы, фильтры, upload) | 5 |
| 8 | UI: Dashboard — Issues block (critical / needs review, grouped) | 5 |
| 9 | UI: Dashboard — Priority Tasks block (overdue first, CTA buttons) | 3 |
| 10 | UI: batch approve в review UI (select multiple → approve) | 3 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T10.1 | Notification: submit → reviewer gets notification | Integration | 1 |
| T10.2 | Notification: reject → collector gets notification | Integration | 1 |
| T10.3 | Notification: mark read | Integration | 1 |
| T10.4 | SLA: deadline -3d → warning notification created | Integration | 2 |
| T10.5 | SLA: deadline +7d → critical notification to admin | Integration | 1 |
| T10.6 | Batch approve: 5 items → all approved, 5 notifications | Integration | 2 |
| T10.7 | Batch reject: comment required → 422 without comment | Integration | 1 |
| T10.8 | Evidence: list with filters (type, binding status) | Integration | 1 |
| T10.9 | E2E: notification appears after submit | E2E | 2 |

**Итого Sprint 10:** ~49 SP

**DoD:**
- [ ] Notifications при workflow events
- [ ] SLA breach detection
- [ ] Email отправляется
- [ ] Batch approve/reject
- [ ] Evidence repository
- [ ] Dashboard: issues + tasks

---

### Sprint 11 — Export + Audit + MVP Polish

**Цель:** Export, audit log UI, финальная полировка MVP

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | Readiness check: GET /api/projects/:id/export/readiness (blocking + warnings + score) | 5 |
| 2 | GRI Content Index generator: structured data → table | 5 |
| 3 | Export: POST /api/projects/:id/export (PDF via Puppeteer/wkhtmltopdf) | 5 |
| 4 | Export: Excel data dump (via exceljs) | 3 |
| 5 | Publish flow: project → published (lock all data, snapshot, audit) | 3 |
| 6 | Audit log: GET /api/audit-log (filters: entity_type, user, date range) | 3 |

#### Frontend

| # | Task | SP |
|---|------|---|
| 7 | UI: /report — GRI Content Index table + readiness check | 5 |
| 8 | UI: export page (format selection, readiness, download) | 3 |
| 9 | UI: /audit — audit log viewer (filters, timeline) | 5 |
| 10 | UI: Dashboard polish (responsive, loading states, empty states) | 3 |
| 11 | UI: user management (/settings/users — list + edit form) | 5 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T11.1 | Readiness: 0 blocking → ready, 1 blocking → not ready | Integration | 1 |
| T11.2 | Readiness: warnings count (outliers, partial) | Integration | 1 |
| T11.3 | Export GRI Index: correct disclosures, statuses, page refs | Integration | 2 |
| T11.4 | Export PDF: file generated, non-empty | Integration | 1 |
| T11.5 | Export Excel: all data_points included with metadata | Integration | 1 |
| T11.6 | Publish: project → published → all data read-only | Integration | 2 |
| T11.7 | Publish: collector tries edit after publish → 422 PROJECT_LOCKED | Integration | 1 |
| T11.8 | Audit: all CRUD actions logged with changes JSON | Integration | 1 |
| T11.9 | Audit: filter by entity_type + date range | Integration | 1 |
| T11.10 | E2E: full flow — create project → enter data → review → approve → export → publish | E2E | 5 |

**Итого Sprint 11:** ~61 SP

**DoD:**
- [ ] Readiness check перед export
- [ ] GRI Content Index export (PDF + Excel)
- [ ] Publish flow с data lock
- [ ] Audit log с фильтрами
- [ ] **MVP COMPLETE** — полный цикл от создания проекта до публикации

---

## PHASE 2: Multi-Standard + Merge

---

### Sprint 12 — Multi-Standard Seed + Merge Engine (Backend)

**Цель:** IFRS S2 + SASB данные, merge algorithm

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | Seed: IFRS S2 2023 — standard + sections + disclosures (~25) + items (~90) | 8 |
| 2 | Seed: SASB Oil&Gas — standard + disclosures (~15) + items (~50) | 5 |
| 3 | Seed: mappings IFRS S2 → shared_elements (~25, с partial) | 5 |
| 4 | Seed: mappings SASB → shared_elements (~15) | 3 |
| 5 | MergeEngine: 5-step algorithm (collect → group → classify → orphans → build) | 8 |
| 6 | API: GET /api/projects/:id/merge — merged view response | 5 |
| 7 | API: GET /api/projects/:id/merge/coverage — coverage per standard | 3 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T12.1 | Merge GRI only: all items returned, no intersections | Integration | 1 |
| T12.2 | Merge GRI + IFRS: common elements identified (e.g., Scope 1) | Integration | 2 |
| T12.3 | Merge GRI + IFRS: unique IFRS elements identified | Integration | 1 |
| T12.4 | Merge: orphan requirements (no shared_element mapping) | Integration | 1 |
| T12.5 | Coverage: GRI 100% when all data approved, IFRS < 100% | Integration | 2 |
| T12.6 | Merge: 3 standards (GRI + IFRS + SASB) — correct grouping | Integration | 2 |
| T12.7 | Performance: merge 3 standards < 3 seconds | Performance | 1 |

**Итого Sprint 12:** ~47 SP

---

### Sprint 13 — Deltas + Add Standard Flow

**Цель:** Delta requirements, добавление стандарта к проекту

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | Миграция: requirement_deltas, requirement_item_overrides | 3 |
| 2 | Delta CRUD: /api/deltas | 3 |
| 3 | Overrides CRUD: /api/overrides | 3 |
| 4 | MergeEngine: integrate deltas and overrides into merge view | 5 |
| 5 | Add standard flow: POST /api/projects/:id/standards → impact preview | 5 |
| 6 | Impact preview: POST /api/projects/:id/impact-preview/standards | 5 |
| 7 | Auto-binding: при добавлении стандарта — reuse existing data_points | 5 |
| 8 | Seed: deltas GRI ↔ IFRS S2 (financial linkage, gas breakdown) | 3 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T13.1 | Delta: create additional_item for IFRS on top of GRI | Integration | 1 |
| T13.2 | Override: stricter validation (threshold 0.4 → 0.2) | Integration | 1 |
| T13.3 | Merge + deltas: delta shows as +Δ in merge view | Integration | 2 |
| T13.4 | Add standard: impact preview shows 12 covered, 3 delta, 3 new | Integration | 2 |
| T13.5 | Add standard: existing data auto-bound, status = complete | Integration | 2 |
| T13.6 | Add standard: new items get status = missing | Integration | 1 |
| T13.7 | Add standard: completeness recalculated for new standard | Integration | 2 |

**Итого Sprint 13:** ~43 SP

---

### Sprint 14 — Merge View UI

**Цель:** Merge View экран, impact preview UI

#### Frontend

| # | Task | SP |
|---|------|---|
| 1 | UI: /merge — матрица element × standard (✔/❌/+Δ/—) | 8 |
| 2 | UI: summary bar (coverage %, common/unique/delta counts) | 3 |
| 3 | UI: фильтры (concept_domain, status, standard) | 3 |
| 4 | UI: drill-down popup (data point details, delta description) | 5 |
| 5 | UI: +Δ popup (delta description, required by which standard) | 3 |
| 6 | UI: access control (скрыть /merge для collector) | 2 |
| 7 | UI: impact preview modal (при добавлении стандарта в settings) | 5 |
| 8 | UI: "Add standard" flow в project settings | 3 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T14.1 | E2E: merge view shows matrix for GRI + IFRS | E2E | 2 |
| T14.2 | E2E: filter by status=missing → only missing rows | E2E | 1 |
| T14.3 | E2E: click ✔ → drill-down shows data point | E2E | 1 |
| T14.4 | E2E: click +Δ → popup shows delta description | E2E | 1 |
| T14.5 | E2E: collector cannot access /merge → redirect | E2E | 1 |
| T14.6 | E2E: add SASB → impact preview → confirm → recalculate | E2E | 2 |

**Итого Sprint 14:** ~40 SP

---

### Sprint 15 — Impact Analysis + Versioning

**Цель:** Impact analysis для admin, versioning mappings

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | Impact analysis: при изменении requirement_item → show affected projects/data | 5 |
| 2 | Impact analysis: при изменении mapping → show affected standards/items | 5 |
| 3 | API: GET /api/mappings/impact-preview | 3 |
| 4 | Versioning: add version, is_current, valid_from, valid_to to requirement_items | 3 |
| 5 | Versioning: mappings — new version on change, old preserved | 3 |
| 6 | Historical query: completeness for published project uses versioned mappings | 5 |

#### Frontend

| # | Task | SP |
|---|------|---|
| 7 | UI: impact preview modal в admin pages (standards, mappings) | 5 |
| 8 | UI: version history viewer (mapping changes over time) | 3 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T15.1 | Impact: change requirement_item → 12 items, 3 standards, 2 projects affected | Integration | 2 |
| T15.2 | Impact: change mapping → correct affected count | Integration | 2 |
| T15.3 | Versioning: change mapping → old version preserved with is_current=false | Integration | 1 |
| T15.4 | Historical: published project uses mapping version from publish date | Integration | 2 |
| T15.5 | E2E: admin changes mapping → impact preview → confirm | E2E | 2 |

**Итого Sprint 15:** ~41 SP

---

### Sprint 16 — Phase 2 Polish + Integration Testing

**Цель:** Полировка merge, cross-standard reuse, regression

#### Tasks

| # | Task | SP |
|---|------|---|
| 1 | Cross-record consistency: scope1 + scope2 ≠ total → flag | 3 |
| 2 | Reuse across standards: enter for GRI → auto-reuse for IFRS | 3 |
| 3 | Dashboard: coverage per standard в overview (GRI 72%, IFRS 45%) | 3 |
| 4 | Qualitative wizard: QL-1→QL-3 для narrative items | 5 |
| 5 | Bulk data import: CSV/Excel → data_points | 5 |
| 6 | Performance optimization: merge + completeness caching | 3 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T16.1 | Full integration: GRI + IFRS project, enter data, merge view correct | Integration | 3 |
| T16.2 | Reuse: enter Scope 1 for GRI → IFRS shows as complete (auto-bound) | Integration | 2 |
| T16.3 | Cross-consistency: scope1=100, scope2=200, total=250 → inconsistency flag | Integration | 2 |
| T16.4 | Import: CSV with 20 data_points → all created correctly | Integration | 2 |
| T16.5 | E2E: full multi-standard flow (GRI+IFRS) → merge → export | E2E | 5 |
| T16.6 | Regression: all Sprint 1-15 tests pass | Regression | 3 |

**Итого Sprint 16:** ~39 SP

---

## PHASE 3: Advanced

---

### Sprint 17 — Webhooks + Calculated Data

**Цель:** Outbound webhooks, расчётные показатели

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | Webhook management: CRUD /api/webhook-endpoints | 5 |
| 2 | Webhook delivery: EventEnvelope + HMAC-SHA256 signing | 5 |
| 3 | 16 webhook events (project/assignment/datapoint/review/completeness/export) | 5 |
| 4 | Webhook retry: 3 attempts with exponential backoff | 3 |
| 5 | Test webhook: POST /api/webhook-endpoints/:id/test | 2 |
| 6 | Миграция: calculation_rules, derived_data_points | 2 |
| 7 | Calculation engine: formula execution, auto-recalculate on source change | 5 |
| 8 | Derived data points: read-only flag, UI distinction | 2 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T17.1 | Webhook: create endpoint → submit data_point → webhook delivered | Integration | 2 |
| T17.2 | Webhook: HMAC signature valid | Integration | 1 |
| T17.3 | Webhook: retry on failure (mock 500 → retry → success) | Integration | 2 |
| T17.4 | Webhook: test endpoint sends sample event | Integration | 1 |
| T17.5 | Calculated: create rule (scope1+scope2=total) → derived value | Integration | 2 |
| T17.6 | Calculated: update source → derived recalculated | Integration | 2 |
| T17.7 | Calculated: derived is read-only → 422 on edit | Integration | 1 |

**Итого Sprint 17:** ~40 SP

---

### Sprint 18 — SSO + Advanced Export

**Цель:** OAuth2/SAML auth, XBRL, advanced PDF

#### Backend

| # | Task | SP |
|---|------|---|
| 1 | OAuth2 integration: authorization code flow | 8 |
| 2 | SAML 2.0 integration (optional, depending on client) | 5 |
| 3 | 2FA: TOTP setup + verification | 3 |
| 4 | XBRL export: structured data → XBRL format | 8 |
| 5 | Advanced PDF: customizable report template | 5 |
| 6 | Export queue: async job processing for large reports | 3 |

#### Frontend

| # | Task | SP |
|---|------|---|
| 7 | UI: SSO login button + OAuth callback handler | 3 |
| 8 | UI: 2FA setup page | 3 |
| 9 | UI: XBRL option in export page | 2 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T18.1 | OAuth2: login → callback → JWT issued | Integration | 2 |
| T18.2 | 2FA: setup → verify → login requires 2FA | Integration | 2 |
| T18.3 | XBRL: valid XBRL output for GRI disclosures | Integration | 2 |
| T18.4 | Async export: queued → running → completed → file downloadable | Integration | 2 |

**Итого Sprint 18:** ~48 SP

---

### Sprint 19 — Analytics + Final Polish

**Цель:** Dashboard analytics, production readiness

#### Tasks

| # | Task | SP |
|---|------|---|
| 1 | Analytics: historical trend charts (completeness over time) | 5 |
| 2 | Analytics: user activity summary (entries per user per week) | 3 |
| 3 | Analytics: SLA compliance report | 3 |
| 4 | Admin: company settings page (/settings/company) | 3 |
| 5 | Admin: roles & permissions UI (/settings/roles) | 5 |
| 6 | Performance: load testing (50 concurrent users) | 3 |
| 7 | Security: penetration testing checklist | 3 |
| 8 | Documentation: API docs (Swagger UI deployment) | 2 |
| 9 | Documentation: user guide (basic) | 3 |
| 10 | Production deployment: Dockerfile, nginx, CI/CD pipeline | 5 |

#### Тесты

| # | Тест | Тип | SP |
|---|------|-----|---|
| T19.1 | Load test: 50 concurrent users, response < 2s | Performance | 3 |
| T19.2 | Security: SQL injection attempts blocked | Security | 1 |
| T19.3 | Security: XSS attempts blocked | Security | 1 |
| T19.4 | Security: rate limiting (>100 req/min → 429) | Security | 1 |
| T19.5 | Full regression: all 150+ tests pass | Regression | 5 |
| T19.6 | E2E: complete user journey (login → project → data → review → merge → export → publish) | E2E | 5 |

**Итого Sprint 19:** ~51 SP

---

## Сводка по тестам

### Типы тестов

| Тип | Количество | Описание |
|-----|-----------|----------|
| **Unit** | ~50 | Чистые функции: validators, formatters, state machine |
| **Integration** | ~120 | API endpoints + DB: CRUD, workflow, permissions, business rules |
| **E2E** | ~25 | Браузерные сценарии: login → wizard → review → export |
| **Performance** | ~5 | Load testing, merge speed, completeness recalculation |
| **Security** | ~5 | SQL injection, XSS, rate limiting |
| **Regression** | ~3 | Full suite re-run at phase boundaries |
| **Total** | **~208** | |

### Тестовый стек

| Tool | Назначение |
|------|-----------|
| **Jest** | Unit + Integration tests |
| **Supertest** | HTTP endpoint testing |
| **Prisma** | Test database (seeded per test suite) |
| **Playwright** | E2E browser tests |
| **k6 / Artillery** | Load/performance testing |
| **Test containers** | Isolated PostgreSQL + MinIO per test run |

### Тестовая стратегия по спринту

```
Каждый спринт:
1. Новые тесты для новой функциональности
2. Regression: все предыдущие тесты проходят
3. CI: тесты запускаются на каждый PR
4. Coverage: > 80% для backend services
5. E2E: минимум 1 сценарий на ключевой user flow
```

---

## Milestones

| Milestone | Sprint | Дата (от старта) | Критерий |
|-----------|--------|-----------------|----------|
| **Foundation Ready** | 1 | +2 нед | Auth + CI/CD + error model работают |
| **Catalog Complete** | 4 | +8 нед | GRI загружен, mappings работают |
| **Data Entry MVP** | 7 | +14 нед | Wizard + workflow + review работают |
| **MVP Complete** | 11 | +22 нед | Export + publish + полный цикл |
| **Multi-Standard** | 14 | +28 нед | Merge View работает с 3 стандартами |
| **Phase 2 Complete** | 16 | +32 нед | Deltas, versioning, impact analysis |
| **Production Ready** | 19 | +38 нед | SSO, webhooks, analytics, load tested |

---

## Риски и митигации

| Риск | Вероятность | Impact | Митигация |
|------|------------|--------|-----------|
| Seed data: сложность декомпозиции стандартов | Высокая | Высокий | Начать с GRI Emissions (305), расширять постепенно |
| Merge Engine: edge cases при 3+ стандартах | Средняя | Высокий | Extensive integration tests, manual QA |
| Performance: completeness recalculation slow | Средняя | Средний | Async + caching + batch processing |
| UX: wizard complexity for non-technical users | Средняя | Средний | User testing after Sprint 7, iterate |
| Scope creep: Phase 2 features leak into MVP | Высокая | Средний | Strict sprint scope, merge engine = Phase 2 |
