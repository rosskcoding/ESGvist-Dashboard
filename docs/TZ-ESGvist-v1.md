# ТЗ на разработку: ESGvist — система управления ESG-данными

**Версия:** 1.1
**Дата:** 2026-03-22
**Автор:** RK + Claude
**Статус:** Согласован

---

## 1. Общее описание

### 1.1. Назначение системы

ESGvist — веб-приложение для сбора, валидации и формирования ESG-отчётности по международным стандартам (GRI, IFRS S2, SASB и др.).

Ключевая идея: **стандарты первичны, данные переиспользуются через сквозной слой (SharedDataElement), различия между стандартами учитываются как дельты.**

### 1.2. Целевые пользователи

| Роль | Описание | Кол-во на компанию |
|------|----------|-------------------|
| **Администратор** | Настройка системы, стандартов, пользователей, периодов | 1–2 |
| **ESG-менеджер** | Управление процессом сбора, ревью, публикация отчётов | 1–3 |
| **Сборщик данных** | Ввод значений метрик, загрузка доказательств | 5–20 |
| **Ревьюер** | Проверка и одобрение данных | 2–5 |
| **Аудитор** (read-only) | Просмотр данных, доказательств, журнала изменений | 1–3 |

### 1.3. Технические ограничения (предварительно)

- Веб-приложение (SPA + API)
- Single-tenant deployment (одна инсталляция = одна организация)
- Локализация: RU / EN (минимум)
- Поддержка браузеров: Chrome, Firefox, Safari, Edge (последние 2 версии)

---

## 2. Архитектура данных

### 2.1. Общая модель

Схема делится на 8 блоков:

```
1. Каталог стандартов          (standards, standard_sections)
2. Каталог требований          (disclosure_requirements, requirement_items, dependencies)
3. Сквозной слой               (shared_elements, dimensions, mappings)
4. Дельты и переопределения    (requirement_deltas, requirement_item_overrides)
5. Проект отчётности           (organizations, reporting_periods, reporting_projects)
6. Фактические данные          (data_points, data_point_dimensions, evidences)
7. Привязка и покрытие         (requirement_item_data_points, statuses)
8. Пользователи и workflow     (users, roles, assignments, audit_log)
```

Основная цепочка:

```
standards → standard_sections → disclosure_requirements → requirement_items
                                                                ↕
                                              requirement_item_shared_elements
                                                                ↕
                                                          shared_elements
                                                                ↕
                                                           data_points
                                                                ↕
                                              requirement_item_data_points
                                                                ↕
                                              requirement_item_statuses
```

---

## 3. PostgreSQL-схема

### 3.1. Блок 1: Каталог стандартов

#### standards

Справочник стандартов.

```sql
create table standards (
    id                  bigserial primary key,
    code                text not null unique,       -- GRI, IFRS_S2, SASB, ESRS_E1
    name                text not null,
    version             text,
    jurisdiction        text,
    effective_from      date,
    effective_to        date,
    is_active           boolean not null default true,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now()
);
```

**Бизнес-правила:**
- Стандарт нельзя удалить, если есть привязанные данные (только `is_active = false`)
- Версионирование: при обновлении стандарта создаётся новая запись с новой version, старая помечается `is_active = false`
- Система поставляется с предзагруженными стандартами (GRI 2021, IFRS S2 2023, SASB)

#### standard_sections

Иерархическая структура стандарта: разделы, подразделы, блоки.

```sql
create table standard_sections (
    id                  bigserial primary key,
    standard_id         bigint not null references standards(id) on delete cascade,
    parent_section_id   bigint references standard_sections(id) on delete cascade,
    code                text,                       -- 305, 305-1, App B
    title               text not null,
    sort_order          integer not null default 0,
    created_at          timestamptz not null default now()
);
```

**Бизнес-правила:**
- Рекурсивная структура через `parent_section_id`
- Используется для отображения дерева стандарта в UI
- `code` опционален (не у всех секций есть формальный код)

---

### 3.2. Блок 2: Каталог требований

#### disclosure_requirements

Конкретное требование раскрытия внутри стандарта.

```sql
create table disclosure_requirements (
    id                  bigserial primary key,
    standard_id         bigint not null references standards(id) on delete cascade,
    section_id          bigint references standard_sections(id) on delete set null,
    code                text not null,              -- GRI 305-1, IFRS S2.29
    title               text not null,
    description         text,
    requirement_type    text not null check (requirement_type in ('quantitative', 'qualitative', 'mixed')),
    mandatory_level     text not null check (mandatory_level in ('mandatory', 'conditional', 'optional')),
    applicability_rule  jsonb,                      -- условие применимости
    sort_order          integer not null default 0,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now(),
    unique (standard_id, code)
);
```

**Бизнес-правила:**
- `mandatory` — обязательно для соответствия стандарту
- `conditional` — обязательно при выполнении условия (см. `applicability_rule`)
- `optional` — рекомендованное раскрытие, можно пропустить с обоснованием
- `applicability_rule` — JSON с условием, например: `{"if_sector": "oil_gas", "if_material": true}`

#### requirement_items

Атомарные части disclosure. Одно disclosure распадается на N элементов.

```sql
create table requirement_items (
    id                          bigserial primary key,
    disclosure_requirement_id   bigint not null references disclosure_requirements(id) on delete cascade,
    parent_item_id              bigint references requirement_items(id) on delete cascade,
    item_code                   text,               -- 305-1.a, 305-1.b
    name                        text not null,
    description                 text,
    item_type                   text not null check (item_type in ('metric', 'attribute', 'dimension', 'narrative', 'document')),
    value_type                  text not null check (value_type in ('number', 'text', 'boolean', 'date', 'enum', 'json')),
    unit_code                   text,               -- tCO2e, kWh, m3
    is_required                 boolean not null default true,
    cardinality_min             integer not null default 0,
    cardinality_max             integer,            -- null = unlimited
    granularity_rule            jsonb,              -- {"by_scope": true, "by_category": false}
    validation_rule             jsonb,              -- {"min": 0, "deviation_threshold": 0.4}
    sort_order                  integer not null default 0,
    created_at                  timestamptz not null default now()
);
```

**item_type — типы:**

| Тип | Описание | Пример |
|-----|----------|--------|
| `metric` | Числовой показатель | Scope 1 total (t CO2e) |
| `attribute` | Атрибут / характеристика | Boundary approach |
| `dimension` | Разрез / breakdown | By gas type |
| `narrative` | Текстовое описание | Methodology description |
| `document` | Требуемый документ | Audit certificate |

#### requirement_item_dependencies

Зависимости между атомарными требованиями.

```sql
create table requirement_item_dependencies (
    id                      bigserial primary key,
    requirement_item_id     bigint not null references requirement_items(id) on delete cascade,
    depends_on_item_id      bigint not null references requirement_items(id) on delete cascade,
    dependency_type         text not null check (dependency_type in ('requires', 'excludes', 'conditional_on')),
    condition_expression    jsonb,
    created_at              timestamptz not null default now(),
    unique (requirement_item_id, depends_on_item_id, dependency_type)
);
```

**Примеры:**
- `requires`: если заполнен Scope 3 total → требуется category breakdown
- `excludes`: location-based и market-based взаимоисключающие для одного disclosure
- `conditional_on`: financial linkage обязателен, если выбран IFRS S2

---

### 3.3. Блок 3: Сквозной слой

#### shared_elements

Сквозные элементы для переиспользования одинаковых сущностей между стандартами.

```sql
create table shared_elements (
    id                  bigserial primary key,
    code                text not null unique,       -- GHG_SCOPE_1_TOTAL
    name                text not null,
    concept_domain      text not null,              -- emissions, energy, water, waste, workforce
    description         text,
    default_value_type  text not null check (default_value_type in ('number', 'text', 'boolean', 'date', 'enum', 'json')),
    default_unit_code   text,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now()
);
```

**Примеры shared_elements:**

| code | name | concept_domain | default_unit |
|------|------|---------------|--------------|
| `GHG_SCOPE_1_TOTAL` | GHG Scope 1 total | emissions | tCO2e |
| `GHG_SCOPE_2_LOCATION` | GHG Scope 2 (location-based) | emissions | tCO2e |
| `GHG_SCOPE_3_TOTAL` | GHG Scope 3 total | emissions | tCO2e |
| `ENERGY_CONSUMPTION` | Energy consumption | energy | MWh |
| `WATER_WITHDRAWAL` | Water withdrawal | water | m3 |
| `BOARD_DIVERSITY_PCT` | Board diversity % | governance | % |

**Бизнес-правила:**
- SharedDataElement — **абстрактный понятийный элемент**, не привязанный к стандарту
- Используется исключительно для reuse, не заменяет стандарт
- Система поставляется с ~80 предзагруженными элементами
- Администратор может создавать кастомные элементы

#### shared_element_dimensions

Допустимые измерения для shared element.

```sql
create table shared_element_dimensions (
    id                  bigserial primary key,
    shared_element_id   bigint not null references shared_elements(id) on delete cascade,
    dimension_type      text not null,              -- scope, gas, category, facility, geography
    is_required         boolean not null default false,
    created_at          timestamptz not null default now(),
    unique (shared_element_id, dimension_type)
);
```

#### requirement_item_shared_elements

Маппинг requirement item ↔ shared element. **Главный мост архитектуры.**

```sql
create table requirement_item_shared_elements (
    id                      bigserial primary key,
    requirement_item_id     bigint not null references requirement_items(id) on delete cascade,
    shared_element_id       bigint not null references shared_elements(id) on delete cascade,
    mapping_type            text not null check (mapping_type in ('full', 'partial', 'derived')),
    notes                   text,
    created_at              timestamptz not null default now(),
    unique (requirement_item_id, shared_element_id)
);
```

**mapping_type:**
- `full` — RequirementItem полностью покрывается SharedElement
- `partial` — покрывается частично (есть дополнительные требования → см. дельты)
- `derived` — SharedElement получается расчётом из других элементов

---

### 3.4. Блок 4: Дельты и переопределения

#### requirement_item_overrides

Переопределения для конкретного item — обязательность, unit, гранулярность.

```sql
create table requirement_item_overrides (
    id                      bigserial primary key,
    requirement_item_id     bigint not null references requirement_items(id) on delete cascade,
    override_type           text not null check (override_type in (
                                'required_flag',
                                'unit',
                                'granularity',
                                'validation',
                                'applicability',
                                'narrative_requirement'
                            )),
    override_payload        jsonb not null,
    created_at              timestamptz not null default now()
);
```

**Примеры override_payload:**

```json
// required_flag: IFRS делает необязательный в GRI элемент обязательным
{"is_required": true, "reason": "IFRS S2 mandates financial impact assessment"}

// granularity: IFRS требует breakdown, GRI нет
{"by_gas": true, "by_scope3_category": true}

// validation: более строгий порог отклонения
{"deviation_threshold": 0.2}
```

#### requirement_deltas

Явные дельты при совмещении стандартов.

```sql
create table requirement_deltas (
    id                      bigserial primary key,
    base_standard_id        bigint not null references standards(id) on delete cascade,
    added_standard_id       bigint not null references standards(id) on delete cascade,
    requirement_item_id     bigint not null references requirement_items(id) on delete cascade,
    delta_type              text not null check (delta_type in (
                                'additional_item',
                                'stricter_validation',
                                'extra_dimension',
                                'extra_narrative',
                                'extra_document'
                            )),
    delta_payload           jsonb not null,
    created_at              timestamptz not null default now()
);
```

**Бизнес-правила:**
- Дельта фиксирует: "при базовом GRI, если добавить IFRS, требуется дополнительно X"
- `base_standard_id` + `added_standard_id` — контекст, в котором дельта релевантна
- При merge дельты **не теряются** — показываются как доп. требования
- Таблица опциональна: можно обойтись overrides, но deltas дают явный сценарий "база + надстройка"

---

### 3.5. Блок 5: Проект отчётности

#### organizations

```sql
create table organizations (
    id                  bigserial primary key,
    name                text not null,
    legal_entity_code   text,
    settings            jsonb,                      -- timezone, locale, fiscal_year_start
    created_at          timestamptz not null default now()
);
```

#### reporting_periods

```sql
create table reporting_periods (
    id                  bigserial primary key,
    organization_id     bigint not null references organizations(id) on delete cascade,
    code                text not null,              -- FY2025, Q2-2025
    period_start        date not null,
    period_end          date not null,
    deadline            date,                       -- дедлайн сдачи
    status              text not null default 'open' check (status in ('open', 'closed', 'archived')),
    created_at          timestamptz not null default now(),
    unique (organization_id, code)
);
```

#### reporting_projects

Конкретный проект отчётности: организация + период + набор стандартов.

```sql
create table reporting_projects (
    id                  bigserial primary key,
    organization_id     bigint not null references organizations(id) on delete cascade,
    reporting_period_id bigint not null references reporting_periods(id) on delete cascade,
    name                text not null,
    status              text not null default 'draft' check (status in ('draft', 'in_progress', 'review', 'published')),
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now()
);
```

#### reporting_project_standards

Какие стандарты включены в проект отчётности.

```sql
create table reporting_project_standards (
    id                  bigserial primary key,
    reporting_project_id bigint not null references reporting_projects(id) on delete cascade,
    standard_id         bigint not null references standards(id) on delete cascade,
    is_base_standard    boolean not null default false,
    sort_order          integer not null default 0,
    created_at          timestamptz not null default now(),
    unique (reporting_project_id, standard_id)
);
```

**Бизнес-правила:**
- `is_base_standard = true` — базовый стандарт (например GRI), на который накладываются дельты
- Один проект может иметь 1+ стандартов
- При добавлении нового стандарта система автоматически пересчитывает merge и completeness

---

### 3.6. Блок 6: Фактические данные

#### data_points

Главная таблица введённых или импортированных фактов.

```sql
create table data_points (
    id                      bigserial primary key,
    organization_id         bigint not null references organizations(id) on delete cascade,
    reporting_period_id     bigint not null references reporting_periods(id) on delete cascade,
    shared_element_id       bigint not null references shared_elements(id) on delete restrict,
    value_type              text not null check (value_type in ('number', 'text', 'boolean', 'date', 'enum', 'json')),
    numeric_value           numeric,
    text_value              text,
    boolean_value           boolean,
    date_value              date,
    json_value              jsonb,
    unit_code               text,
    methodology_id          bigint references methodologies(id) on delete set null,
    boundary_id             bigint references boundaries(id) on delete set null,
    source_record_id        bigint references source_records(id) on delete set null,
    -- Workflow
    status                  text not null default 'draft' check (status in ('draft', 'submitted', 'in_review', 'approved', 'rejected', 'needs_revision')),
    submitted_by            bigint references users(id) on delete set null,
    submitted_at            timestamptz,
    reviewed_by             bigint references users(id) on delete set null,
    reviewed_at             timestamptz,
    review_comment          text,
    -- Timestamps
    created_by              bigint references users(id) on delete set null,
    created_at              timestamptz not null default now(),
    updated_by              bigint references users(id) on delete set null,
    updated_at              timestamptz not null default now()
);
```

**Бизнес-правила:**

Данные привязаны к **SharedElement**, не к стандарту. Данные считаются одинаковыми (reuse), если совпадают:
- `shared_element_id`
- `unit_code`
- `reporting_period_id`
- `organization_id`
- `boundary_id`
- `methodology_id`

Если хотя бы один параметр отличается — создаётся отдельный DataPoint.

**Identity Rule for Reuse (правило идентичности):**

DataPoint считается пригодным для переиспользования (reuse), если совпадают **все** следующие параметры:

| Параметр | Поле | Описание |
|----------|------|----------|
| Сквозной элемент | `shared_element_id` | Тот же понятийный элемент |
| Организация | `organization_id` | Та же организация |
| Период | `reporting_period_id` | Тот же отчётный период |
| Единица измерения | `unit_code` | Та же единица (tCO2e, MWh и т.д.) |
| Boundary | `boundary_id` | Тот же организационный boundary |
| Методология | `methodology_id` | Та же методология расчёта |
| Измерения | полное совпадение `data_point_dimensions` | Все dimension_type + dimension_value совпадают |

Если **любой** из параметров отличается — это **другой DataPoint**, и система должна создать новую запись. Это правило критично для:
- Корректного UX при reuse (пользователь видит только точные совпадения)
- Правильной работы merge (не объединять данные с разными boundaries)
- Предотвращения «грязных» данных (два стандарта с разной гранулярностью не могут шарить один DataPoint)

**Workflow статусов:**

```
draft → submitted → in_review → approved
                              → rejected → (fix) → submitted
                              → needs_revision → (clarify) → submitted
```

| Из | В | Кто | Условия |
|----|---|-----|---------|
| — | draft | Сборщик | Создание нового DataPoint |
| draft | submitted | Сборщик | Все required поля заполнены |
| submitted | in_review | Система | Автоматически при наличии ревьюера |
| in_review | approved | Ревьюер | Данные корректны |
| in_review | rejected | Ревьюер | Обязателен review_comment |
| in_review | needs_revision | Ревьюер | Обязателен review_comment (мягкий возврат) |
| rejected | submitted | Сборщик | Исправления внесены |
| needs_revision | submitted | Сборщик | Уточнения внесены |
| approved | draft | ESG-менеджер | Откат (с обоснованием, запись в audit_log) |

#### data_point_dimensions

Разрезы конкретного значения.

```sql
create table data_point_dimensions (
    id                  bigserial primary key,
    data_point_id       bigint not null references data_points(id) on delete cascade,
    dimension_type      text not null,              -- scope, gas, category, facility, geography
    dimension_value     text not null,
    unique (data_point_id, dimension_type, dimension_value)
);
```

**Примеры:**
- `scope = Scope 3`, `category = Category 6`
- `gas = CH4`
- `facility = Котельная #3`

#### methodologies

```sql
create table methodologies (
    id                  bigserial primary key,
    code                text unique,
    name                text not null,
    description         text,
    reference_source    text,
    created_at          timestamptz not null default now()
);
```

#### boundaries

```sql
create table boundaries (
    id                  bigserial primary key,
    boundary_type       text not null,              -- operational_control, financial_control, equity_share
    description         text,
    created_at          timestamptz not null default now()
);
```

#### source_records

Провенанс: откуда пришёл факт.

```sql
create table source_records (
    id                  bigserial primary key,
    source_type         text not null check (source_type in ('manual', 'file_import', 'api', 'integration')),
    source_name         text,
    external_reference  text,
    payload             jsonb,
    created_at          timestamptz not null default now()
);
```

#### Evidence (доказательная база)

> **Полная спецификация модуля Evidence:** см. `docs/TZ-Evidence.md`

Evidence — отдельная доменная сущность (не attachment). Поддерживает файлы и ссылки, M:N привязки к data_points и requirement_items, обязательность через `requires_evidence`.

```sql
-- Добавить в requirement_items:
ALTER TABLE requirement_items
    ADD COLUMN requires_evidence boolean NOT NULL DEFAULT false;

-- Основная таблица
create table evidences (
    id                  bigserial primary key,
    organization_id     bigint not null references organizations(id) on delete cascade,
    type                text not null check (type in ('file', 'link')),
    title               text not null,
    description         text,
    source_type         text not null check (source_type in ('manual', 'upload', 'integration')),
    created_by          bigint references users(id) on delete set null,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now()
);

-- Файлы (1:1 с evidences)
create table evidence_files (
    evidence_id         bigint primary key references evidences(id) on delete cascade,
    file_name           text not null,
    file_uri            text not null,
    mime_type           text,
    file_size           integer
);

-- Ссылки (1:1 с evidences)
create table evidence_links (
    evidence_id         bigint primary key references evidences(id) on delete cascade,
    url                 text not null,
    label               text,
    access_note         text
);

-- Привязка evidence к data_point (M:N)
create table data_point_evidences (
    id                  bigserial primary key,
    data_point_id       bigint not null references data_points(id) on delete cascade,
    evidence_id         bigint not null references evidences(id) on delete cascade,
    linked_by           bigint references users(id) on delete set null,
    linked_at           timestamptz not null default now(),
    unique (data_point_id, evidence_id)
);

-- Привязка evidence к requirement_item (M:N)
create table requirement_item_evidences (
    id                  bigserial primary key,
    requirement_item_id bigint not null references requirement_items(id) on delete cascade,
    evidence_id         bigint not null references evidences(id) on delete cascade,
    linked_by           bigint references users(id) on delete set null,
    linked_at           timestamptz not null default now(),
    unique (requirement_item_id, evidence_id)
);
```

---

### 3.7. Блок 7: Привязка и покрытие

#### requirement_item_data_points

Явная привязка: какой DataPoint закрывает какое требование в проекте.

```sql
create table requirement_item_data_points (
    id                      bigserial primary key,
    reporting_project_id    bigint not null references reporting_projects(id) on delete cascade,
    requirement_item_id     bigint not null references requirement_items(id) on delete cascade,
    data_point_id           bigint not null references data_points(id) on delete cascade,
    binding_type            text not null check (binding_type in ('direct', 'derived', 'manual_override')),
    created_at              timestamptz not null default now(),
    unique (reporting_project_id, requirement_item_id, data_point_id)
);
```

**binding_type:**
- `direct` — DataPoint напрямую закрывает RequirementItem через SharedElement
- `derived` — DataPoint получен расчётом
- `manual_override` — привязка назначена вручную (не через SharedElement mapping)

#### requirement_item_statuses

Статус покрытия атомарного требования.

```sql
create table requirement_item_statuses (
    id                      bigserial primary key,
    reporting_project_id    bigint not null references reporting_projects(id) on delete cascade,
    requirement_item_id     bigint not null references requirement_items(id) on delete cascade,
    status                  text not null check (status in ('missing', 'partial', 'complete', 'not_applicable')),
    status_reason           text,
    validation_result       jsonb,
    last_checked_at         timestamptz,
    updated_at              timestamptz not null default now(),
    unique (reporting_project_id, requirement_item_id)
);
```

#### disclosure_requirement_statuses

Статус disclosure целиком (агрегат).

```sql
create table disclosure_requirement_statuses (
    id                          bigserial primary key,
    reporting_project_id        bigint not null references reporting_projects(id) on delete cascade,
    disclosure_requirement_id   bigint not null references disclosure_requirements(id) on delete cascade,
    status                      text not null check (status in ('missing', 'partial', 'complete', 'not_applicable')),
    completion_percent          numeric(5,2),
    missing_summary             jsonb,
    updated_at                  timestamptz not null default now(),
    unique (reporting_project_id, disclosure_requirement_id)
);
```

---

### 3.8. Блок 8: Пользователи, роли, workflow

#### users

```sql
create table users (
    id                  bigserial primary key,
    organization_id     bigint not null references organizations(id) on delete cascade,
    email               text not null unique,
    password_hash       text,                       -- null для SSO-only пользователей
    first_name          text not null,
    last_name           text not null,
    middle_name         text,
    position            text,                       -- "Директор по комплаенсу"
    role                text not null check (role in ('admin', 'esg_manager', 'collector', 'reviewer', 'auditor')),
    is_active           boolean not null default true,
    last_login_at       timestamptz,
    notification_prefs  jsonb,                      -- {"email": true, "in_app": true}
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now()
);
```

#### metric_assignments

Назначение метрик на пользователей.

```sql
create table metric_assignments (
    id                      bigserial primary key,
    reporting_project_id    bigint not null references reporting_projects(id) on delete cascade,
    shared_element_id       bigint not null references shared_elements(id) on delete cascade,
    collector_id            bigint references users(id) on delete set null,
    reviewer_id             bigint references users(id) on delete set null,
    deadline                date,
    status                  text not null default 'pending' check (status in ('pending', 'in_progress', 'submitted', 'approved')),
    created_at              timestamptz not null default now(),
    updated_at              timestamptz not null default now(),
    -- Сборщик и ревьюер не могут быть одним лицом
    check (collector_id is distinct from reviewer_id)
);
```

**Бизнес-правила:**
- Метрика может быть создана **без назначения** (`collector_id = null`, `reviewer_id = null`)
- В этом случае `status = 'pending'`, в UI: "Не назначен"
- ESG-менеджер назначает позже (через карточку метрики или матрицу назначений)
- Constraint: `collector_id != reviewer_id` — один человек не может и вводить, и ревьюить одну метрику

#### comments

Threaded comments для review-процесса.

```sql
create table comments (
    id                  bigserial primary key,
    data_point_id       bigint references data_points(id) on delete cascade,
    requirement_item_id bigint references requirement_items(id) on delete cascade,
    parent_comment_id   bigint references comments(id) on delete cascade,
    user_id             bigint not null references users(id) on delete cascade,
    comment_type        text not null check (comment_type in ('question', 'issue', 'suggestion', 'resolution', 'general')),
    body                text not null,
    is_resolved         boolean not null default false,
    created_at          timestamptz not null default now()
);
```

**Бизнес-правила:**
- Комментарий привязан к data_point и/или requirement_item
- Поддерживает threading через `parent_comment_id`
- `comment_type` помогает категоризировать: вопрос, проблема, рекомендация, решение
- `is_resolved` позволяет закрывать threads

#### audit_log

Immutable журнал всех действий.

```sql
create table audit_log (
    id                  bigserial primary key,
    organization_id     bigint not null references organizations(id) on delete cascade,
    user_id             bigint references users(id) on delete set null,
    action              text not null,              -- create, update, delete, submit, approve, reject, export, login
    entity_type         text not null,              -- DataPoint, Attachment, User, Standard, etc.
    entity_id           bigint,
    changes             jsonb,                      -- {"field": {"old": x, "new": y}}
    ip_address          inet,
    user_agent          text,
    created_at          timestamptz not null default now()
);
```

**Бизнес-правила:**
- Логируются ВСЕ изменения данных
- Audit log **immutable** — нельзя удалить или изменить
- Доступ: Администратор + Аудитор
- Хранение: минимум 5 лет

#### data_point_versions

Версионирование значений DataPoint.

```sql
create table data_point_versions (
    id                  bigserial primary key,
    data_point_id       bigint not null references data_points(id) on delete cascade,
    version             integer not null,
    numeric_value       numeric,
    text_value          text,
    json_value          jsonb,
    changed_by          bigint references users(id) on delete set null,
    changed_at          timestamptz not null default now(),
    change_reason       text
);
```

#### notifications

```sql
create table notifications (
    id                  bigserial primary key,
    user_id             bigint not null references users(id) on delete cascade,
    type                text not null,              -- assignment, deadline, review_request, approval, rejection
    title               text not null,
    message             text,
    entity_type         text,
    entity_id           bigint,
    is_read             boolean not null default false,
    sent_email          boolean not null default false,
    created_at          timestamptz not null default now()
);
```

---

### 3.9. Расчётные показатели

#### calculation_rules

```sql
create table calculation_rules (
    id                  bigserial primary key,
    shared_element_id   bigint not null references shared_elements(id) on delete cascade,
    code                text not null unique,
    name                text not null,
    formula             jsonb not null,             -- описание формулы
    created_at          timestamptz not null default now()
);
```

#### derived_data_points

```sql
create table derived_data_points (
    id                      bigserial primary key,
    data_point_id           bigint not null references data_points(id) on delete cascade,
    calculation_rule_id     bigint not null references calculation_rules(id) on delete restrict,
    created_at              timestamptz not null default now(),
    unique (data_point_id, calculation_rule_id)
);
```

**Правила: Input vs Calculated Data (ввод vs расчётные данные):**

| Правило | Описание |
|---------|----------|
| Read-only | Расчётные DataPoint (`derived_data_points`) **недоступны для редактирования** пользователем |
| Автопересчёт | При изменении любого source DataPoint, участвующего в формуле, расчётный DataPoint **пересчитывается автоматически** |
| Manual override | Ручное переопределение расчётного значения возможно только через `binding_type = 'manual_override'` в `requirement_item_data_points`. Требует явного действия ESG-менеджера |
| UI-индикация | Интерфейс **обязан** визуально различать input-данные и calculated-данные (иконка, цвет, tooltip с формулой) |
| Audit trail | При автопересчёте записывается запись в `data_point_versions` с `change_reason = 'auto_recalculation'` |
| Override warning | При установке `manual_override` система предупреждает: «Расчётное значение будет заменено. При изменении исходных данных автопересчёт не будет применён» |

---

### 3.10. Индексы

```sql
-- Каталог требований
create index idx_disclosure_requirements_standard_id
    on disclosure_requirements(standard_id);

create index idx_requirement_items_disclosure_requirement_id
    on requirement_items(disclosure_requirement_id);

-- Shared layer
create index idx_rise_requirement_item_id
    on requirement_item_shared_elements(requirement_item_id);

create index idx_rise_shared_element_id
    on requirement_item_shared_elements(shared_element_id);

-- Data points
create index idx_data_points_shared_element_id
    on data_points(shared_element_id);

create index idx_data_points_org_period
    on data_points(organization_id, reporting_period_id);

create index idx_data_points_status
    on data_points(status);

create index idx_data_point_dimensions_lookup
    on data_point_dimensions(dimension_type, dimension_value);

-- Bindings & completeness
create index idx_ridp_project_item
    on requirement_item_data_points(reporting_project_id, requirement_item_id);

create index idx_ris_project
    on requirement_item_statuses(reporting_project_id);

create index idx_drs_project
    on disclosure_requirement_statuses(reporting_project_id);

-- Users & assignments
create index idx_users_organization
    on users(organization_id);

create index idx_metric_assignments_project
    on metric_assignments(reporting_project_id);

create index idx_audit_log_entity
    on audit_log(entity_type, entity_id);

create index idx_notifications_user_unread
    on notifications(user_id) where is_read = false;
```

---

## 4. Merge Layer — логика объединения стандартов

### 4.1. Алгоритм merge

**Вход:** `reporting_project_id` → через `reporting_project_standards` получаем набор стандартов

**Шаги:**

```
Step 1: Собрать все requirement_items из выбранных стандартов
        (через disclosure_requirements → requirement_items)

Step 2: Через requirement_item_shared_elements сгруппировать по shared_element

Step 3: Для каждого shared_element определить:
        - required_by: [список стандартов, которые его требуют]
        - is_common: required_by.length > 1
        - overrides: [requirement_item_overrides для каждого стандарта]
        - deltas: [requirement_deltas, если есть]

Step 4: Выделить orphan requirements (не маппятся на shared_element)

Step 5: Сформировать MergedView
```

**SQL для merge view:**

```sql
SELECT
    se.id as shared_element_id,
    se.code,
    se.name,
    se.concept_domain,
    array_agg(DISTINCT s.code) as required_by_standards,
    count(DISTINCT s.id) as standard_count,
    dp.status as data_status,
    dp.numeric_value,
    dp.unit_code
FROM shared_elements se
JOIN requirement_item_shared_elements rise ON rise.shared_element_id = se.id
JOIN requirement_items ri ON ri.id = rise.requirement_item_id
JOIN disclosure_requirements dr ON dr.id = ri.disclosure_requirement_id
JOIN standards s ON s.id = dr.standard_id
JOIN reporting_project_standards rps ON rps.standard_id = s.id
    AND rps.reporting_project_id = :project_id
LEFT JOIN data_points dp ON dp.shared_element_id = se.id
    AND dp.organization_id = :org_id
    AND dp.reporting_period_id = :period_id
GROUP BY se.id, se.code, se.name, se.concept_domain, dp.status, dp.numeric_value, dp.unit_code
ORDER BY se.concept_domain, se.code;
```

### 4.2. Правила merge

| Ситуация | Правило |
|----------|---------|
| Оба стандарта требуют одно и то же | Один DataPoint, reuse |
| GRI требует total, IFRS требует breakdown | Total обязателен + breakdown как delta |
| Только один стандарт требует элемент | Элемент помечается required только для этого стандарта |
| Разные единицы измерения | Два DataPoint (конвертация не автоматическая) |
| Разные методологии | Два DataPoint (каждый со своей methodology_id) |
| Stricter rule wins | При merge: если один стандарт требует точнее — берётся строгое правило |

### 4.3. Добавление нового стандарта

При добавлении стандарта к проекту (INSERT в `reporting_project_standards`):

1. Система находит пересечения (через `requirement_item_shared_elements`)
2. Для пересечений — данные уже есть (reuse), `requirement_item_statuses.status = 'complete'`
3. Для дельт — подсвечивает: "IFRS дополнительно требует: financial linkage"
4. Для уникальных требований — `status = 'missing'`, нужен ввод
5. Пересчитывается completeness для нового стандарта

**UI-уведомление:**
> "Добавлен IFRS S2. 12 из 18 требований уже покрыты. 3 дельты. 3 новых требования."

---

## 5. Completeness Engine

Completeness Engine — выделенный сервис/модуль, отвечающий за автоматический расчёт статусов покрытия требований и disclosure на основе фактических данных.

### 5.1. Триггеры пересчёта

Completeness Engine запускается при следующих событиях:

| Событие | Описание |
|---------|----------|
| `data_point_change` | Создание, обновление, удаление или смена статуса DataPoint |
| `binding_change` | Создание или удаление записи в `requirement_item_data_points` |
| `standard_added` | Добавление нового стандарта к проекту (`reporting_project_standards`) |
| `rules_changed` | Изменение `validation_rule`, `granularity_rule`, `is_required` в `requirement_items` |

### 5.2. Логика определения статуса RequirementItem

Для каждого RequirementItem в контексте проекта:

```
IF exists binding in requirement_item_data_points
   AND data_point.status = 'approved':
    IF all required fields filled (numeric_value / text_value / etc.):
        IF all dimension_rules satisfied:
            IF all narrative requirements met (if item_type = 'narrative'):
                IF all attachment requirements met (if item_type = 'document'):
                    IF all validation_rules passed:
                        status = 'complete'
                    ELSE:
                        status = 'partial'
                        status_reason = "Validation rule failed: {rule_details}"
                ELSE:
                    status = 'partial'
                    status_reason = "Required document not attached"
            ELSE:
                status = 'partial'
                status_reason = "Narrative description required"
        ELSE:
            status = 'partial'
            status_reason = "Missing breakdown by {dimension_type}"
    ELSE:
        status = 'partial'
        status_reason = "Required field {field_name} is empty"
ELSE IF exists binding AND data_point.status IN ('draft', 'submitted', 'in_review'):
    status = 'partial'
    status_reason = "Data not yet approved"
ELSE:
    status = 'missing'
    status_reason = "No data submitted"
```

### 5.3. Логика определения статуса DisclosureRequirement

Для каждого DisclosureRequirement (агрегат по входящим RequirementItems):

```
IF all required items = 'complete':
    disclosure_status = 'complete'
    completion_percent = 100
ELSE IF any item has data (even partial):
    disclosure_status = 'partial'
    completion_percent = count(complete) / count(required) * 100
ELSE:
    disclosure_status = 'missing'
    completion_percent = 0
```

### 5.4. Completeness по стандарту

```
overall_score = count(complete mandatory disclosures) / count(total mandatory disclosures)
```

- Немандаторные disclosures не влияют на overall_score
- `not_applicable` исключается из расчёта (с обоснованием в `status_reason`)

### 5.5. Выходные данные

| Выход | Таблица | Описание |
|-------|---------|----------|
| `requirement_item_status` | `requirement_item_statuses` | Статус атомарного требования: missing / partial / complete / not_applicable |
| `disclosure_requirement_status` | `disclosure_requirement_statuses` | Агрегированный статус disclosure + `completion_percent` |
| `completion_percent` | `disclosure_requirement_statuses.completion_percent` | Процент заполненности disclosure (0..100) |

### 5.6. Правила пересчёта

- Пересчёт выполняется **асинхронно** после каждого триггерного события
- При `data_point_change` пересчитываются только затронутые `requirement_item_statuses` и их parent `disclosure_requirement_statuses`
- При `standard_added` пересчитываются все статусы нового стандарта + обновляются reuse-статусы
- При `rules_changed` пересчитываются все проекты, использующие изменённый `requirement_item`
- Каскадный пересчёт: RequirementItem → DisclosureRequirement → Standard overall_score

### 5.7. Требования к производительности

- Пересчёт одного RequirementItem: < 100ms
- Пересчёт всех статусов проекта (full recalculation): < 5s для 500 requirement items
- При массовых операциях (batch approve, standard added) пересчёт выполняется одним batch, а не поэлементно
- Результаты кэшируются в таблицах статусов, UI читает из кэша

---

## 6. Роли и права доступа

### 6.1. Матрица прав

| Действие | admin | esg_manager | collector | reviewer | auditor |
|----------|:---:|:---:|:---:|:---:|:---:|
| Настройка стандартов | ✅ | ❌ | ❌ | ❌ | ❌ |
| Управление пользователями | ✅ | ❌ | ❌ | ❌ | ❌ |
| Настройка периодов | ✅ | ✅ | ❌ | ❌ | ❌ |
| Назначение метрик | ✅ | ✅ | ❌ | ❌ | ❌ |
| Ввод данных | ❌ | ✅ | ✅* | ❌ | ❌ |
| Загрузка доказательств | ❌ | ✅ | ✅* | ❌ | ❌ |
| Ревью данных | ❌ | ✅ | ❌ | ✅* | ❌ |
| Публикация отчёта | ❌ | ✅ | ❌ | ❌ | ❌ |
| Просмотр данных | ✅ | ✅ | ✅* | ✅* | ✅ |
| Merge View | ✅ | ✅ | ❌ | ❌ | ✅ |
| Журнал аудита | ✅ | ✅ | ❌ | ❌ | ✅ |

`*` — только назначенные метрики / данные

---

## 7. Уведомления

| Событие | Получатель | Канал |
|---------|-----------|-------|
| Метрика назначена | Сборщик | in-app + email |
| DataPoint submitted | Ревьюер | in-app + email |
| DataPoint approved | Сборщик | in-app |
| DataPoint rejected | Сборщик | in-app + email |
| Дедлайн через 3 дня | Сборщик | in-app + email |
| Дедлайн просрочен | Сборщик + ESG-менеджер | in-app + email |
| Новый стандарт добавлен | ESG-менеджер | in-app |
| Completeness достигла 100% | ESG-менеджер | in-app |

---

## 8. Экраны и UI

### 8.1. Общий layout

```
┌──────────────────────────────────────────────────┐
│  Context Topbar                                  │
│  [Logo] [Period] ─────[68%]───── [Deadline][Export]│
├────────┬─────────────────────────────────────────┤
│        │                                         │
│ Side-  │  Main Content Area                      │
│  bar   │                                         │
│        │                                         │
│ Overv. │                                         │
│ Coll.  │                                         │
│ Valid.  │                                         │
│ Tasks  │                                         │
│ Data S │                                         │
│ Export │                                         │
│        │                                         │
└────────┴─────────────────────────────────────────┘
```

### 8.2. Список экранов

| # | Экран | URL | Описание |
|---|-------|-----|----------|
| 1 | Auth | `/login` | Авторизация |
| 2 | Overview | `/dashboard` | Прогресс, issues, tasks, категории |
| 3 | Collection | `/collection` | Таблица метрик со статусами |
| 4 | Data Entry | `/collection/:id/edit` | Wizard ввода данных |
| 5 | Validation | `/validation` | Split panel: ревью |
| 6 | Tasks | `/tasks` | Персональные задачи |
| 7 | Data Sources | `/evidence` | Хранилище файлов |
| 8 | Export | `/report` | GRI Content Index, readiness |
| 9 | **Merge View** | `/merge` | Матрица элемент × стандарт |
| 10 | Standards Setup | `/settings/standards` | Выбор стандартов |
| 11 | Users | `/settings/users` | Список пользователей |
| 12 | User Edit | `/settings/users/:id` | Карточка пользователя |
| 13 | Assignments | `/settings/assignments` | Матрица назначений |
| 14 | Periods | `/settings/periods` | Управление периодами |
| 15 | Company | `/settings/company` | Настройки компании |
| 16 | Audit Log | `/audit` | Журнал действий |

### 8.3. Merge View — ключевой экран

```
┌───────────────────┬─────┬────────┬───────┬──────────┐
│ Element           │ GRI │ IFRS   │ SASB  │ Status   │
├───────────────────┼─────┼────────┼───────┼──────────┤
│ Scope 1 total     │ ✔   │ ✔      │ ✔     │ complete │
│ Scope 2 total     │ ✔   │ ✔      │ —     │ complete │
│ Scope 3 by cat.   │ ❌  │ ✔ +Δ   │ —     │ missing  │
│ Energy consump.   │ ✔   │ —      │ ✔     │ partial  │
│ Water withdrawal  │ ✔   │ —      │ —     │ complete │
│ Board diversity   │ ✔   │ —      │ ✔     │ missing  │
└───────────────────┴─────┴────────┴───────┴──────────┘

Легенда:
  ✔  — требуется стандартом, данные есть
  ❌ — требуется стандартом, данных нет
  +Δ — есть дополнительные требования (дельта)
  —  — стандарт не требует
```

**Интерактивность:**
- Клик по ✔/❌ → переход к DataPoint или форме ввода
- Клик по +Δ → popup с описанием дельты
- Фильтры: по concept_domain, по статусу, по стандарту
- Summary bar: `Coverage: GRI 72% | IFRS 45% | SASB 60%`

### 8.4. UI-паттерны

| Паттерн | Описание |
|---------|----------|
| Status-first | В таблицах статус — первая колонка |
| Visual hierarchy | Проблемы → красный/оранжевый; прогресс → зелёный; secondary → muted |
| Actionable | Каждый элемент с проблемой имеет CTA |
| Fast scan summary | Кликабельные stat-блоки над таблицами |
| Continue collection | Глобальная кнопка → первый незаполненный элемент |

---

## 9. Валидация данных

### 9.1. Уровни валидации

| Уровень | Когда | Что проверяет |
|---------|-------|---------------|
| **Field** | При вводе | Тип данных, min/max, формат |
| **Record** | При submit | Все required поля, dimension_rules |
| **Cross-record** | При approve | Outlier detection, consistency |
| **Standard** | Completeness check | Все mandatory disclosures заполнены |

### 9.2. Outlier detection

```
IF abs(current_value - previous_value) / previous_value > deviation_threshold:
    flag as outlier → require reviewer attention
```

- `deviation_threshold` из `requirement_items.validation_rule`
- Default: 40%
- Outlier **не блокирует** submit, но помечается в UI

### 9.3. Cross-record consistency

```
IF scope1 + scope2 != total_reported → flag inconsistency
IF electricity > total_energy → flag inconsistency
```

---

## 10. API — основные endpoints

### 10.1. Standards & Requirements

```
GET    /api/standards                           — Список стандартов
GET    /api/standards/:id                       — Детали + sections
GET    /api/standards/:id/disclosures           — Требования стандарта
GET    /api/standards/:id/disclosures/:id/items — Атомарные требования
```

### 10.2. Merge

```
GET    /api/projects/:id/merge                  — Merged view
GET    /api/projects/:id/merge/coverage         — Coverage по каждому стандарту
POST   /api/projects/:id/standards              — Добавить стандарт + пересчитать
DELETE /api/projects/:id/standards/:id          — Убрать стандарт
```

### 10.3. Data Points

```
GET    /api/data-points                         — Список (с фильтрами)
GET    /api/data-points/:id                     — Детали + dimensions + versions
POST   /api/data-points                         — Создать (draft)
PUT    /api/data-points/:id                     — Обновить
POST   /api/data-points/:id/submit              — Отправить на ревью
POST   /api/data-points/:id/approve             — Одобрить
POST   /api/data-points/:id/reject              — Отклонить (+ comment)
```

### 10.4. Evidence

> Полная спецификация: `docs/TZ-Evidence.md`, раздел 6

```
GET    /api/evidences                                    — Список (фильтры: type, source_type, unlinked)
GET    /api/evidences/:id                                — Детали + файл/ссылка + привязки
POST   /api/evidences                                    — Создать (file или link)
POST   /api/evidences/upload                             — Upload файла (multipart/form-data)
PUT    /api/evidences/:id                                — Обновить title, description
DELETE /api/evidences/:id                                — Удалить (если не в approved scope)
POST   /api/data-points/:id/evidences                    — Привязать evidence к data_point
DELETE /api/data-points/:id/evidences/:evidenceId        — Отвязать
GET    /api/data-points/:id/evidences                    — Список evidence для data_point
POST   /api/requirement-items/:id/evidences              — Привязать evidence к requirement_item
DELETE /api/requirement-items/:id/evidences/:evidenceId  — Отвязать
GET    /api/requirement-items/:id/evidences              — Список evidence для requirement_item
```

### 10.5. Completeness

```
GET    /api/projects/:id/completeness           — Сводный отчёт
GET    /api/projects/:id/completeness/:std_id   — По стандарту
```

### 10.6. Assignments

```
GET    /api/projects/:id/assignments            — Матрица назначений
POST   /api/projects/:id/assignments            — Создать назначение
PUT    /api/assignments/:id                     — Обновить
POST   /api/projects/:id/assignments/bulk       — Массовое назначение
```

### 10.7. Users

```
GET    /api/users                               — Список
POST   /api/users                               — Создать
PUT    /api/users/:id                           — Обновить
GET    /api/users/:id/assignments               — Назначения пользователя
```

### 10.8. Export

```
GET    /api/projects/:id/export/readiness       — Готовность к экспорту
POST   /api/projects/:id/export/gri-index       — GRI Content Index
POST   /api/projects/:id/export/report          — Отчёт (PDF/Excel)
```

### 10.9. Audit

```
GET    /api/audit-log                           — Журнал (с фильтрами)
```

---

## 11. Предзагруженные данные (Seed)

### 11.1. Стандарты

| Стандарт | Версия | Disclosures | RequirementItems |
|----------|--------|-------------|-----------------|
| GRI Standards | 2021 | ~35 | ~120 |
| IFRS S2 | 2023 | ~25 | ~90 |
| SASB (Oil & Gas) | 2023 | ~15 | ~50 |

### 11.2. SharedElements

~80 предзагруженных элементов по доменам:
- **Emissions** (~20): Scope 1/2/3, by gas, by category, intensity
- **Energy** (~10): consumption, intensity, renewables
- **Water** (~8): withdrawal, discharge, consumption
- **Waste** (~8): generated, diverted, disposal
- **Workforce** (~12): headcount, turnover, diversity, training
- **Health & Safety** (~8): incidents, fatalities, rates
- **Governance** (~14): board composition, anti-corruption, ethics, tax

### 11.3. Mappings

Предзагруженные mappings для всех трёх стандартов на SharedElements, включая:
- ~40 `full` mappings
- ~15 `partial` mappings (с соответствующими overrides/deltas)

### 11.4. Methodologies

- GHG Protocol (Scope 1, 2, 3)
- Location-based method
- Market-based method
- Equity share approach
- Operational control approach

---

## 12. Нефункциональные требования

### 12.1. Производительность

| Операция | Цель |
|----------|------|
| Загрузка любого экрана | < 2 сек |
| Merge calculation (3 стандарта) | < 3 сек |
| Completeness check | < 5 сек |
| Export (PDF/Excel) | < 30 сек |

### 12.2. Безопасность

- Аутентификация: email + password, SSO (SAML 2.0 / OAuth 2.0)
- Авторизация: RBAC
- Шифрование: TLS 1.3, at rest AES-256
- Сессии: JWT, timeout 8 часов
- 2FA: опционально, TOTP

### 12.3. Масштабируемость

- До 50 одновременных пользователей
- До 10 000 DataPoints на период
- До 5 000 файлов Evidence
- До 5 стандартов в одном проекте

### 12.4. Доступность

- Uptime: 99.5%
- Бэкапы: ежедневные, хранение 30 дней
- RTO: 4 часа, RPO: 1 час

---

## 13. Этапы реализации

### Phase 1: MVP (8–10 недель)

**Scope:**
- Auth (login/logout)
- Один стандарт (GRI)
- Data collection (CRUD DataPoint)
- Evidence upload
- Workflow (draft → submit → approve/reject)
- Completeness по GRI
- Basic export (GRI Content Index)
- User management + assignments
- Audit log

**Минимальные таблицы:**
- standards, disclosure_requirements, requirement_items
- shared_elements, requirement_item_shared_elements
- organizations, reporting_periods, reporting_projects, reporting_project_standards
- data_points, data_point_dimensions
- requirement_item_data_points, requirement_item_statuses
- users, metric_assignments, audit_log

**Не входит:**
- Merge layer, multi-standard
- Deltas, overrides
- SSO, notifications
- Расчётные показатели

### Phase 2: Multi-standard + Merge (6–8 недель)

**Scope:**
- Добавление IFRS S2, SASB
- Merge Layer (алгоритм + UI)
- requirement_deltas, requirement_item_overrides
- Merge View экран
- Coverage per standard
- "Add standard" flow с пересчётом
- Notifications (in-app + email)

### Phase 3: Advanced (4–6 недель)

**Scope:**
- Расчётные показатели (calculation_rules, derived_data_points)
- Advanced export (PDF report, Excel data dump)
- SSO integration
- Cross-record validation
- Requirement item dependencies
- API для внешних систем
- Dashboard analytics

---

## 14. Открытые вопросы

| # | Вопрос | Варианты | Решение |
|---|--------|----------|---------|
| 1 | Стек фронтенда | React + Next.js / Vue + Nuxt | React + Next.js 14 (App Router) + shadcn/ui ✅ |
| 2 | Стек бэкенда | Node.js + Prisma / Python + FastAPI / Go | Python + FastAPI + SQLAlchemy 2.0 ✅ |
| 3 | База данных | PostgreSQL | PostgreSQL 16 ✅ |
| 4 | Хостинг | AWS / GCP / Self-hosted | Docker Compose (MVP), AWS ECS (Phase 3) ✅ |
| 5 | Файловое хранилище | S3 / MinIO / GCS | MinIO (dev) / S3 (prod) ✅ |
| 6 | Multi-language UI | RU+EN / RU+EN+KZ | ? |
| 7 | Интеграции | 1C / SAP / Excel import / API | ? |
| 8 | Версионирование стандартов | При обновлении GRI 2021→2024: новая запись или inplace? | Новая запись (рек.) |
| 9 | Версионирование mappings | Маппинги привязаны к версии стандарта? | Да (рек.) |
| 10 | Кастомные стандарты | Может ли клиент создать свой стандарт? | Да (Phase 3) |

---

## 15. Приложения

### Приложение А. Пример merge GRI + IFRS S2

**Scope 1 emissions:**

| Аспект | GRI 305-1 | IFRS S2.29(a) | Merge result |
|--------|-----------|---------------|-------|
| Total value | Required | Required | **1 DataPoint (reuse)** |
| Unit | t CO2e | t CO2e | Совпадает |
| By gas breakdown | Optional | Required | **Required (stricter wins)** |
| Financial impact | Not required | Required | **Delta: additional_item** |
| Methodology | GHG Protocol | GHG Protocol | Совпадает |

### Приложение Б. Минимально жизнеспособное ядро (11 таблиц)

Если стартовать с урезанного ядра:

```
standards
disclosure_requirements
requirement_items
shared_elements
requirement_item_shared_elements
reporting_projects
reporting_project_standards
data_points
data_point_dimensions
requirement_item_data_points
requirement_item_statuses
```

Этого хватит чтобы:
- Загрузить стандарты
- Выбрать GRI + IFRS
- Показать общие элементы
- Переиспользовать одинаковые data points
- Отдельно считать coverage

### Приложение В. Справочник статусов

```
data_points.status:
  draft           — черновик, можно редактировать
  submitted       — отправлен, ожидает ревью
  in_review       — ревьюер взял в работу
  approved        — одобрен
  rejected        — отклонён, нужны исправления
  needs_revision  — требует доработки (мягкий возврат)

requirement_item_statuses.status:
  missing         — данных нет
  partial         — данные есть, но неполные / не approved
  complete        — полностью закрыт
  not_applicable  — не применимо (с обоснованием)

reporting_projects.status:
  draft       — проект создан
  in_progress — идёт сбор данных
  review      — финальная проверка
  published   — опубликован

reporting_periods.status:
  open        — можно вводить данные
  closed      — ввод закрыт
  archived    — в архиве
```
