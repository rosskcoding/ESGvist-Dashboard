# Аудит реализации по техспекам

Дата: 2026-03-24

## Как проверял

- Сверил все `docs/TZ-*.md` с backend/API, frontend/UI и тестами.
- Прогнал targeted backend suites:
  - `backend/tests/test_architecture.py`
  - `backend/tests/test_gaps.py`
  - `backend/tests/test_full_coverage.py`
  - `backend/tests/test_workflow.py`
  - `backend/tests/test_data_points.py`
  - `backend/tests/test_review_queue.py`
  - `backend/tests/test_notifications.py`
  - `backend/tests/test_platform_hardening.py`
  - `backend/tests/test_ai_tools.py`
  - `backend/tests/test_deltas_ai.py`
- Затем прогнал полный backend suite: `271 passed`, `8 failed`.

## Важное замечание по полному test suite

Падения в полном backend suite выглядят как устаревшие тесты, а не как явная продуктовая поломка:

- `backend/tests/test_standards.py`
- `backend/tests/test_shared_elements.py`
- `backend/tests/test_requirement_items.py`

Во всех 8 падениях тесты делают `GET` на catalog/read endpoints без auth/org headers и ожидают `200`, а текущие routes уже требуют контекст пользователя. То есть после auth hardening тесты не были синхронизированы с новым контрактом.

## Статусы

- `done` - реализовано по смыслу и подтверждается кодом/тестами.
- `partial-high` - основной контур реализован, хвосты в UI или отдельных сценариях.
- `partial` - модуль рабочий, но до ТЗ не дотягивает по нескольким заметным блокам.
- `gap` - заметная часть ТЗ отсутствует.

## TZ-AIAssistance.md

Статус: `partial-high`

Подтверждено:

- Есть отдельные AI endpoints: `backend/app/api/routes/ai.py`.
- Есть orchestration со safety gates, audit trail и fallback: `backend/app/services/ai_service.py`.
- Есть реальные LLM adapters для Anthropic/OpenAI и streaming: `backend/app/infrastructure/llm_client.py`.
- Есть frontend inline explain и copilot: `frontend/components/ai-inline-explain.tsx`, `frontend/components/ai-copilot.tsx`.
- AI tool/gate поведение подтверждено тестами: `backend/tests/test_ai_tools.py`, `backend/tests/test_deltas_ai.py`.

Пробелы:

- AI подключен не ко всем описанным в ТЗ surface areas; wiring выборочный, а не повсеместный.
- Нет отдельного frontend слоя, который бы системно встраивал explain/help в каждый badge/error/boundary touchpoint.

## TZ-Admin.md

Статус: `partial-high`

Подтверждено:

- Standards CRUD, sections, disclosures, requirement items: `backend/app/api/routes/standards.py`, `backend/app/api/routes/requirement_items.py`, `frontend/app/(app)/settings/standards/page.tsx`, `frontend/app/(app)/settings/standards/[id]/requirements/page.tsx`.
- Shared elements и mappings: `backend/app/api/routes/shared_elements.py`, `backend/app/api/routes/mappings.py`, `frontend/app/(app)/settings/shared-elements/page.tsx`.
- Impact analysis и mapping versioning backend: `backend/app/api/routes/impact.py`, `backend/app/services/mapping_service.py`.
- Админский backend хорошо покрыт тестами: `backend/tests/test_standards.py`, `backend/tests/test_requirement_items.py`, `backend/tests/test_shared_elements.py`, `backend/tests/test_mappings.py`.

Пробелы:

- Нет frontend UI для dimensions shared elements, хотя backend endpoints есть: `backend/app/api/routes/shared_elements.py`.
- Нет frontend UI для mapping history/diff, хотя backend endpoints есть: `backend/app/api/routes/mappings.py`.
- Нет admin UI для form configurations; backend есть, frontend management page отсутствует.
- Не найден bulk import flow каталога стандартов/требований.

## TZ-BackendArchitecture.md

Статус: `partial-high`

Подтверждено:

- Архитектура реально разложена на `api/routes`, `services`, `repositories`, `policies`, `workflows`, `events`: см. `backend/app/*`.
- Middleware, request-id, exception mapping, router registration: `backend/app/main.py`, `backend/app/core/middleware.py`.
- Есть gate/workflow слой: `backend/app/workflows/gates/*`, `backend/app/services/workflow_service.py`.
- Есть архитектурный тест на изоляцию domain layer: `backend/tests/test_architecture.py`.

Пробелы:

- Domain layer номинальный: фактически в `backend/app/domain` есть только `workflow_state.py`.
- Полный suite не зеленый из-за устаревших catalog tests, значит архитектурный контракт auth/read endpoints еще не синхронизирован на уровне regression suite.

## TZ-BoundaryIntegration.md

Статус: `partial-high`

Подтверждено:

- Project boundary selection и snapshot save: `frontend/app/(app)/projects/[id]/settings/page.tsx`, `backend/app/api/routes/snapshots.py`.
- Merge учитывает boundary scope: `frontend/app/(app)/merge/page.tsx`, `backend/tests/test_merge.py`.
- Completeness/report/dashboard используют boundary context: `frontend/app/(app)/completeness/page.tsx`, `frontend/app/(app)/report/page.tsx`, `frontend/app/(app)/dashboard/page.tsx`.
- Review panel показывает boundary context: `frontend/app/(app)/validation/page.tsx`, `backend/app/services/review_service.py`.

Пробелы:

- Snapshot history в boundary settings не подключен к backend: `frontend/app/(app)/settings/boundaries/page.tsx:392` и `frontend/app/(app)/settings/boundaries/page.tsx:393`.
- Не весь explanation layer из ТЗ surfaced одинаково на всех экранах.

## TZ-CompanyStructure.md

Статус: `partial-high`

Подтверждено:

- CRUD сущностей, ownership/control links, root entity setup: `backend/app/api/routes/entities.py`, `backend/app/services/entity_service.py`.
- Entity tree и effective ownership: `backend/app/api/routes/entity_tree.py`, `backend/tests/test_full_coverage.py`, `backend/tests/test_entities.py`.
- Company structure UI и boundaries UI существуют: `frontend/app/(app)/settings/company-structure/page.tsx`, `frontend/app/(app)/settings/boundaries/page.tsx`.
- Snapshot backend реализован: `backend/app/api/routes/snapshots.py`, `backend/app/db/models/boundary_snapshot.py`.

Пробелы:

- Snapshot history в UI не завершен.
- Не видно расширенных bulk/admin операций и override сценариев, описанных в ТЗ.

## TZ-ESGManager.md

Статус: `partial-high`

Подтверждено:

- Projects list/settings, standards attachment, boundary, workflow actions: `frontend/app/(app)/projects/page.tsx`, `frontend/app/(app)/projects/[id]/settings/page.tsx`, `backend/app/api/routes/projects.py`.
- Assignment matrix, backup collector, escalation fields: `frontend/app/(app)/settings/assignments/page.tsx`, `backend/app/services/project_service.py`.
- SLA checks и escalation backend: `backend/app/services/sla_service.py`, `backend/tests/test_sla_service.py`.
- Dashboard/readiness/export: `frontend/app/(app)/dashboard/page.tsx`, `frontend/app/(app)/report/page.tsx`, `backend/tests/test_export_jobs.py`.

Пробелы:

- Нет отдельного UX для управления outlier/warning backlog на уровне проекта.
- Quality controls и escalation UX больше опираются на badges/statuses, чем на отдельный управленческий workflow.

## TZ-ESGvist-v1.md

Статус: `partial-high`

Подтверждено:

- Основной системный контур собран: auth, org, standards, mappings, projects, collection, review, evidence, export, notifications, AI, platform admin.
- Большая часть backend покрыта тестами и реально проходит.

Пробелы:

- Нет frontend surface для calculation rules: есть `backend/app/api/routes/calculations.py`, но нет отдельного UI.
- Нет frontend/admin surface для form configurations.
- Value/dimension engine ограничен по сравнению с полным ТЗ.

## TZ-Evidence.md

Статус: `partial-high`

Подтверждено:

- Multipart upload/download/delete и storage abstraction: `backend/app/api/routes/data_points.py`, `backend/app/services/evidence_service.py`, `backend/app/infrastructure/storage.py`.
- Evidence repository UI: `frontend/app/(app)/evidence/page.tsx`.
- Collection wizard реально использует upload endpoint: `frontend/app/(app)/collection/[id]/page.tsx`.
- Evidence binding к data points и requirement items есть в backend.

Пробелы:

- Не видно полного набора rich-preview/document-heavy UX сценариев из ТЗ.
- Основной поток закрыт, но глубина работы с документами все еще проще, чем в спеке.

## TZ-NFR.md

Статус: `partial`

Подтверждено:

- Request ID: `RequestIdMiddleware` генерирует UUID, принимает `X-Request-ID`, добавляет `X-Request-Duration` (middleware.py lines 14-62). Error envelope: `AppError.to_response()` → `{error: {code, message, details[], requestId}}` (exceptions.py lines 4-63).
- Health: `/api/health` (basic), `/api/health/db` (SELECT 1), `/api/health/redis` (ping), `/api/health/storage` (storage backend), `/api/metrics` (Prometheus) — всё в `health.py`.
- Prometheus: `REQUEST_LATENCY` histogram, `REQUEST_COUNT` counter, `ACTIVE_REQUESTS` gauge, `DB_QUERY_LATENCY` histogram — `metrics.py`. `MetricsMiddleware` зарегистрирован в `main.py` (line 57).
- Retries: webhook — `RETRY_DELAYS_SECONDS = [1, 2, 4, 8, 16]`, dead letter queue (webhook_service.py lines 265-309, 375-400). Export — `EXPORT_RETRY_DELAYS_SECONDS = [1, 2, 4]`, idempotency через `idempotency_repo.py`, header `X-Idempotency-Key` (export_service.py line 582+).

Пробелы:

- **Tracing/OpenTelemetry**: не найдено. Grep по `otel`, `opentelemetry`, `tracing`, `jaeger`, `zipkin` — 0 результатов в production-коде.
- **Backup/restore**: не найдено. Grep по `backup`, `restore`, `pg_dump` — 0 результатов.
- **Security headers (CSP/HSTS/X-Frame-Options)**: не найдено в application layer. `main.py` содержит только CORS middleware, нет security headers middleware. Все grep-результаты по `Content-Security-Policy`, `Strict-Transport`, `X-Frame-Options` — только в docs и test artifacts.
- Нет benchmark/profiling evidence в repo.

## TZ-Notifications.md

Статус: `partial`

Подтверждено:

- In-app notification center, filters, mark-read, preferences UI: `frontend/app/(app)/notifications/page.tsx`.
- Backend notifications, email abstraction, webhook delivery/retry, platform jobs: `backend/app/services/notification_service.py`, `backend/app/services/webhook_service.py`, `backend/app/api/routes/notifications.py`, `backend/app/api/routes/platform.py`.
- Digest worker реально есть: `backend/app/workers/digest_worker.py`.

Пробелы:

- ~~`digest_frequency` используется внутри сервиса, но не surfaced в API schema~~ **НЕВЕРНО**: `digest_frequency` реально exposed в `NotificationPreferencesOut` и `NotificationPreferencesUpdate` в `backend/app/schemas/notifications.py` (lines 8, 15). Claim отозван.
- Нет более богатой delivery analytics/ops поверхности.

## TZ-OrgSetup.md

Статус: `partial`

Подтверждено:

- Register/login pages есть: `frontend/app/(auth)/register/page.tsx`, `frontend/app/(auth)/login/page.tsx`.
- Invite accept flow есть: `frontend/app/(auth)/invite/[token]/page.tsx`, `backend/app/api/routes/invitations.py`.
- Organization setup backend, root entity и admin binding создаются: `backend/app/api/routes/entities.py`, `backend/app/services/entity_service.py`.
- 2FA и auth settings shell есть: `backend/app/api/routes/auth.py`, `frontend/app/(app)/settings/profile/page.tsx`, `frontend/app/(app)/settings/page.tsx`.

Пробелы:

- Не найден frontend onboarding wizard `/onboarding`.
- Регистрация ведет сразу на `/dashboard`, а не в setup flow: `frontend/app/(auth)/register/page.tsx:57`-`frontend/app/(auth)/register/page.tsx:60`.
- Нет guided post-setup onboarding UX.

## TZ-PermissionMatrix.md

Статус: `partial-high`

Подтверждено:

- Scope-aware role model и `role_bindings`: `backend/app/repositories/role_binding_repo.py`, `backend/app/db/models/role_binding.py`.
- `RequestContext` поддерживает platform scope, org scope и support mode headers: `backend/app/core/dependencies.py`.
- Screen/API role guards реализованы по ключевым зонам: validation, merge, notifications, platform, users.
- Права хорошо подтверждены тестами: `backend/tests/test_platform_hardening.py`, `backend/tests/test_review_queue.py`, `backend/tests/test_gaps.py`.

Пробелы:

- Полный regression suite не синхронизирован с новыми auth semantics для catalog reads.
- Support mode реализован на backend уровне, но без полноценного UI workflow.

## TZ-PlatformAdmin.md

Статус: `partial-high`

Подтверждено:

- Tenants list/create/detail pages есть: `frontend/app/(app)/platform/tenants/page.tsx`, `frontend/app/(app)/platform/tenants/new/page.tsx`, `frontend/app/(app)/platform/tenants/[id]/page.tsx`.
- Platform admin backend для tenant lifecycle, jobs, self-registration config и support session есть: `backend/app/api/routes/platform.py`.
- Platform hardening и audit подтверждены тестами: `backend/tests/test_platform_hardening.py`.

Пробелы:

- ~~Не найден frontend UI для support session / support mode / tenant context switch.~~ **НЕВЕРНО**: Support mode UI реально существует:
  - `frontend/lib/support-mode.ts` — state management (localStorage, `startSupportMode()`, `stopSupportMode()`, `readSupportMode()`).
  - `frontend/app/(app)/platform/tenants/[id]/page.tsx` — dialog для start support session с полем reason.
  - `frontend/lib/api.ts` — автоматический inject `X-Support-Session-Id` header.
  - Backend: `POST /api/platform/tenants/{tenant_id}/support-session`, `DELETE /api/platform/support-session/{session_id}` в `backend/app/api/routes/platform.py` (lines 467-556), модель `backend/app/db/models/support_session.py`.
  Claim отозван. Статус PlatformAdmin повышен до `done` по основному контуру.

## TZ-Reviewer.md

Статус: `partial-high`

Подтверждено:

- Review split panel, approve/reject/revision: `frontend/app/(app)/validation/page.tsx`, `backend/app/api/routes/review.py`, `backend/app/services/review_service.py`.
- **Batch actions полностью реализованы**: `runBatchAction()` (lines 327-363 validation page), API calls к `/review/batch-approve`, `/review/batch-reject`, `/review/batch-request-revision`. UI с checkbox select-all, reason dropdown, comment textarea (lines 502-585).
- Threaded comments и author metadata: `backend/app/api/routes/comments.py`, `frontend/app/(app)/validation/page.tsx`.
- **Outlier detection подключен**: `OutlierService` импортирован и вызывается batch-проверкой в `review_service.py` (line 359), результат сериализуется с `is_outlier`, `outlier_reason`, `previous_value` (lines 428-439). UI показывает `AlertTriangle` icon при `is_outlier: true` (line 631).
- Evidence, boundary context, AI review assist, auditor read-only path — всё есть.

Пробелы:

- Нет статуса `not_applicable` — review actions ограничены `approved`/`rejected`/`needs_revision`.
- Нет structured justification для подтверждения outlier (reviewer видит warning, но нет отдельной формы "confirm outlier with reason").

## TZ-User.md

Статус: `partial`

Подтверждено:

- Collection list, status-first layout, reuse badges, boundary badges: `frontend/app/(app)/collection/page.tsx`.
- Wizard с draft/save/submit/gate-check/evidence upload: `frontend/app/(app)/collection/[id]/page.tsx`.
- Review comment loop и resubmission backend есть.

Пробелы:

- DataPoint model и wizard поддерживают только `numeric_value` и `text_value`; не видно full support для `date`, `enum`, `json`: `backend/app/db/models/data_point.py`, `backend/app/schemas/data_points.py`.
- Dimensions: DB модель (`DataPointDimension`) принимает произвольный `dimension_type: str`, комментарий в `SharedElementDimension` списком `scope|gas|category|facility|geography` (5 типов), но API schema `DimensionFlagsOut` возвращает только 3 boolean-флага: `scope`, `gas_type`, `category`. Расхождение между DB flexibility и API contract.
- Wizard не driven через form-config. `wizard-renderer.tsx` **существует и полностью функционален**, но **нигде не импортирован**. Collection flow в `collection/[id]/page.tsx` использует hardcoded step-based wizard (steps 0-3). Form-config backend полностью реализован (`backend/app/api/routes/form_configs.py`, `backend/app/services/form_config_service.py`, `backend/app/repositories/form_config_repo.py`), admin UI есть (`frontend/app/(app)/settings/form-configs/page.tsx`), но runtime использование отсутствует.
- Backend calculation rules (`backend/app/api/routes/calculations.py`) реализованы (create, list, recalculate), но frontend UI для управления ими не существует.

## TZ-WorkflowGateMatrix.md

Статус: `partial-high`

Подтверждено:

- Есть `GateEngine`, gate types и структурированный результат: `backend/app/workflows/gates/base.py`.
- Workflow transitions и `POST /api/gate-check`: `backend/app/services/workflow_service.py`, `backend/app/api/routes/workflow.py`.
- Gate checks логируются в audit: `backend/app/services/workflow_service.py`.
- Project/export workflows тоже используют gates: `backend/app/services/project_service.py`, `backend/app/services/export_service.py`.
- Тесты по workflow/gate проходят: `backend/tests/test_workflow.py`, `backend/tests/test_export_jobs.py`.

Пробелы:

- Реестр gate-кодов и advanced semantics из ТЗ реализованы не на 100 процентов.
- Severity есть, но **не configurable**: `GateFailure.severity` принимает `"blocker"` или `"warning"`, `GateEngine.check()` разделяет их (lines 45-48), но значения хардкожены в каждом gate (CompletenessGate = всегда `"blocker"`, BoundaryGate = mixed). Нет admin API для per-gate severity override.
- Gate types реализованы (6 шт): `data`, `completeness`, `boundary`, `evidence`, `review`, `workflow`.
- Workflow endpoints: submit, approve, reject, request-revision, rollback + generic `POST /api/gate-check`.

## Итог

Реальный статус проекта лучше старой `docs/SPEC-COVERAGE-MATRIX.md` в трёх местах:

- AI слой сильнее, чем там указано.
- Collection wizard уже работает через `/evidences/upload`.
- Platform admin UI есть не только списком tenants, но и с create/detail screens + support mode UI.

### Ошибки в первой версии аудита (исправлены)

1. **digest_frequency** — claim "не exposed в API schema" был неверен. Поле есть в `NotificationPreferencesOut` и `NotificationPreferencesUpdate`.
2. **Support mode UI** — claim "не найден frontend UI" был неверен. `frontend/lib/support-mode.ts` + dialog в tenant detail page + автоматический header inject в `api.ts` — всё работает.
3. **Dimensions** — claim "ограничены scope/gas_type/category" неполный. DB поддерживает 5 типов (comment: `scope|gas|category|facility|geography`), но API schema действительно возвращает только 3 boolean-флага.
4. **Batch actions** — не были упомянуты в подтверждённом списке Reviewer, хотя полностью реализованы.
5. **Form-config** — не было указано, что backend + admin UI полностью готовы, а wizard-renderer существует но не подключен.

### Реальные хвосты (приоритизированные)

**Blocked flows (мёртвый код / disconnect)**:
- `wizard-renderer.tsx` существует, но не импортирован — collection flow hardcoded;
- form-config backend + admin UI готовы, но runtime не использует;
- calculation rules backend готов, frontend UI отсутствует;
- snapshot history в boundary UI не подключен к backend.

**Missing UX**:
- onboarding wizard и guided org setup (register → сразу /dashboard);
- `not_applicable` status в review flow;
- structured outlier justification form;
- mapping history/diff frontend.

**Infra gaps**:
- tracing/OpenTelemetry не реализован;
- backup/restore operational layer отсутствует;
- CSP/HSTS/security headers не настроены на application level;
- 8 тестов в `test_standards.py`, `test_shared_elements.py`, `test_requirement_items.py` устарели после auth hardening.

**API/schema inconsistencies**:
- DimensionFlagsOut возвращает 3 булевых флага, DB поддерживает 5 string-типов;
- DataPoint model: только `numeric_value` + `text_value`, нет `date`/`enum`/`json`.
