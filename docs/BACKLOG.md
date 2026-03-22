# ESGvist — JIRA Backlog

**Версия:** 1.0
**Дата:** 2026-03-22
**Статус:** На согласовании

---

## Структура

```
8 Epics → 22 Features → ~80 Tasks
```

| Epic | Название | Phase | Features |
|------|----------|-------|----------|
| EPIC-1 | Standard Management | MVP | 3 |
| EPIC-2 | Shared Data Layer | MVP | 3 |
| EPIC-3 | Merge & Delta Engine | Phase 2 | 3 |
| EPIC-4 | Data Collection | MVP | 3 |
| EPIC-5 | Workflow & Review | MVP | 3 |
| EPIC-6 | Completeness Engine | MVP | 2 |
| EPIC-7 | Project Management | MVP | 2 |
| EPIC-8 | Reporting & Export | MVP/Phase 2 | 3 |

---

## 🧱 EPIC-1: Standard Management (Admin)

**Цель:** Загрузка и управление стандартами, требованиями и их декомпозицией

**Phase:** MVP

**Связь с ТЗ:** TZ-Admin 3.1–3.3, TZ-ESGvist-v1 раздел 3.1–3.2

---

### Feature 1.1 — Manage Standards

**User Story:**
> Как администратор, я хочу создавать и версионировать стандарты, чтобы система поддерживала актуальные требования.

**Acceptance Criteria:**
- [ ] Можно создать стандарт (code, name, version, jurisdiction, effective_from)
- [ ] Можно загрузить / создать структуру секций (standard_sections, иерархия)
- [ ] Можно деактивировать версию (is_active = false)
- [ ] Нельзя удалить стандарт, если есть привязанные данные
- [ ] При обновлении стандарта создаётся новая версия, старая помечается deprecated
- [ ] Структура отображается в виде дерева

**Tasks:**

| # | Task | Type | Priority | Story Points |
|---|------|------|----------|-------------|
| 1.1.1 | Создать миграцию: таблицы `standards`, `standard_sections` | Backend | Must | 3 |
| 1.1.2 | API: CRUD `/api/standards` (создание, чтение, обновление, деактивация) | Backend | Must | 5 |
| 1.1.3 | API: CRUD `/api/standards/:id/sections` (дерево секций) | Backend | Must | 3 |
| 1.1.4 | Валидация: запрет удаления при наличии привязанных disclosure_requirements | Backend | Must | 2 |
| 1.1.5 | UI: страница `/settings/standards` — список стандартов | Frontend | Must | 5 |
| 1.1.6 | UI: дерево секций (рекурсивный компонент) | Frontend | Must | 5 |
| 1.1.7 | UI: форма создания/редактирования стандарта | Frontend | Must | 3 |
| 1.1.8 | Seed: загрузка GRI 2021 (структура + секции) | Data | Must | 5 |
| 1.1.9 | Seed: загрузка IFRS S2 2023 (структура + секции) | Data | Should | 5 |
| 1.1.10 | Seed: загрузка SASB Oil & Gas 2023 | Data | Should | 5 |
| 1.1.11 | Тесты: CRUD стандартов, защита от удаления | QA | Must | 3 |

---

### Feature 1.2 — Disclosure Requirements

**User Story:**
> Как администратор, я хочу управлять disclosure requirements, чтобы моделировать требования стандартов.

**Acceptance Criteria:**
- [ ] Можно создать disclosure requirement (code, title, description)
- [ ] Можно задать mandatory_level (mandatory / conditional / optional)
- [ ] Можно задать requirement_type (quantitative / qualitative / mixed)
- [ ] Можно задать applicability_rule (JSON)
- [ ] Уникальность code внутри стандарта (standard_id + code)
- [ ] Можно связать с section_id
- [ ] Управление sort_order

**Tasks:**

| # | Task | Type | Priority | SP |
|---|------|------|----------|---|
| 1.2.1 | Миграция: таблица `disclosure_requirements` | Backend | Must | 2 |
| 1.2.2 | API: CRUD `/api/standards/:id/disclosures` | Backend | Must | 5 |
| 1.2.3 | Валидация: unique (standard_id, code), JSON schema для applicability_rule | Backend | Must | 3 |
| 1.2.4 | UI: список disclosures внутри стандарта (таблица с фильтрами) | Frontend | Must | 5 |
| 1.2.5 | UI: форма создания/редактирования disclosure | Frontend | Must | 3 |
| 1.2.6 | Seed: disclosure requirements для GRI 2021 (~35 штук) | Data | Must | 8 |
| 1.2.7 | Seed: disclosure requirements для IFRS S2 (~25 штук) | Data | Should | 5 |
| 1.2.8 | Тесты: CRUD, uniqueness, applicability_rule validation | QA | Must | 3 |

---

### Feature 1.3 — Requirement Items

**User Story:**
> Как администратор, я хочу декомпозировать требования на атомарные элементы, чтобы точно моделировать, что нужно для раскрытия.

**Acceptance Criteria:**
- [ ] Можно создать item с типом (metric / attribute / dimension / narrative / document)
- [ ] Можно задать value_type (number / text / boolean / date / enum / json)
- [ ] Можно задать unit_code, is_required, cardinality
- [ ] Поддерживается иерархия (parent_item_id)
- [ ] Поддерживаются validation_rule и granularity_rule (JSON)
- [ ] Можно задать зависимости между items (requires / excludes / conditional_on)

**Tasks:**

| # | Task | Type | Priority | SP |
|---|------|------|----------|---|
| 1.3.1 | Миграция: таблицы `requirement_items`, `requirement_item_dependencies` | Backend | Must | 3 |
| 1.3.2 | API: CRUD `/api/disclosures/:id/items` | Backend | Must | 5 |
| 1.3.3 | API: CRUD зависимостей `/api/items/:id/dependencies` | Backend | Should | 3 |
| 1.3.4 | Валидация: JSON schema для validation_rule, granularity_rule | Backend | Must | 3 |
| 1.3.5 | UI: список items внутри disclosure (дерево с иерархией) | Frontend | Must | 5 |
| 1.3.6 | UI: форма создания item (тип, value_type, unit, rules) | Frontend | Must | 5 |
| 1.3.7 | UI: визуализация зависимостей между items | Frontend | Could | 3 |
| 1.3.8 | Seed: requirement items для GRI 305 (Emissions) — полная декомпозиция | Data | Must | 5 |
| 1.3.9 | Seed: requirement items для GRI 302 (Energy), 303 (Water) | Data | Should | 5 |
| 1.3.10 | Тесты: CRUD, hierarchy, dependencies, validation rules | QA | Must | 3 |

---

## 🧩 EPIC-2: Shared Data Layer

**Цель:** Создание сквозного слоя для переиспользования данных между стандартами

**Phase:** MVP

**Связь с ТЗ:** TZ-Admin 3.4–3.5, TZ-ESGvist-v1 раздел 3.3

---

### Feature 2.1 — Shared Elements

**User Story:**
> Как администратор, я хочу создавать shared элементы, чтобы переиспользовать одинаковые данные между стандартами.

**Acceptance Criteria:**
- [ ] Уникальный code (GHG_SCOPE_1_TOTAL)
- [ ] Можно задать concept_domain (emissions / energy / water / ...)
- [ ] Можно задать default_value_type и default_unit_code
- [ ] Описание и документация

**Tasks:**

| # | Task | Type | Priority | SP |
|---|------|------|----------|---|
| 2.1.1 | Миграция: таблица `shared_elements` | Backend | Must | 2 |
| 2.1.2 | API: CRUD `/api/shared-elements` | Backend | Must | 3 |
| 2.1.3 | UI: каталог shared elements (таблица с фильтром по domain) | Frontend | Must | 5 |
| 2.1.4 | UI: форма создания/редактирования shared element | Frontend | Must | 3 |
| 2.1.5 | Seed: ~80 shared elements (emissions, energy, water, waste, workforce, governance) | Data | Must | 8 |
| 2.1.6 | Тесты: CRUD, uniqueness code | QA | Must | 2 |

---

### Feature 2.2 — Dimensions

**User Story:**
> Как администратор, я хочу задавать допустимые измерения для shared элементов.

**Acceptance Criteria:**
- [ ] Можно задать dimension_type (scope / gas / category / facility / geography)
- [ ] Можно отметить is_required
- [ ] Uniqueness (shared_element_id, dimension_type)

**Tasks:**

| # | Task | Type | Priority | SP |
|---|------|------|----------|---|
| 2.2.1 | Миграция: таблица `shared_element_dimensions` | Backend | Must | 1 |
| 2.2.2 | API: CRUD `/api/shared-elements/:id/dimensions` | Backend | Must | 2 |
| 2.2.3 | UI: management dimensions в карточке shared element | Frontend | Must | 3 |
| 2.2.4 | Seed: dimensions для emission elements (scope, gas) | Data | Must | 2 |
| 2.2.5 | Тесты | QA | Must | 1 |

---

### Feature 2.3 — Mapping (Requirement ↔ Shared Element)

**User Story:**
> Как администратор, я хочу связывать requirement items с shared elements, чтобы определить, какие данные закрывают какие требования.

**Acceptance Criteria:**
- [ ] mapping_type (full / partial / derived)
- [ ] Один requirement item → несколько shared elements
- [ ] Один shared element → несколько requirement items (из разных стандартов)
- [ ] Визуализация: какие стандарты используют один shared element

**Tasks:**

| # | Task | Type | Priority | SP |
|---|------|------|----------|---|
| 2.3.1 | Миграция: таблица `requirement_item_shared_elements` | Backend | Must | 2 |
| 2.3.2 | API: CRUD `/api/mappings` + lookup endpoints | Backend | Must | 5 |
| 2.3.3 | API: query «shared elements used by multiple standards» | Backend | Must | 3 |
| 2.3.4 | UI: матрица маппинга (shared element × standards) | Frontend | Must | 8 |
| 2.3.5 | UI: drag-and-drop или select для привязки item → shared element | Frontend | Should | 5 |
| 2.3.6 | Seed: mappings для GRI emissions ↔ shared elements | Data | Must | 5 |
| 2.3.7 | Seed: mappings для IFRS S2 ↔ shared elements (с partial) | Data | Should | 5 |
| 2.3.8 | Тесты: CRUD, multi-standard lookup | QA | Must | 3 |

---

## 🔀 EPIC-3: Merge & Delta Engine

**Цель:** Объединение стандартов через shared layer, управление дельтами

**Phase:** Phase 2

**Связь с ТЗ:** TZ-ESGvist-v1 раздел 4, TZ-Admin 3.6–3.7, TZ-ESGManager 3.4

---

### Feature 3.1 — Merge Engine (Backend)

**User Story:**
> Как система, я хочу объединять требования стандартов через shared layer, чтобы определять пересечения и уникальные требования.

**Acceptance Criteria:**
- [ ] Grouping requirement_items по shared_element
- [ ] Определение common элементов (required_by 2+ стандартов)
- [ ] Определение unique элементов (required_by 1 стандарт)
- [ ] Определение orphan requirements (нет mapping на shared element)
- [ ] Формирование MergedView response

**Tasks:**

| # | Task | Type | Priority | SP |
|---|------|------|----------|---|
| 3.1.1 | Service: MergeEngine — алгоритм merge (5 шагов) | Backend | Must | 8 |
| 3.1.2 | API: `GET /api/projects/:id/merge` — merged view | Backend | Must | 5 |
| 3.1.3 | API: `GET /api/projects/:id/merge/coverage` — coverage per standard | Backend | Must | 3 |
| 3.1.4 | Обработка добавления нового стандарта: пересчёт merge + impact preview | Backend | Must | 5 |
| 3.1.5 | Тесты: merge GRI + IFRS S2 (pересечения, дельты, orphans) | QA | Must | 5 |

---

### Feature 3.2 — Delta Requirements

**User Story:**
> Как администратор, я хочу задавать дополнительные требования при комбинации стандартов.

**Acceptance Criteria:**
- [ ] base_standard_id + added_standard_id
- [ ] delta_type (additional_item / stricter_validation / extra_dimension / extra_narrative / extra_document)
- [ ] delta_payload (JSON)
- [ ] Дельта применяется только в контексте конкретной комбинации стандартов
- [ ] Overrides: переопределение required_flag, unit, granularity

**Tasks:**

| # | Task | Type | Priority | SP |
|---|------|------|----------|---|
| 3.2.1 | Миграция: таблицы `requirement_deltas`, `requirement_item_overrides` | Backend | Must | 3 |
| 3.2.2 | API: CRUD `/api/deltas` | Backend | Must | 3 |
| 3.2.3 | API: CRUD `/api/overrides` | Backend | Must | 3 |
| 3.2.4 | Интеграция: MergeEngine учитывает дельты и overrides | Backend | Must | 5 |
| 3.2.5 | UI: управление дельтами (создание, привязка к item + стандартам) | Frontend | Must | 5 |
| 3.2.6 | Seed: дельты GRI ↔ IFRS S2 (financial linkage, gas breakdown) | Data | Must | 3 |
| 3.2.7 | Тесты: дельты применяются корректно в merge | QA | Must | 3 |

---

### Feature 3.3 — Merge View (UI)

**User Story:**
> Как ESG-менеджер, я хочу видеть пересечения стандартов в матричном виде.

**Acceptance Criteria:**
- [ ] Матрица: element × standard (✔ / ❌ / +Δ / —)
- [ ] Summary bar: coverage per standard
- [ ] Фильтры: по concept_domain, по статусу, по стандарту
- [ ] Drill-down: клик → DataPoint или форма ввода
- [ ] Клик по +Δ → popup с описанием дельты
- [ ] Доступ: esg_manager + reviewer (read-only) + auditor (read-only) + admin

**Tasks:**

| # | Task | Type | Priority | SP |
|---|------|------|----------|---|
| 3.3.1 | UI: страница `/merge` — матрица element × standard | Frontend | Must | 8 |
| 3.3.2 | UI: summary bar (coverage %, common/unique/delta counts) | Frontend | Must | 3 |
| 3.3.3 | UI: фильтры (domain, status, standard) | Frontend | Must | 3 |
| 3.3.4 | UI: drill-down popup (data point details, delta description) | Frontend | Must | 5 |
| 3.3.5 | UI: access control (скрыть для collector) | Frontend | Must | 2 |
| 3.3.6 | Тесты: merge view корректно отображает данные | QA | Must | 3 |

---

## 📊 EPIC-4: Data Collection

**Цель:** Ввод ESG-данных пользователями

**Phase:** MVP

**Связь с ТЗ:** TZ-User 3.3–3.4, TZ-ESGvist-v1 раздел 3.6

---

### Feature 4.1 — Data Entry (Backend)

**User Story:**
> Как пользователь, я хочу вводить данные по назначенным метрикам.

**Acceptance Criteria:**
- [ ] Поддержка типов значений (number, text, boolean, date, enum, json)
- [ ] Dimensions обязательны, если заданы в granularity_rule
- [ ] Unit selection из справочника
- [ ] Methodology и boundary selection
- [ ] Сохранение draft
- [ ] Валидация: required fields, min/max, deviation threshold

**Tasks:**

| # | Task | Type | Priority | SP |
|---|------|------|----------|---|
| 4.1.1 | Миграция: таблицы `data_points`, `data_point_dimensions`, `methodologies`, `boundaries`, `source_records` | Backend | Must | 5 |
| 4.1.2 | API: CRUD `/api/data-points` (создание, чтение, обновление) | Backend | Must | 5 |
| 4.1.3 | API: `/api/data-points/:id/dimensions` — управление разрезами | Backend | Must | 3 |
| 4.1.4 | Валидация: field-level (type, min/max), record-level (required fields, dimensions) | Backend | Must | 5 |
| 4.1.5 | Outlier detection: deviation_threshold check vs previous period | Backend | Should | 3 |
| 4.1.6 | Seed: справочники methodologies, boundaries | Data | Must | 2 |
| 4.1.7 | Тесты: CRUD, validation, outlier detection | QA | Must | 3 |

---

### Feature 4.2 — Wizard Forms (UI)

**User Story:**
> Как пользователь, я хочу вводить данные через wizard с шагами.

**Acceptance Criteria:**
- [ ] Формы генерируются из requirement_items
- [ ] Шаги wizard (QN-1: выбор метрики → QN-2: ввод данных → QN-3: проверка → QN-4: отправка)
- [ ] Блокирующая валидация при переходе между шагами
- [ ] Кнопки: «Сохранить черновик» + «Отправить на ревью»
- [ ] Отображение reuse indicator и delta badge

**Tasks:**

| # | Task | Type | Priority | SP |
|---|------|------|----------|---|
| 4.2.1 | UI: компонент Wizard (stepper + навигация + валидация) | Frontend | Must | 8 |
| 4.2.2 | UI: шаг QN-1 — выбор метрики (список назначенных) | Frontend | Must | 3 |
| 4.2.3 | UI: шаг QN-2 — форма ввода (dynamic fields из requirement_items) | Frontend | Must | 8 |
| 4.2.4 | UI: шаг QN-3 — preview + валидация | Frontend | Must | 5 |
| 4.2.5 | UI: шаг QN-4 — отправка (draft / submit) | Frontend | Must | 3 |
| 4.2.6 | UI: qualitative wizard (QL-1 → QL-3) | Frontend | Should | 5 |
| 4.2.7 | Тесты: wizard flow, validation blocking, draft/submit | QA | Must | 3 |

---

### Feature 4.3 — Reuse Detection

**User Story:**
> Как пользователь, я хочу переиспользовать существующие данные вместо повторного ввода.

**Acceptance Criteria:**
- [ ] Поиск совпадений по Identity Rule (7 параметров)
- [ ] Предложение reuse с объяснением совпадения
- [ ] Reuse Transparency: показ всех стандартов, использующих значение
- [ ] Возможность создать новое значение, если параметры отличаются
- [ ] Locking warning при редактировании multi-bound DataPoint

**Tasks:**

| # | Task | Type | Priority | SP |
|---|------|------|----------|---|
| 4.3.1 | Service: ReuseDetector — поиск по Identity Rule | Backend | Must | 5 |
| 4.3.2 | API: `GET /api/data-points/find-reuse?shared_element_id=...&period_id=...` | Backend | Must | 3 |
| 4.3.3 | API: `POST /api/data-points/:id/bind` — создать binding (requirement_item_data_points) | Backend | Must | 3 |
| 4.3.4 | UI: reuse suggestion dialog (значение, параметры, список стандартов) | Frontend | Must | 5 |
| 4.3.5 | UI: reuse badge (inline indicator: «используется в 3 стандартах») | Frontend | Must | 3 |
| 4.3.6 | UI: locking warning при edit multi-bound DataPoint | Frontend | Must | 3 |
| 4.3.7 | Тесты: reuse detection, binding creation, locking | QA | Must | 3 |

---

## 🔄 EPIC-5: Workflow & Review

**Цель:** Workflow данных и процесс ревью

**Phase:** MVP

**Связь с ТЗ:** TZ-User 3.10–3.11, TZ-Reviewer 3.1–3.8, TZ-ESGvist-v1 раздел 6

---

### Feature 5.1 — DataPoint Workflow

**User Story:**
> Как пользователь, я хочу управлять статусами данных через формальный workflow.

**Acceptance Criteria:**
- [ ] Переходы: draft → submitted → in_review → approved / rejected / needs_revision
- [ ] Ограничения редактирования по статусу (см. TZ-User 3.3)
- [ ] Откат approved → draft только ESG-менеджером (с audit log)
- [ ] Уведомления при переходах (submitted → reviewer, rejected → collector)
- [ ] Версионирование значений (data_point_versions)

**Tasks:**

| # | Task | Type | Priority | SP |
|---|------|------|----------|---|
| 5.1.1 | Service: WorkflowEngine — state machine (валидация переходов) | Backend | Must | 5 |
| 5.1.2 | API: `POST /api/data-points/:id/submit`, `/approve`, `/reject`, `/request-revision` | Backend | Must | 5 |
| 5.1.3 | Миграция: таблица `data_point_versions` | Backend | Must | 2 |
| 5.1.4 | Автоматическое создание version при изменении value | Backend | Must | 3 |
| 5.1.5 | Ограничение редактирования: read-only для submitted/in_review/approved | Backend | Must | 3 |
| 5.1.6 | UI: status badge + lock indicator на формах ввода | Frontend | Must | 3 |
| 5.1.7 | UI: кнопки workflow (Submit, Save Draft) с условной видимостью | Frontend | Must | 3 |
| 5.1.8 | Тесты: state machine transitions, locking, versioning | QA | Must | 3 |

---

### Feature 5.2 — Review UI

**User Story:**
> Как ревьюер, я хочу проверять данные в split panel интерфейсе.

**Acceptance Criteria:**
- [ ] Split panel: список слева + детали справа
- [ ] Approve / Reject / Request revision
- [ ] Обязательный комментарий при reject / needs_revision
- [ ] Batch approve (multiple items)
- [ ] Outlier и consistency alerts
- [ ] Review consistency: reuse count, impact of approval

**Tasks:**

| # | Task | Type | Priority | SP |
|---|------|------|----------|---|
| 5.2.1 | UI: страница `/validation` — split panel layout | Frontend | Must | 8 |
| 5.2.2 | UI: левая панель — список с фильтрами (status, standard, overdue) | Frontend | Must | 5 |
| 5.2.3 | UI: правая панель — детали (значение, prev year, evidence, comments) | Frontend | Must | 5 |
| 5.2.4 | UI: action buttons (Approve / Reject / Request Revision) | Frontend | Must | 3 |
| 5.2.5 | UI: batch approve с summary preview | Frontend | Should | 5 |
| 5.2.6 | UI: outlier badge + consistency warning | Frontend | Should | 3 |
| 5.2.7 | UI: reuse indicator (этот DataPoint используется в N стандартах) | Frontend | Must | 2 |
| 5.2.8 | Тесты: review flow, batch approve, comment requirement | QA | Must | 3 |

---

### Feature 5.3 — Comments

**User Story:**
> Как пользователь, я хочу обсуждать данные с ревьюером через threaded comments.

**Acceptance Criteria:**
- [ ] Threaded comments (parent_comment_id)
- [ ] Comment types (question / issue / suggestion / resolution / general)
- [ ] Resolve threads (is_resolved)
- [ ] Привязка к data_point и/или requirement_item

**Tasks:**

| # | Task | Type | Priority | SP |
|---|------|------|----------|---|
| 5.3.1 | Миграция: таблица `comments` | Backend | Must | 2 |
| 5.3.2 | API: CRUD `/api/comments` + threaded queries | Backend | Must | 5 |
| 5.3.3 | API: resolve thread (`PATCH /api/comments/:id/resolve`) | Backend | Must | 1 |
| 5.3.4 | UI: comment thread component (reviewer ↔ collector dialog) | Frontend | Must | 5 |
| 5.3.5 | UI: comment type selector + resolve button | Frontend | Should | 3 |
| 5.3.6 | Тесты: threading, resolve, comment types | QA | Must | 2 |

---

## 🧠 EPIC-6: Completeness Engine

**Цель:** Автоматический расчёт статусов покрытия требований

**Phase:** MVP

**Связь с ТЗ:** TZ-ESGvist-v1 раздел 5 (Completeness Engine)

---

### Feature 6.1 — Requirement Status Calculation

**User Story:**
> Как система, я хочу автоматически рассчитывать статус каждого requirement item.

**Acceptance Criteria:**
- [ ] Проверка: required fields заполнены
- [ ] Проверка: required dimensions присутствуют
- [ ] Проверка: evidence прикреплены (если item_type = document)
- [ ] Проверка: data_point.status = approved
- [ ] Результат: missing / partial / complete / not_applicable
- [ ] Триггеры: data_point change, binding change, standard added, rules changed
- [ ] Performance: < 100ms per item

**Tasks:**

| # | Task | Type | Priority | SP |
|---|------|------|----------|---|
| 6.1.1 | Миграция: таблицы `requirement_item_statuses`, `requirement_item_data_points` | Backend | Must | 3 |
| 6.1.2 | Service: CompletenessEngine — расчёт статуса requirement_item | Backend | Must | 8 |
| 6.1.3 | Триггеры: пересчёт при изменении data_point (event-driven) | Backend | Must | 5 |
| 6.1.4 | Триггеры: пересчёт при изменении binding | Backend | Must | 3 |
| 6.1.5 | API: `GET /api/projects/:id/completeness` | Backend | Must | 3 |
| 6.1.6 | Performance: benchmark < 100ms per item, < 5s per project | QA | Must | 3 |
| 6.1.7 | Тесты: missing/partial/complete scenarios, trigger cascading | QA | Must | 5 |

---

### Feature 6.2 — Disclosure Aggregation

**User Story:**
> Как система, я хочу агрегировать статус disclosure из статусов его requirement items.

**Acceptance Criteria:**
- [ ] completion_percent = count(complete required items) / count(total required items)
- [ ] missing_summary (JSON: какие items отсутствуют)
- [ ] disclosure_status: missing / partial / complete / not_applicable
- [ ] Overall score per standard

**Tasks:**

| # | Task | Type | Priority | SP |
|---|------|------|----------|---|
| 6.2.1 | Миграция: таблица `disclosure_requirement_statuses` | Backend | Must | 2 |
| 6.2.2 | Service: агрегация disclosure status из item statuses | Backend | Must | 5 |
| 6.2.3 | API: `GET /api/projects/:id/completeness/:standard_id` (per standard) | Backend | Must | 3 |
| 6.2.4 | API: overall score per standard в response merge view | Backend | Must | 2 |
| 6.2.5 | Тесты: aggregation logic, edge cases (all missing, all complete, mixed) | QA | Must | 3 |

---

## 🏢 EPIC-7: Project Management

**Цель:** Управление проектами отчётности

**Phase:** MVP

**Связь с ТЗ:** TZ-ESGManager 3.1–3.2, TZ-ESGvist-v1 раздел 3.5

---

### Feature 7.1 — Reporting Projects

**User Story:**
> Как ESG-менеджер, я хочу создавать и управлять проектами отчётности.

**Acceptance Criteria:**
- [ ] Создание проекта (organization, period, name)
- [ ] Выбор стандартов (с определением base_standard)
- [ ] Workflow проекта: draft → in_progress → review → published
- [ ] Дедлайн
- [ ] При добавлении стандарта — impact preview

**Tasks:**

| # | Task | Type | Priority | SP |
|---|------|------|----------|---|
| 7.1.1 | Миграция: таблицы `organizations`, `reporting_periods`, `reporting_projects`, `reporting_project_standards` | Backend | Must | 5 |
| 7.1.2 | API: CRUD `/api/projects` | Backend | Must | 5 |
| 7.1.3 | API: `POST /api/projects/:id/standards` (add standard + impact preview) | Backend | Must | 5 |
| 7.1.4 | API: project workflow transitions | Backend | Must | 3 |
| 7.1.5 | UI: Dashboard overview (progress, issues, category cards) | Frontend | Must | 8 |
| 7.1.6 | UI: project settings (standards selection, deadline) | Frontend | Must | 5 |
| 7.1.7 | UI: impact preview при добавлении стандарта | Frontend | Should | 5 |
| 7.1.8 | Тесты: project CRUD, standard addition, workflow | QA | Must | 3 |

---

### Feature 7.2 — Assignments

**User Story:**
> Как ESG-менеджер, я хочу назначать метрики на сборщиков и ревьюеров.

**Acceptance Criteria:**
- [ ] Назначение collector + reviewer на shared_element
- [ ] Constraint: collector ≠ reviewer
- [ ] Backup owner (backup_collector_id)
- [ ] Дедлайн + escalation_after_days
- [ ] Массовое назначение (bulk assign)
- [ ] Возможность оставить без назначения (pending)

**Tasks:**

| # | Task | Type | Priority | SP |
|---|------|------|----------|---|
| 7.2.1 | Миграция: таблица `metric_assignments` (с backup_collector_id, escalation_after_days) | Backend | Must | 3 |
| 7.2.2 | API: CRUD `/api/projects/:id/assignments` | Backend | Must | 5 |
| 7.2.3 | API: `POST /api/projects/:id/assignments/bulk` | Backend | Must | 3 |
| 7.2.4 | Валидация: collector ≠ reviewer ≠ backup_collector | Backend | Must | 2 |
| 7.2.5 | UI: матрица назначений (shared_element × collector × reviewer × deadline × status) | Frontend | Must | 8 |
| 7.2.6 | UI: bulk assign (select multiple → assign collector/reviewer) | Frontend | Should | 5 |
| 7.2.7 | Тесты: assignments CRUD, constraints, bulk | QA | Must | 3 |

---

## 📤 EPIC-8: Reporting & Export

**Цель:** Проверка готовности и экспорт отчётов

**Phase:** MVP (readiness) + Phase 2 (advanced export)

**Связь с ТЗ:** TZ-ESGManager 3.7, TZ-ESGvist-v1 раздел 10

---

### Feature 8.1 — Readiness Check

**User Story:**
> Как ESG-менеджер, я хочу проверить готовность отчёта перед экспортом.

**Acceptance Criteria:**
- [ ] % completion (overall + per standard)
- [ ] Blocking issues (missing mandatory disclosures)
- [ ] Warnings (outliers, partial data, pending review)
- [ ] Список конкретных пробелов с drill-down

**Tasks:**

| # | Task | Type | Priority | SP |
|---|------|------|----------|---|
| 8.1.1 | API: `GET /api/projects/:id/export/readiness` | Backend | Must | 5 |
| 8.1.2 | Service: readiness calculator (blocking issues + warnings + score) | Backend | Must | 5 |
| 8.1.3 | UI: readiness dashboard (progress, issues list, warnings) | Frontend | Must | 5 |
| 8.1.4 | UI: drill-down от issue → data point | Frontend | Must | 3 |
| 8.1.5 | Тесты: readiness calculation, edge cases | QA | Must | 3 |

---

### Feature 8.2 — Export

**User Story:**
> Как ESG-менеджер, я хочу выгружать отчёт в разных форматах.

**Acceptance Criteria:**
- [ ] GRI Content Index (PDF + Excel)
- [ ] Full data dump (Excel)
- [ ] Publish flow: project → published (lock all data)

**Tasks:**

| # | Task | Type | Priority | SP |
|---|------|------|----------|---|
| 8.2.1 | Service: GRI Content Index generator (structured data → table) | Backend | Must | 8 |
| 8.2.2 | API: `POST /api/projects/:id/export/gri-index` (PDF) | Backend | Must | 5 |
| 8.2.3 | API: `POST /api/projects/:id/export/report` (Excel data dump) | Backend | Must | 5 |
| 8.2.4 | Service: publish flow (lock data, create snapshot, audit log) | Backend | Must | 5 |
| 8.2.5 | UI: export page (format selection, preview, download) | Frontend | Must | 5 |
| 8.2.6 | UI: publish confirmation dialog | Frontend | Must | 2 |
| 8.2.7 | Тесты: export correctness, publish locking | QA | Must | 3 |

---

### Feature 8.3 — Evidence Management

**User Story:**
> Как пользователь, я хочу загружать и привязывать файлы-доказательства к данным.

**Acceptance Criteria:**
- [ ] Upload файлов (PDF, Excel, изображения)
- [ ] Привязка к data_point и/или requirement_item
- [ ] Поиск и фильтрация файлов
- [ ] Индикация обязательности evidence

**Tasks:**

| # | Task | Type | Priority | SP |
|---|------|------|----------|---|
| 8.3.1 | Миграция: таблица `attachments` | Backend | Must | 2 |
| 8.3.2 | API: upload + bind + list `/api/attachments` | Backend | Must | 5 |
| 8.3.3 | File storage integration (S3 / MinIO) | Backend | Must | 5 |
| 8.3.4 | UI: evidence repository (список, фильтры, upload) | Frontend | Must | 5 |
| 8.3.5 | UI: inline attach в форме ввода данных | Frontend | Must | 3 |
| 8.3.6 | UI: badge «evidence required» на items с type = document | Frontend | Should | 2 |
| 8.3.7 | Тесты: upload, bind, filter | QA | Must | 3 |

---

## 📊 Summary

### Story Points по Epic

| Epic | Features | Tasks | Total SP |
|------|----------|-------|----------|
| EPIC-1: Standard Management | 3 | 29 | ~115 |
| EPIC-2: Shared Data Layer | 3 | 19 | ~68 |
| EPIC-3: Merge & Delta Engine | 3 | 18 | ~78 |
| EPIC-4: Data Collection | 3 | 21 | ~85 |
| EPIC-5: Workflow & Review | 3 | 22 | ~82 |
| EPIC-6: Completeness Engine | 2 | 12 | ~48 |
| EPIC-7: Project Management | 2 | 15 | ~65 |
| EPIC-8: Reporting & Export | 3 | 20 | ~72 |
| **Total** | **22** | **~156** | **~613** |

### MVP Scope (Phase 1)

| Epic | Включено |
|------|---------|
| EPIC-1: Standard Management | ✅ Полностью |
| EPIC-2: Shared Data Layer | ✅ Полностью |
| EPIC-3: Merge & Delta | ❌ Phase 2 |
| EPIC-4: Data Collection | ✅ Полностью |
| EPIC-5: Workflow & Review | ✅ Полностью |
| EPIC-6: Completeness Engine | ✅ Полностью |
| EPIC-7: Project Management | ✅ Полностью |
| EPIC-8: Reporting & Export | ✅ Readiness + Basic Export |

**MVP SP:** ~435 SP
**При velocity 40 SP/sprint (2 нед):** ~11 спринтов ≈ **22 недели**

### Phase 2 Scope

| Epic | Включено |
|------|---------|
| EPIC-3: Merge & Delta | ✅ Полностью |
| EPIC-8: Advanced Export | ✅ XBRL, advanced PDF |

**Phase 2 SP:** ~178 SP
**При velocity 40 SP/sprint:** ~5 спринтов ≈ **10 недель**
