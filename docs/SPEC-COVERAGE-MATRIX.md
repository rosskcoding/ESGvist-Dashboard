# Spec Coverage Matrix

Актуализация: 2026-03-23

## Статусы

- `done` — реализовано по смыслу и присутствует в коде/UI.
- `partial-high` — ядро реализовано, остались важные, но локальные хвосты.
- `partial` — блок рабочий, но до ТЗ не дотягивает по нескольким заметным подпунктам.
- `partial-low` — есть только часть фундамента, до требований ещё далеко.
- `gap` — в коде почти нет реализации или она только номинальная.

## Матрица по документам

| Документ | Статус | Что закрыто | Что недоделано / пробелы |
| --- | --- | --- | --- |
| `ARCHITECTURE.md` | `partial-high` | FastAPI backend, `route -> schema -> service -> repo`, policies, event registry, worker/job runner, audit, tests, screen regression | Нет полноценного domain layer как первого класса, нет production observability уровня metrics/tracing, архитектурные read-endpoints не везде одинаково защищены |
| `BACKLOG.md` | `partial-high` | EPIC 1-8 в основном покрыты: standards, shared elements, mappings, merge, collection, workflow, completeness, projects, export, evidence | Закрылась часть backlog по formula/derived, outlier, digest и form-config backend, но UI и regression coverage для новых блоков ещё неполные |
| `ERROR-MODEL.md` | `partial-high` | `AppError`, единый response format, `request_id`, permission/error codes, gate errors | Не все коды из ТЗ доведены до фактического runtime-использования, нет полной матрицы покрытия error codes тестами |
| `SPRINT-PLAN.md` | `partial-high` | Реализована большая часть foundation/backend/frontend sprint scope, есть UI e2e и demo flows | Финальные polish/ops/perf части спринтов не доведены до формального completion |
| `TZ-AIAssistance.md` | `partial` | AI endpoints, role gating, audit logging, provider abstraction, fallback/grounded provider, review assist | Нет real LLM/provider integration с tools/streaming, нет dependency graph grounding, нет anomaly/outlier tools, нет action execution loop |
| `TZ-Admin.md` | `partial-high` | UI и backend для standards, sections, disclosures, requirement items, dependencies, shared elements, mappings, deltas, impact analysis; backend для form configs и mapping history/diff появился | Нет bulk import каталога, нет UI управления shared element dimensions, нет UI для form configuration, нет UI для mapping history/diff |
| `TZ-BackendArchitecture.md` | `partial-high` | Сервисная архитектура, policies, workers, event handlers, repo слой, тесты | Нет полноценной миграционной истории как части архитектурного контракта, не все read endpoints проходят через единый auth/policy слой |
| `TZ-BoundaryIntegration.md` | `partial-high` | Boundaries, memberships, snapshots, project boundary settings, assignments preview, boundary-aware completeness/readiness, boundary summary | Не весь boundary context доведён до каждого UI-паттерна из ТЗ: merge/review/collection badges и explanation layer закрыты не полностью |
| `TZ-CompanyStructure.md` | `partial-high` | Company structure UI, entities, parent-child, ownership, control, entity tree, effective ownership, boundary linkage | Нет продвинутых override/workflow сценариев и более богатых bulk/admin операций по структуре |
| `TZ-ESGManager.md` | `partial-high` | Projects, project settings, standards attachment, assignments, dashboard, merge, readiness, export, SLA fields | Outlier/warning management неполный, project quality controls и escalation UX не полностью доведены |
| `TZ-ESGvist-v1.md` | `partial-high` | Основной контур системы реализован: standards, mappings, projects, data points, evidence, workflow, review, export, notifications, screens; backend для `calculation_rules` и derived data points появился | Нет UI для calculation rules / derived flows, нет полного dimension engine, outlier/derived покрытие тестами и UX пока неполные |
| `TZ-Evidence.md` | `partial-high` | Evidence repository, multipart upload endpoint, download endpoint, storage abstraction (`local` / `minio`), data point binding, requirement binding, audit/provenance, UI repository | Collection wizard пока ещё использует старый metadata-only flow вместо нового upload endpoint; не хватает полной e2e интеграции нового upload pipeline |
| `TZ-NFR.md` | `partial` | Health checks, request id, retries, idempotency, worker jobs, auth/security foundation, file validation limits, `/api/metrics`, Prometheus middleware, storage health | Нет tracing, нет benchmark/profiling evidence, нет backup/restore operational layer, нет transport/security hardening beyond app basics |
| `TZ-Notifications.md` | `partial-high` | In-app notifications, unread/read, preferences, email abstraction, event wiring, webhooks, retry/dead-letter, scheduled jobs, digest model + worker | Digest пока backend-only, без явного UI/ops wiring; нет production mail/webhook delivery infra beyond abstractions, нет richer delivery analytics |
| `TZ-OrgSetup.md` | `partial-high` | Register/login, org setup, root entity, default boundary baseline, invitations, invite acceptance, organization settings, auth settings | Нет полноценного onboarding wizard с богатым guided UX, AI onboarding help отсутствует |
| `TZ-PermissionMatrix.md` | `partial-high` | Role bindings, platform admin scope, object access helpers, screen role gates; catalog/read routes теперь проводят `RequestContext` | Read-политики по catalog API всё ещё широкие и не везде явно role-specific на уровне сервисов; нужен финальный pass по permission semantics |
| `TZ-PlatformAdmin.md` | `partial-high` | Tenant list/create/update/archive, self-registration toggle, platform jobs, platform UI, SSO/auth settings basis, support session backend endpoints | Support mode пока backend-only, без UI и без полноценного tenant context switch / assisted session flow |
| `TZ-Reviewer.md` | `partial-high` | Validation queue, split review UI, approve/reject/revision, batch ops, comments, auditor read-only path, AI review assist, backend outlier detection | Нужно добить качество heuristics и покрытие тестами; reviewer UX ещё не использует расширенное объяснение outlier/deviation в полном объёме |
| `TZ-User.md` | `partial-high` | Collection table, wizard, revisions, evidence linking, project-scoped collection, role flows, E2E screen coverage | Полный dimension workflow ограничен; collection wizard пока не переведён на новый real upload endpoint; document-heavy scenarios закрыты не полностью |
| `TZ-WorkflowGateMatrix.md` | `partial-high` | Gate engine, gate-check endpoint, workflow transitions, export gates, evidence/completeness gates, audit | Нет полного покрытия advanced gates из ТЗ: dimension-specific blockers, outlier/consistency rules и часть project-level gate semantics ещё упрощены |
| `SCREENS-REGISTRY.md` | `partial-high` | Screen baseline пройден, role journeys и edge/error waves начаты, Playwright artifacts есть | Phase 3 ещё не доведён до полного destructive/error-path покрытия по всем экранам |

## Подтверждённо реализованные сильные блоки

1. Auth / RBAC / role bindings / platform admin.
2. Org setup, invitations, SSO shell, 2FA shell.
3. Standards catalog, disclosures, requirement items, dependencies.
4. Shared elements, mappings, deltas, merge layer.
5. Company structure, boundary, snapshots, boundary-aware completeness/readiness.
6. Projects, assignments, SLA, dashboard, export jobs.
7. Data collection, review, comments, audit, notifications, webhooks.
8. Screen baseline + deep role journeys + edge-case packs в Playwright.

## Основные реальные незакрытые хвосты

### P0

1. `Collection wizard upload integration`: экран всё ещё шлёт fake metadata в старый `/evidences` flow вместо нового upload endpoint.
2. `Regression green state`: после изменения mapping versioning тестовый набор больше не зелёный, текущий контракт и тесты расходятся.
3. `Frontend coverage for new backend blocks`: calculations, form configs, support mode, digest пока почти не представлены в UI.

### P1

1. `Admin form configuration UI`: backend есть, но UI и e2e на него не собраны.
2. `Shared element dimensions UX`: backend есть, UI управления dimensions фактически не доведён.
3. `Mapping history/diff UI`: backend есть, но это не surfaced в admin screens.
4. `Digest notifications UI/ops`: worker и модель есть, но нет явного user/admin flow вокруг digest.
5. `Platform support mode UI`: backend endpoints есть, но нет frontend/admin workflow.
6. `Outlier heuristics hardening`: база есть, но её ещё надо калибровать и покрывать тестами.

### P2

1. `Observability`: metrics появились, но tracing и benchmark layer всё ещё отсутствуют.
2. `Onboarding polish`: guided wizard / AI assistance.
3. `Phase 3 edge coverage`: расширить destructive/error scenarios по всем экранным блокам.

## Рекомендуемый порядок добивки

1. Закрыть `P0`: collection wizard upload integration, вернуть green test suite, подключить UI к новым backend blocks.
2. Затем `P1`: form config UI, dimensions UX, mapping history UI, digest/support workflows, outlier hardening.
3. После этого `P2`: tracing/benchmark, onboarding polish, расширенный edge/error regression.

## Recheck delta (2026-03-23, second pass)

### Что реально улучшилось относительно предыдущей матрицы

1. Появился настоящий evidence upload/download + storage abstraction.
2. Появились backend `calculation_rules` и derived data points.
3. Появились backend `form_configurations`.
4. Появились backend metrics и `/api/metrics`.
5. Появился backend digest worker.
6. Появились backend support sessions для `platform_admin`.
7. Catalog routes получили `RequestContext`.

### Что обнаружилось при перепроверке

1. Collection wizard всё ещё не использует новый upload endpoint.
2. Mapping versioning изменил поведение duplicate create, и тесты сейчас не согласованы с новым контрактом.
3. Существенная часть новых блоков уже есть в backend, но пока не поднята в UI и не закрыта e2e сценариями.
