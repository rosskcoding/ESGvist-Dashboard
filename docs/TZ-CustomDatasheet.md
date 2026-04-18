# ТЗ: Project Settings -> Custom Datasheet

**Модуль:** проектный конструктор custom datasheet  
**Версия:** 1.0  
**Статус:** Draft / на согласовании  
**Дата:** 2026-04-17

---

## 1. Контекст и проблема

В текущей системе есть:

- master-каталог стандартов (`standards`, `disclosure_requirements`, `requirement_items`);
- нормализованный слой метрик (`shared_elements`);
- проектные assignment/data point/evidence workflow.

Но отсутствует удобный проектный слой, где ESG-менеджер может собрать собственный "документ данных":

- частично из метрик, уже пришедших из стандартов;
- частично из уже существующих tenant custom metrics;
- частично из новых custom metrics, созданных прямо в проекте.

Проблема текущего состояния:

- custom metric можно создать только технически, а не как нормальный продуктовый flow;
- нет проектного экрана, где можно собрать curated набор метрик под конкретный клиентский datasheet;
- если ввести обязательные `section -> group -> metric`, модель становится слишком тяжёлой для первого рабочего сценария.

---

## 2. Цель

Добавить в `Project Settings` новый таб/экран `Custom Datasheet`, который позволит:

- создать один или несколько project-scoped datasheet-контейнеров;
- собирать datasheet из framework metrics и custom metrics;
- создавать новый custom metric прямо внутри datasheet flow;
- классифицировать item по укрупнённой бизнес-категории (`Category / Pillar`);
- использовать datasheet без отдельного сложного каталога sections/groups/disclosures.

---

## 3. Ключевое решение

### 3.1. Datasheet — это контейнер, а не новый стандарт

`Custom Datasheet` не является ещё одним `standard`.

Это project-scoped curated view, в которую включаются уже существующие метрики или создаются новые tenant custom metrics.

### 3.2. В v1 не вводить обязательные Section/Group сущности

Для `v1` не требуется:

- отдельная таблица `datasheet_sections`;
- отдельная таблица `datasheet_groups`;
- отдельный workflow "сначала создай section, потом создай group".

Причина:

- это перегружает UX;
- не соответствует основному use case;
- не нужно для интеграции с текущими `shared_elements`, `assignments`, `data_points`.

### 3.3. Обязательная классификация — Category

Каждый item в datasheet обязан иметь `category`.

`Category` используется как:

- основной пользовательский навигационный слой;
- будущий `pillar`/колонка/секция в UI;
- способ смешивать framework и custom items в одном документе.

### 3.4. Display Group — опциональный текстовый grouping label

Вместо отдельной иерархии `section/group` вводится простое поле:

- `display_group` (nullable text)

Пример:

- category: `Governance`
- display_group: `Board composition`

Это:

- не отдельная справочная сущность;
- не требует предварительного создания;
- используется только для удобства отображения.

### 3.5. Metric definition живёт отдельно от datasheet

Custom metric должен существовать как самостоятельная tenant metric definition в `shared_elements`.

Datasheet не "владеет" метрикой, а лишь включает её в свой состав.

Это нужно, чтобы один и тот же custom metric можно было:

- назначать в assignments;
- собирать в collection;
- привязывать к evidence;
- переиспользовать в нескольких datasheet;
- использовать вне datasheet.

---

## 4. Термины

| Термин | Смысл |
|--------|-------|
| `Framework metric` | Метрика из internal catalog / standards-модели |
| `Custom metric` | Tenant metric, созданная пользователем/организацией |
| `Custom Datasheet` | Project-scoped контейнер с curated набором метрик |
| `Datasheet item` | Запись внутри datasheet, указывающая на metric + display metadata |
| `Category` | Обязательная укрупнённая бизнес-классификация |
| `Display group` | Опциональный текстовый grouping label внутри category |

---

## 5. Модель категорий

### 5.1. Категории v1

Для `v1` вводится фиксированный справочник:

- `environmental`
- `social`
- `governance`
- `business_operations`
- `other`

UI labels:

- `Environmental`
- `Social`
- `Governance`
- `Business / Operations`
- `Other`

### 5.2. Почему не использовать только standard sections

Sections из стандарта нужны для внутренней структуры framework catalog, но не подходят как универсальный UX-слой для custom datasheet, потому что:

- у разных стандартов разные section trees;
- custom metrics вообще не обязаны иметь section;
- пользователю нужен более устойчивый business-level grouping.

### 5.3. Автоподсказка category

При добавлении standard metric система может предлагать category автоматически:

- по `shared_elements.concept_domain`;
- по `standard_catalog.catalog_group_code` для стандартов, где это уже определено;
- fallback → `other`.

Примеры:

- `emissions`, `energy`, `water`, `waste` → `environmental`
- `workforce`, `human_rights`, `community` → `social`
- `governance` → `governance`
- всё нераспознанное → `other`

Пользователь всегда может переопределить category вручную.

---

## 6. UX flow по экранам

## 6.1. Entry point

Новый таб в проекте:

- `Projects -> [Project] -> Settings -> Custom Datasheet`

Экран находится рядом с:

- `General`
- `Standards`
- `Boundary`
- `Team`

Новый таб:

- `Custom Datasheet`

## 6.2. Empty state

Если datasheet ещё нет:

- заголовок: `Custom Datasheet`
- описание: `Assemble a project-specific reporting sheet using framework metrics and your own custom fields.`
- primary CTA: `Create datasheet`

## 6.3. Create Datasheet dialog

Поля:

- `Name` — обязательное
- `Description` — optional
- `Status` — `draft` по умолчанию

После создания пользователь попадает в builder datasheet.

## 6.4. Datasheet Builder

Экран builder показывает:

- header с названием datasheet;
- summary:
  - total items
  - framework items
  - custom items
  - categories used
- primary CTA: `Add item`

Отображение item:

- сгруппировано по `Category`;
- внутри category может быть подзаголовок `display_group`, если он заполнен;
- если `display_group` пуст, item просто показывается в category list.

Важно:

- category — это часть модели данных;
- колонка/accordion/section в UI — это только способ отрисовки.

Система не обязана в `v1` рисовать именно board-columns layout. Достаточно grouped list по category.

## 6.5. Add Item flow

Кнопка `Add item` открывает выбор источника:

1. `From standards`
2. `From existing custom`
3. `Create new custom`

### 6.5.1. From standards

Пользователь видит searchable picker:

- search by metric code / metric name / standard code / disclosure code;
- filters:
  - attached standards only
  - category
  - concept domain

Для каждого результата показывается:

- metric name
- metric code
- standard/disclosure context
- suggested category

После выбора открывается mini-form:

- `Category` — required, prefilled
- `Display group` — optional
- `Label override` — optional
- `Help text` — optional
- `Collection scope`:
  - `Project level`
  - `Entity level`
  - `Facility level`
- при необходимости:
  - `Entity`
  - `Facility`

Далее:

- если assignment уже существует для этого context → reuse;
- если assignment отсутствует → система создаёт assignment автоматически.

### 6.5.2. From existing custom

Пользователь видит список tenant custom metrics организации:

- search by code / name;
- filters by category / type / status.

Далее шаги те же:

- выбрать category;
- optionally указать display_group;
- выбрать collection scope/context;
- reuse existing assignment или создать новый assignment.

### 6.5.3. Create new custom

Это основной новый flow.

Форма:

- `Metric name` — required
- `Metric code` — optional editable, по умолчанию генерируется из name
- `Category` — required
- `Display group` — optional
- `Description` — optional
- `Value type` — required:
  - `number`
  - `text`
  - `boolean`
  - `date`
  - `enum`
  - `document`
- `Unit` — optional / required for number where applicable
- `Evidence required` — boolean
- `Methodology required` — boolean
- `Collection scope`:
  - `Project level`
  - `Entity level`
  - `Facility level`
- `Entity / Facility` — optional depending on scope

Submit:

- создаётся tenant custom metric в `shared_elements`;
- создаётся assignment для проекта и выбранного context;
- создаётся datasheet item;
- пользователь остаётся в builder.

Дополнительный CTA:

- `Create and open in collection`

В этом случае после создания:

- если datapoint уже есть → открывается он;
- если datapoint отсутствует → он создаётся и открывается collection flow.

## 6.6. Item actions

Для каждого datasheet item:

- `Open data point`
- `Open in assignments`
- `Edit display settings`
- `Move category`
- `Archive from datasheet`

Важно:

- удаление item из datasheet не должно автоматически удалять `shared_element`;
- удаление item из datasheet не должно автоматически удалять assignment/data point;
- datasheet — это curated view, не владелец runtime данных.

## 6.7. Evidence flow

Evidence по-прежнему привязывается к data point.

Datasheet не становится новым evidence owner.

Связь:

- datasheet item → assignment / data point
- evidence → data point

В будущем evidence drawer может дополнительно показывать:

- `Used in datasheet: BP ESG Datasheet`

Но это не блокирующее требование для `v1`.

---

## 7. API endpoints

## 7.1. Datasheet list/create

### `GET /api/projects/{project_id}/custom-datasheets`

Возвращает список datasheet проекта.

Response item:

- `id`
- `name`
- `description`
- `status`
- `item_count`
- `framework_item_count`
- `custom_item_count`
- `updated_at`

### `POST /api/projects/{project_id}/custom-datasheets`

Request:

```json
{
  "name": "BP ESG Datasheet",
  "description": "Project-specific client sheet for BP",
  "status": "draft"
}
```

## 7.2. Datasheet read/update/archive

### `GET /api/projects/{project_id}/custom-datasheets/{datasheet_id}`

Возвращает:

- header datasheet
- grouped items by category
- counts

### `PATCH /api/projects/{project_id}/custom-datasheets/{datasheet_id}`

Изменяемые поля:

- `name`
- `description`
- `status`

### `POST /api/projects/{project_id}/custom-datasheets/{datasheet_id}/archive`

Архивирует datasheet, не удаляя runtime данные.

## 7.3. Search options for add-item flow

### `GET /api/projects/{project_id}/custom-datasheet-options`

Query params:

- `source=framework|custom|all`
- `q=...`
- `category=...`
- `attached_only=true|false`

Возвращает search results с унифицированной структурой:

- `source_type`
- `shared_element_id`
- `shared_element_code`
- `shared_element_name`
- `owner_layer`
- `is_custom`
- `suggested_category`
- `framework_context`:
  - `standard_code`
  - `standard_name`
  - `disclosure_code`
  - `disclosure_title`

## 7.4. Add item from existing metric

### `POST /api/projects/{project_id}/custom-datasheets/{datasheet_id}/items`

Request:

```json
{
  "shared_element_id": 123,
  "source_type": "framework",
  "category": "governance",
  "display_group": "Board composition",
  "label_override": "Female representation on board",
  "help_text": "Use the latest approved board composition source.",
  "collection_scope": "entity",
  "entity_id": 2,
  "facility_id": null,
  "create_assignment_if_missing": true
}
```

Response:

- datasheet item data
- `assignment_id`
- `assignment_created`

## 7.5. Create new custom metric + add to datasheet

### `POST /api/projects/{project_id}/custom-datasheets/{datasheet_id}/items/create-custom`

Request:

```json
{
  "metric": {
    "name": "Female representation on board",
    "code": "CUST-BP-BOARD-DIVERSITY",
    "description": "Percentage of female board members.",
    "category": "governance",
    "value_type": "number",
    "default_unit_code": "%",
    "evidence_required": true,
    "methodology_required": false
  },
  "datasheet_item": {
    "display_group": "Board composition",
    "label_override": null,
    "help_text": "Attach the current BP board composition source."
  },
  "collection_scope": "entity",
  "entity_id": 2,
  "facility_id": null
}
```

Response:

- `shared_element`
- `assignment`
- `datasheet_item`
- `data_point` (optional, only if immediate create/open requested)

## 7.6. Update datasheet item

### `PATCH /api/projects/{project_id}/custom-datasheets/{datasheet_id}/items/{item_id}`

Изменяемые поля:

- `category`
- `display_group`
- `label_override`
- `help_text`
- `sort_order`
- `is_required`

Важно:

- patch item не меняет исходную `shared_element` definition, если пользователь редактирует только display metadata.

## 7.7. Remove item from datasheet

### `DELETE /api/projects/{project_id}/custom-datasheets/{datasheet_id}/items/{item_id}`

Удаляет item из datasheet.

Не удаляет:

- `shared_element`
- `assignment`
- `data_point`
- `evidence`

---

## 8. Таблицы

## 8.1. Не создавать новую таблицу custom metrics

Для `v1` custom metrics должны жить в уже существующей таблице `shared_elements`.

Причина:

- это уже центральная metric definition модель;
- она уже связана с `metric_assignments`, `data_points`, `mappings`, `evidence` flow;
- отдельная таблица custom metrics создаст лишний разрыв.

## 8.2. Новая таблица `custom_datasheets`

```sql
create table custom_datasheets (
    id                  bigserial primary key,
    reporting_project_id bigint not null references reporting_projects(id) on delete cascade,
    name                text not null,
    description         text,
    status              text not null default 'draft'
                        check (status in ('draft', 'active', 'archived')),
    created_by          bigint references users(id) on delete set null,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now()
);

create index ix_custom_datasheets_project
    on custom_datasheets(reporting_project_id);
```

## 8.3. Новая таблица `custom_datasheet_items`

```sql
create table custom_datasheet_items (
    id                  bigserial primary key,
    custom_datasheet_id bigint not null references custom_datasheets(id) on delete cascade,
    reporting_project_id bigint not null references reporting_projects(id) on delete cascade,
    shared_element_id   bigint not null references shared_elements(id) on delete restrict,
    assignment_id       bigint references metric_assignments(id) on delete set null,
    source_type         text not null
                        check (source_type in ('framework', 'existing_custom', 'new_custom')),
    category            text not null
                        check (category in ('environmental', 'social', 'governance', 'business_operations', 'other')),
    display_group       text,
    label_override      text,
    help_text           text,
    collection_scope    text not null
                        check (collection_scope in ('project', 'entity', 'facility')),
    entity_id           bigint references company_entities(id) on delete set null,
    facility_id         bigint references company_entities(id) on delete set null,
    is_required         boolean not null default true,
    sort_order          integer not null default 0,
    status              text not null default 'active'
                        check (status in ('active', 'archived')),
    created_by          bigint references users(id) on delete set null,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now()
);

create index ix_custom_datasheet_items_datasheet
    on custom_datasheet_items(custom_datasheet_id, category, sort_order);

create index ix_custom_datasheet_items_shared_element
    on custom_datasheet_items(shared_element_id);
```

## 8.4. Почему `assignment_id` nullable

Причины:

- item может быть добавлен в datasheet до окончательной настройки assignment context;
- часть item может сначала собираться как curated design layer;
- assignment может быть создан позже при первом переходе в collection.

Но для `v1` рекомендуется default behavior:

- если context выбран и assignment отсутствует, создавать assignment сразу.

---

## 9. Как это ляжет на текущие `shared_elements` и `assignments`

## 9.1. Shared elements

Текущая стратегия:

- internal/framework metrics живут в `shared_elements` с:
  - `owner_layer = 'internal_catalog'`
- custom tenant metrics живут там же с:
  - `owner_layer = 'tenant_catalog'`
  - `organization_id = tenant org`
  - `is_custom = true`

Это правильная модель и её нужно продолжать использовать.

### Правило создания custom metric

При `Create new custom` система должна создавать `shared_elements` запись со значениями:

- `code = CUST-*`
- `name`
- `description`
- `default_value_type`
- `default_unit_code`
- `concept_domain` (optional, если есть)
- `element_key`
- `owner_layer = 'tenant_catalog'`
- `organization_id = project.organization_id`
- `lifecycle_status = 'active'`
- `is_custom = true`

## 9.2. Assignments

Текущая runtime модель уже завязана на:

- `metric_assignments`
- `data_points`
- `evidence`

Поэтому datasheet не должен изобретать новый collection runtime.

Правильное правило:

- datasheet item использует существующий assignment runtime;
- если нужен сбор данных, item должен быть привязан к assignment context.

### Поведение add-item

#### Если metric уже назначен в проекте на нужный context

- reuse existing `metric_assignments` row;
- `custom_datasheet_items.assignment_id = existing_assignment.id`

#### Если metric существует, но assignment отсутствует

- создать новый assignment;
- записать `assignment_id`

#### Если создаётся новый custom metric

Система выполняет 3 шага:

1. создать `shared_element` tenant type;
2. создать `metric_assignment`;
3. создать `custom_datasheet_item`

## 9.3. Data points

`DataPoint` создаётся либо:

- при первом заходе в collection;
- либо сразу, если пользователь выбрал `Create and open in collection`.

Datasheet не должен напрямую дублировать таблицу `data_points`.

## 9.4. Evidence

Evidence остаётся привязанным к `data_point`.

Для интеграции без взрыва:

- ничего не менять в ownership evidence;
- datasheet использует уже существующий data point/evidence flow;
- drawer evidence может дополнительно показывать datasheet membership как derived context.

---

## 10. Что не делать в v1

Не делать:

- отдельный mini-framework engine для datasheet;
- отдельные `section` и `group` таблицы;
- собственные datasheet-specific datapoints;
- direct evidence binding к datasheet item;
- complex versioning/revision workflow для datasheet;
- отдельный standard-like disclosure tree для кастома.

---

## 11. Минимальный пилотный сценарий

## 11.1. Use case

Пользователь открывает:

- `Project Settings -> Custom Datasheet`

И делает:

1. `Create datasheet` → `BP ESG Datasheet`
2. `Add item` → `Create new custom`
3. заполняет:
   - `Metric name`: `Female representation on board`
   - `Metric code`: `CUST-BP-BOARD-DIVERSITY`
   - `Category`: `Governance`
   - `Display group`: `Board composition`
   - `Type`: `number`
   - `Unit`: `%`
   - `Evidence required`: `yes`
   - `Collection scope`: `Entity level`
   - `Entity`: `GreenTech Energy GmbH`
4. система:
   - создаёт tenant custom metric
   - создаёт assignment
   - добавляет item в `BP ESG Datasheet`
5. после этого пользователь может:
   - открыть collection
   - создать data point
   - привязать `bp-esg-datasheet-2024.xlsx`

## 11.2. Acceptance criteria

- custom metric создаётся без framework admin доступа;
- custom metric попадает в `shared_elements` как tenant metric;
- datasheet item виден в builder сразу после создания;
- для item существует assignment context;
- `bp-esg-datasheet-2024.xlsx` можно привязать к созданному data point;
- linked evidence drawer различает:
  - `Framework metric`
  - `Custom metric`

---

## 12. Этапы реализации

### Phase 1

- DB tables `custom_datasheets`, `custom_datasheet_items`
- backend CRUD datasheet
- backend add-item flows
- create custom metric flow

### Phase 2

- UI tab `Project Settings -> Custom Datasheet`
- datasheet builder grouped by category
- add item dialogs

### Phase 3

- deep links:
  - `Open in collection`
  - `Open in assignments`
- datasheet metadata in evidence/data point preview

### Phase 4

- optional export layout for datasheet
- optional printable/client-facing sheet view

---

## 13. Итоговое архитектурное решение

Для `Custom Datasheet` в `v1` принимается следующая модель:

- `Datasheet` = project container
- `Datasheet item` = reference to metric + display metadata
- `Category` = обязательный pillar/topic layer
- `Display group` = optional label
- `Custom metric` = tenant `shared_element`
- `Assignment/DataPoint/Evidence` = использовать существующий runtime без отдельной ветки

Это решение:

- даёт простой UX;
- не плодит лишнюю иерархию;
- поддерживает mixing framework + custom;
- естественно ложится на текущие `shared_elements`, `assignments`, `data_points`, `evidence`.
