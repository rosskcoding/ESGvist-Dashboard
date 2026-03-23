# Screen Registry — ESGvist Dashboard

## Summary

**Total: 37 screens / components** (34 full pages + 3 embedded components)

---

## Scenario-Driven Hardening Protocol

Этот реестр используется не только как список экранов, но и как рабочая техспека для пошаговой стабилизации продукта через реальные пользовательские сценарии.

### Execution model

Работа идёт по одному экрану или одному вкладочному блоку за итерацию:

1. Выбирается один экран или один конкретный вкладочный сценарий внутри экрана.
2. Для него фиксируются допустимые роли и ожидаемое поведение по этой странице.
3. Под него разрабатывается набор Playwright-сценариев.
4. Сценарии прогоняются на засеянной demo-среде.
5. Найденные дефекты исправляются до зелёного прогона.
6. После фикса экран остаётся в общем regression-наборе, и следующий экран добавляется поверх уже пройденных.

### Fixed demo personas

Все page-level сценарии должны опираться на один и тот же seeded demo tenant и фиксированный набор ролей:

- `platform_admin`
- `esg_manager`
- `collector` (GHG)
- `collector` (Energy/Water)
- `reviewer`
- `auditor`

Источник истины для логинов и seeded state:

- `artifacts/demo/credentials.md`
- `artifacts/demo/demo-state.json`

### Required scenario types per screen

Для каждого экрана или вкладки минимум покрываются:

1. `happy path` для основной разрешённой роли;
2. `role access` для разрешённых и запрещённых ролей;
3. `empty / loading / error state`, если экран зависит от API-загрузки;
4. `critical action flow` для основных кнопок и переходов;
5. `cross-screen navigation`, если экран является частью основного user journey;
6. `audit / side effects`, если действия на экране создают workflow, уведомления, evidence, snapshots или audit log.

### Definition of done per screen

Экран или вкладка считаются закрытыми только если:

1. все сценарии для него зелёные;
2. нет role leakage и forbidden actions дают ожидаемый отказ;
3. основной пользовательский путь проходит end-to-end на seeded данных;
4. не ломаются ранее пройденные сценарии;
5. артефакты прогона сохранены;
6. найденные баги исправлены, а не задокументированы как временное исключение, если это не согласовано отдельно.

### Execution order

Проход идёт сверху вниз по пользовательской ценности и по связанности flow:

1. Auth: `#1-3`
2. Dashboard & Completeness: `#6-7`
3. Projects: `#11-12`
4. Assignments & Users: `#19-20`
5. Company Structure & Boundary: `#8-10`
6. Data Collection & Evidence: `#13-15`
7. Review & Validation: `#16-17`
8. Merge & Analysis: `#18`
9. Report / Export / Audit: `#27-29`
10. Admin Settings: `#21-23`
11. Notifications: `#30-31`
12. Platform Admin: `#24-26`
13. AI Components: `#32-34`
14. Profile / Org / Webhooks: `#35-37`

### Regression rule

После завершения каждого нового экрана:

1. новый сценарий добавляется в общий suite;
2. прогоняется не только новый экран, но и весь накопленный набор;
3. артефакты складываются отдельно от ad-hoc тестов;
4. если экран зависит от seeded domain state, seed обновляется только совместимым способом или versioned-сценарием.

### Delivery outputs for each screen

Для каждой итерации должны появляться:

1. сценарии Playwright для конкретного экрана;
2. список дефектов, найденных этим прогоном;
3. исправления в коде;
4. итоговый прогон с артефактами;
5. короткая отметка, что экран переведён в regression baseline.

---

## 1. Auth (3 screens)

| # | Screen | Route | Roles | Doc |
|---|--------|-------|-------|-----|
| 1 | Login | `/login` | Anonymous | Auth |
| 2 | Registration | `/register` | Anonymous | Auth |
| 3 | Invite Acceptance | `/invite/:token` | Invited user | TZ-OrgSetup |

## 2. Onboarding (2 screens)

| # | Screen | Route | Roles | Doc |
|---|--------|-------|-------|-----|
| 4 | Organization Setup Wizard (5 steps) | `/onboarding` | New user | TZ-OrgSetup |
| 5 | Post-Setup Dashboard (guidance) | `/dashboard` (first login) | admin | TZ-OrgSetup |

## 3. Dashboard & Overview (2 screens)

| # | Screen | Route | Roles | Doc |
|---|--------|-------|-------|-----|
| 6 | Overview Dashboard | `/dashboard` | All | TZ-ESGManager |
| 7 | Completeness / Coverage | `/completeness` | esg_manager, admin, auditor | TZ-ESGManager |

### Screen 6 — Overview Dashboard zones:
- Progress bar (overall %)
- Completion by standard (GRI / IFRS / ESRS)
- Completion by theme (Emissions / Water / Governance)
- Completion by user
- Overdue / SLA indicators (green/yellow/orange/red)
- Boundary Summary (selected boundary, entities in scope, excluded, snapshot status)
- Boundary Impact on Completeness
- Priority Tasks block
- Heatmap visualization

### Screen 7 — Completeness zones:
- Summary header (%, boundary name, snapshot date, entity count)
- By standard breakdown (progress bars)
- By theme/category breakdown
- Disclosure-level detail table (covered/missing/excluded entities)
- Contextual explanation text

## 4. Company Structure & Boundary (3 screens)

| # | Screen | Route | Roles | Doc |
|---|--------|-------|-------|-----|
| 8 | Company Structure (React Flow) | `/settings/company-structure` | admin, esg_manager | TZ-CompanyStructure |
| 9 | Boundary Definitions | `/settings/boundaries` | admin | TZ-BoundaryIntegration |
| 10 | Boundary Preview / Compare | embedded in Project Settings | esg_manager | TZ-BoundaryIntegration |

### Screen 8 — Company Structure zones:
- Left panel: entity tree with search/filter
- Center: React Flow graph (nodes = entities, edges = ownership/control)
- Right panel: selected entity card (attributes, ownership links, control links, boundary membership)
- Top toolbar: view mode toggle (Structure / Control / Boundary)

### Screen 9 — Boundary Definitions:
- List of boundary_definitions
- Detail: name, type, is_default, membership list, consolidation method per entity
- Calculate membership button
- Snapshot history

## 5. Projects (2 screens)

| # | Screen | Route | Roles | Doc |
|---|--------|-------|-------|-----|
| 11 | Project List | `/projects` | esg_manager, admin | TZ-ESGManager |
| 12 | Project Settings | `/projects/:id/settings` | esg_manager, admin | TZ-ESGManager |

### Screen 12 — Project Settings zones:
- Basic info (name, period, status, deadline)
- Standards selection (multi-select + impact preview)
- Reporting Boundary block (selector, snapshot status, entities count)
- Workflow controls (draft → active → review → published)
- Readiness check trigger

## 6. Data Collection (3 screens)

| # | Screen | Route | Roles | Doc |
|---|--------|-------|-------|-----|
| 13 | Collection Table | `/collection` | collector, esg_manager | TZ-User |
| 14 | Data Entry Wizard (4 steps) | `/collection/:id` | collector | TZ-User |
| 15 | Evidence Repository | `/evidence` | collector, esg_manager, auditor | TZ-Evidence |

### Screen 13 — Collection Table columns:
- Shared element code/name
- Status badge (missing/partial/complete)
- Entity name
- Facility
- Boundary status badge
- Consolidation mode
- Reuse badge (used in X standards)
- Filters: entity, boundary, status, standard, theme

### Screen 14 — Data Entry Wizard steps:
- Step 1: Assigned metrics list
- Step 2: Dynamic form (value, unit, dimensions, methodology, entity context, evidence upload)
- Step 3: Preview & validation summary
- Step 4: Submit (gate check inline)

### Screen 15 — Evidence Repository:
- List (type, title, upload date, created by, binding status)
- Filters: type (file/link), bound/unbound, date range
- File preview, download, delete
- Linked data points display

## 7. Review & Validation (2 screens)

| # | Screen | Route | Roles | Doc |
|---|--------|-------|-------|-----|
| 16 | Review Split Panel | `/validation` | reviewer, auditor (read-only) | TZ-Reviewer |
| 17 | Batch Review | embedded in `/validation` | reviewer | TZ-Reviewer |

### Screen 16 — Review Split Panel:
- Left: data point list (sortable by urgency, submit date; filters: status, standard)
- Right: detail panel
  - Value + unit + dimensions
  - YoY comparison
  - Standard requirement context
  - Evidence section (files, links, required indicator)
  - Boundary context (entity, inclusion reason, consolidation, snapshot)
  - Threaded comments
  - Action buttons: Approve / Reject / Request Revision
  - Review reason codes (OUT_OF_BOUNDARY_SCOPE, WRONG_CONSOLIDATION_CONTEXT)
  - Outlier flags (% difference)
  - Reuse impact indicator

## 8. Merge & Analysis (1 screen)

| # | Screen | Route | Roles | Doc |
|---|--------|-------|-------|-----|
| 18 | Merge View Matrix | `/merge` | esg_manager, admin, auditor | TZ-Admin |

### Screen 18 — Merge View zones:
- Matrix: rows = shared elements, columns = standards
- Cells: status color (red/yellow/green) + binding type
- Summary bar (coverage %, common/unique/delta counts)
- Boundary Scope Layer (entities in scope, excluded, consolidation)
- Filters: standard, status, domain
- Drill-down on click

## 9. Assignments & Users (2 screens)

| # | Screen | Route | Roles | Doc |
|---|--------|-------|-------|-----|
| 19 | Assignments Matrix | `/settings/assignments` | esg_manager, admin | TZ-ESGManager |
| 20 | User Management | `/settings/users` | admin | TZ-PlatformAdmin |

### Screen 19 — Assignments Matrix columns:
- Shared element
- Entity / Facility
- Boundary included
- Consolidation method
- Collector (dropdown)
- Reviewer (dropdown)
- Deadline (date picker)
- Status
- SLA badge
- Bulk edit, inline editing
- Boundary Change Impact Preview modal

## 10. Admin Settings (3 screens)

| # | Screen | Route | Roles | Doc |
|---|--------|-------|-------|-----|
| 21 | Standards Management | `/settings/standards` | admin | TZ-Admin |
| 22 | Requirement Items Config | `/settings/standards/:id/requirements` | admin | TZ-Admin |
| 23 | Shared Elements & Mappings | `/settings/shared-elements` | admin | TZ-Admin |

## 11. Platform Admin (3 screens)

| # | Screen | Route | Roles | Doc |
|---|--------|-------|-------|-----|
| 24 | Tenant List | `/platform/tenants` | platform_admin | TZ-PlatformAdmin |
| 25 | Create Tenant Wizard | `/platform/tenants/new` | platform_admin | TZ-PlatformAdmin |
| 26 | Tenant Details (tabs) | `/platform/tenants/:id` | platform_admin | TZ-PlatformAdmin |

## 12. Export & Report (2 screens)

| # | Screen | Route | Roles | Doc |
|---|--------|-------|-------|-----|
| 27 | Report Readiness + Export | `/report` | esg_manager, admin | TZ-ESGManager |
| 28 | Report Preview (modal) | `/report/preview` | esg_manager | TZ-ESGManager |

### Screen 27 — Report Readiness zones:
- Readiness check summary (ready/warnings/blockers)
- Blocking issues list
- Warnings list
- Boundary Validation block (snapshot locked, entities, overrides)
- Export format selection (GRI Index, PDF, Excel, XBRL)
- Generate / Preview / Publish buttons

## 13. Audit (1 screen)

| # | Screen | Route | Roles | Doc |
|---|--------|-------|-------|-----|
| 29 | Audit Log Viewer | `/audit` | admin, auditor | TZ-ESGManager |

## 14. Notifications (2 components)

| # | Screen | Route | Roles | Doc |
|---|--------|-------|-------|-----|
| 30 | Notification Bell (topbar) | global component | All | TZ-Notifications |
| 31 | Notification Center | `/notifications` | All | TZ-Notifications |

## 15. AI Components (3 components)

| # | Screen | Route | Roles | Doc |
|---|--------|-------|-------|-----|
| 32 | AI Copilot Side Panel | global component | All | TZ-AIAssistance |
| 33 | Inline AI Explain (tooltip) | field-level | All | TZ-AIAssistance |
| 34 | Review AI Assistant | embedded in `/validation` | reviewer | TZ-AIAssistance |

## 16. Profile & Settings (3 screens)

| # | Screen | Route | Roles | Doc |
|---|--------|-------|-------|-----|
| 35 | User Profile | `/settings/profile` | All | Standard |
| 36 | Organization Settings | `/settings` | admin | TZ-OrgSetup |
| 37 | Webhook Management | `/settings/webhooks` | admin | TZ-Notifications |

---

## Implementation Priority

### Phase 1 — Core (Sprint F1-F3)
1. Login / Register / Invite (#1-3)
2. Organization Setup Wizard (#4)
3. Dashboard (#6)
4. Collection Table + Data Entry Wizard (#13-14)
5. Review Split Panel (#16)
6. Notification Bell (#30)

### Phase 2 — Management (Sprint F4-F6)
7. Project List + Settings (#11-12)
8. Assignments Matrix (#19)
9. Merge View (#18)
10. Completeness (#7)
11. Company Structure (#8)
12. Evidence Repository (#15)
13. User Management (#20)
14. Notification Center (#31)

### Phase 3 — Admin & Advanced (Sprint F7-F9)
15. Standards Management (#21)
16. Requirement Items Config (#22)
17. Shared Elements & Mappings (#23)
18. Boundary Definitions (#9)
19. Report Readiness + Export (#27-28)
20. Audit Log (#29)
21. AI Copilot Panel (#32)
22. Platform Admin screens (#24-26)

### Phase 4 — Polish (Sprint F10)
23. Review AI Assistant (#34)
24. Inline AI Explain (#33)
25. Batch Review (#17)
26. Webhook Management (#37)
27. Org Settings (#36)
28. User Profile (#35)
