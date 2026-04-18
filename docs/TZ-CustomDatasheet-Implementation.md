# Implementation Plan: Custom Datasheet

**Связанный документ:** [TZ-CustomDatasheet.md](./TZ-CustomDatasheet.md)  
**Версия:** 1.0  
**Статус:** Ready for execution  
**Дата:** 2026-04-17

---

## 1. Цель implementation plan

Этот документ переводит [TZ-CustomDatasheet.md](./TZ-CustomDatasheet.md) в последовательный план реализации:

- какие миграции нужны первыми;
- какие backend-компоненты менять;
- какие frontend-экраны добавлять;
- как внедрить `Custom Datasheet` без слома текущих `shared_elements`, `assignments`, `data_points`, `evidence`.

---

## 2. Принципы реализации

### 2.1. Не ломать текущий runtime

Новый модуль не должен:

- менять ownership `data_points`;
- менять ownership `evidence`;
- вводить новую параллельную коллекционную модель;
- дублировать `metric_assignments`.

### 2.2. Reuse вместо fork

Нужно переиспользовать уже существующие сущности:

- `shared_elements` — как metric definition
- `metric_assignments` — как project/context runtime binding
- `data_points` — как факт сбора данных
- `evidence` — как proof layer

### 2.3. Минимальный слой новых таблиц

Для `v1` добавляем только:

- `custom_datasheets`
- `custom_datasheet_items`

Не добавляем:

- `custom_datasheet_sections`
- `custom_datasheet_groups`
- `custom_metric_definitions`

### 2.4. Safe incremental rollout

Реализация разбивается на foundation-first этапы:

1. schema + backend foundation
2. read/write backend APIs
3. builder UI
4. create-custom UX
5. collection/deep-link polish

---

## 3. Deliverables

## 3.1. Backend

Новые deliverables:

- Alembic migration для `custom_datasheets`
- Alembic migration для `custom_datasheet_items`
- schemas
- repository/service layer
- routes
- tests

Расширения в существующих модулях:

- `project_service`
- `shared_element_repo/service`
- `evidence_service` только для derived context, если понадобится привязка datasheet metadata

## 3.2. Frontend

Новые deliverables:

- новый tab `Custom Datasheet` в `frontend/app/(app)/projects/[id]/settings/page.tsx`
- builder screen / panel
- dialogs:
  - `Create Datasheet`
  - `Add Item`
  - `Create New Custom Metric`

Расширения существующих экранов:

- `Collection` deep links
- `Evidence` drawer — optional datasheet badge later
- `Assignments` deep link target support

---

## 4. DB migrations

## 4.1. Migration 1 — `custom_datasheets`

### Таблица

```sql
create table custom_datasheets (
    id                   bigserial primary key,
    reporting_project_id bigint not null references reporting_projects(id) on delete cascade,
    name                 text not null,
    description          text,
    status               text not null default 'draft'
                         check (status in ('draft', 'active', 'archived')),
    created_by           bigint references users(id) on delete set null,
    created_at           timestamptz not null default now(),
    updated_at           timestamptz not null default now()
);

create index ix_custom_datasheets_project
    on custom_datasheets(reporting_project_id);
```

### Acceptance

- project может иметь 0..N datasheet
- delete project cascade удаляет datasheet
- статус datasheet ограничен перечислением

## 4.2. Migration 2 — `custom_datasheet_items`

### Таблица

```sql
create table custom_datasheet_items (
    id                   bigserial primary key,
    custom_datasheet_id  bigint not null references custom_datasheets(id) on delete cascade,
    reporting_project_id bigint not null references reporting_projects(id) on delete cascade,
    shared_element_id    bigint not null references shared_elements(id) on delete restrict,
    assignment_id        bigint references metric_assignments(id) on delete set null,
    source_type          text not null
                         check (source_type in ('framework', 'existing_custom', 'new_custom')),
    category             text not null
                         check (category in ('environmental', 'social', 'governance', 'business_operations', 'other')),
    display_group        text,
    label_override       text,
    help_text            text,
    collection_scope     text not null
                         check (collection_scope in ('project', 'entity', 'facility')),
    entity_id            bigint references company_entities(id) on delete set null,
    facility_id          bigint references company_entities(id) on delete set null,
    is_required          boolean not null default true,
    sort_order           integer not null default 0,
    status               text not null default 'active'
                         check (status in ('active', 'archived')),
    created_by           bigint references users(id) on delete set null,
    created_at           timestamptz not null default now(),
    updated_at           timestamptz not null default now()
);

create index ix_custom_datasheet_items_datasheet
    on custom_datasheet_items(custom_datasheet_id, category, sort_order);

create index ix_custom_datasheet_items_shared_element
    on custom_datasheet_items(shared_element_id);
```

### Дополнительные constraints

Рекомендуемые уникальности для `v1`:

```sql
create unique index uq_custom_datasheet_item_context
on custom_datasheet_items(
    custom_datasheet_id,
    shared_element_id,
    coalesce(entity_id, 0),
    coalesce(facility_id, 0),
    collection_scope
)
where status = 'active';
```

Это защитит от случайного двойного добавления одного и того же metric context в один datasheet.

## 4.3. Migration 3 — optional later

Не делать в первом PR, но зарезервировать как future migration:

- `default_category` для `shared_elements`
- `evidence_required` для `shared_elements` или отдельной tenant metric metadata таблицы
- `methodology_required`

Для `v1` эти поля можно хранить на `custom_datasheet_items` или в lightweight JSON metadata, если нужно быстро пойти в UI.

---

## 5. Backend model ownership

## 5.1. Existing ownership

| Сущность | Источник правды |
|----------|------------------|
| Metric definition | `shared_elements` |
| Project binding | `metric_assignments` |
| Actual value | `data_points` |
| Evidence | `evidences` + `data_point_evidences` |
| Datasheet membership | `custom_datasheet_items` |

## 5.2. Важное правило

`custom_datasheet_items` не должен стать новым runtime owner.

Он хранит:

- curated membership
- display metadata
- preferred collection scope/context
- optional link to assignment

Но не хранит:

- собранное значение
- статус review
- evidence ownership

---

## 6. Backend schemas

## 6.1. New schemas

Новый файл:

- `backend/app/schemas/custom_datasheets.py`

Основные модели:

- `CustomDatasheetCreate`
- `CustomDatasheetUpdate`
- `CustomDatasheetOut`
- `CustomDatasheetListOut`
- `CustomDatasheetItemCreate`
- `CustomDatasheetItemCreateCustomMetric`
- `CustomDatasheetItemUpdate`
- `CustomDatasheetItemOut`
- `CustomDatasheetDetailOut`
- `CustomDatasheetOptionSearchOut`

## 6.2. Enumerations

В schemas зафиксировать перечисления:

- `datasheet_status`: `draft | active | archived`
- `datasheet_item_status`: `active | archived`
- `source_type`: `framework | existing_custom | new_custom`
- `category`: `environmental | social | governance | business_operations | other`
- `collection_scope`: `project | entity | facility`
- `custom_value_type`: `number | text | boolean | date | enum | document`

---

## 7. Backend repository layer

Новые файлы:

- `backend/app/repositories/custom_datasheet_repo.py`

Responsibilities:

- create/list/get/update datasheets
- create/list/update/archive datasheet items
- lookup duplicate item contexts
- assignment linking helpers

### Repository methods

Минимальный набор:

- `create_datasheet(...)`
- `list_project_datasheets(project_id)`
- `get_datasheet_or_raise(datasheet_id, project_id)`
- `update_datasheet(...)`
- `create_datasheet_item(...)`
- `list_datasheet_items(datasheet_id)`
- `update_datasheet_item(...)`
- `archive_datasheet_item(...)`
- `find_item_duplicate(...)`

---

## 8. Backend service layer

Новый файл:

- `backend/app/services/custom_datasheet_service.py`

### 8.1. Responsibilities

- auth/policy checks
- project ownership checks
- item create orchestration
- assignment reuse/create logic
- create custom metric orchestration
- grouped builder response

### 8.2. Core service methods

- `list_project_datasheets(project_id, ctx)`
- `create_datasheet(project_id, payload, ctx)`
- `get_datasheet_detail(project_id, datasheet_id, ctx)`
- `update_datasheet(project_id, datasheet_id, payload, ctx)`
- `archive_datasheet(project_id, datasheet_id, ctx)`
- `search_add_item_options(project_id, q, source, category, attached_only, ctx)`
- `add_existing_metric_item(project_id, datasheet_id, payload, ctx)`
- `create_custom_metric_and_add_item(project_id, datasheet_id, payload, ctx)`
- `update_datasheet_item(project_id, datasheet_id, item_id, payload, ctx)`
- `delete_datasheet_item(project_id, datasheet_id, item_id, ctx)`

### 8.3. Assignment orchestration

Нужен helper внутри service:

- `_resolve_or_create_assignment(...)`

Логика:

1. найти existing assignment по:
   - `project_id`
   - `shared_element_id`
   - `entity_id`
   - `facility_id`
2. если найден → reuse
3. если нет и `create_if_missing=true` → создать через существующий assignment flow
4. вернуть `assignment_id`

### 8.4. Custom metric creation orchestration

Нужен helper:

- `_create_tenant_custom_metric(...)`

Он должен использовать уже существующий shared element pattern:

- `owner_layer = 'tenant_catalog'`
- `organization_id = project.organization_id`
- `is_custom = true`

И не плодить новую custom metric storage model.

---

## 9. API routes

Новый файл:

- `backend/app/api/routes/custom_datasheets.py`

Роуты:

- `GET /api/projects/{project_id}/custom-datasheets`
- `POST /api/projects/{project_id}/custom-datasheets`
- `GET /api/projects/{project_id}/custom-datasheets/{datasheet_id}`
- `PATCH /api/projects/{project_id}/custom-datasheets/{datasheet_id}`
- `POST /api/projects/{project_id}/custom-datasheets/{datasheet_id}/archive`
- `GET /api/projects/{project_id}/custom-datasheet-options`
- `POST /api/projects/{project_id}/custom-datasheets/{datasheet_id}/items`
- `POST /api/projects/{project_id}/custom-datasheets/{datasheet_id}/items/create-custom`
- `PATCH /api/projects/{project_id}/custom-datasheets/{datasheet_id}/items/{item_id}`
- `DELETE /api/projects/{project_id}/custom-datasheets/{datasheet_id}/items/{item_id}`

### Policy

Доступ:

- `admin`
- `esg_manager`
- `platform_admin` in support mode

Read-only deny:

- `collector`
- `reviewer`
- `auditor` for write actions

---

## 10. Search/add-item backend logic

## 10.1. Search source: framework

Источник:

- attached project standards preferred
- `shared_elements` + mapping + requirement context

Нужно вернуть:

- `shared_element_id`
- `shared_element_code`
- `shared_element_name`
- `owner_layer`
- `is_custom=false`
- `framework_context[]`
- `suggested_category`

## 10.2. Search source: existing custom

Источник:

- `shared_elements`
  - `owner_layer='tenant_catalog'`
  - `organization_id=current org`
  - `is_custom=true`

Нужно вернуть:

- `shared_element_id`
- `shared_element_code`
- `shared_element_name`
- `is_custom=true`
- optional usage counts across project/datasheets

## 10.3. Suggested category algorithm

Новый helper:

- `backend/app/services/custom_datasheet_category.py`

Method:

- `suggest_category(shared_element, framework_context) -> str`

Правила:

1. `concept_domain in ('emissions', 'energy', 'water', 'waste', 'biodiversity')` → `environmental`
2. `concept_domain in ('workforce', 'human_rights', 'community', 'health_safety')` → `social`
3. `concept_domain == 'governance'` → `governance`
4. если framework meta group = governance/social/environmental → использовать её
5. иначе `other`

---

## 11. Frontend implementation

## 11.1. Project Settings tab

Изменить:

- `frontend/app/(app)/projects/[id]/settings/page.tsx`

Добавить:

- новый tab value: `custom_datasheet`
- routing/state handling
- lazy query for datasheets

### UI deliverables

- datasheet list card
- empty state
- create datasheet CTA

## 11.2. Datasheet builder component

Новый компонент:

- `frontend/components/projects/custom-datasheet-builder.tsx`

Responsibilities:

- render current datasheet
- group by category
- subgroup by `display_group` if present
- show item chips and row actions

## 11.3. Create Datasheet dialog

Новый компонент:

- `frontend/components/projects/custom-datasheet-create-dialog.tsx`

Fields:

- name
- description
- status

## 11.4. Add Item dialog

Новый компонент:

- `frontend/components/projects/custom-datasheet-add-item-dialog.tsx`

States:

- source selector
- search mode
- add from result
- jump to create custom

## 11.5. Create New Custom Metric dialog

Новый компонент:

- `frontend/components/projects/custom-metric-create-dialog.tsx`

Fields:

- metric name
- metric code
- category
- display group
- description
- value type
- unit
- evidence required
- methodology required
- collection scope
- entity/facility selector

### UX notes

- code auto-generates from name until user edits it manually
- category is required
- display group optional
- if `collection_scope=project`, entity/facility selectors are hidden

## 11.6. Builder grouped display

Рендер order:

1. category order:
   - governance
   - environmental
   - social
   - business_operations
   - other
2. within category:
   - grouped by `display_group`
   - items without `display_group` go into a plain list block

For each item show:

- label override or metric name
- code
- badge: `Framework metric` / `Custom metric`
- assignment context
- actions:
  - `Open data point`
  - `Open assignment`
  - `Edit`
  - `Remove`

---

## 12. Integration with current screens

## 12.1. Collection

No new collection screen required.

Need only:

- deep link from datasheet item to existing collection page
- optional highlight param:
  - `/collection/{data_point_id}?projectId=...&fromDatasheet=...`

## 12.2. Assignments

Optional enhancement:

- link from datasheet item to assignments table prefiltered by `shared_element_id`

Can be phase 2 polish.

## 12.3. Evidence

No mandatory changes in phase 1.

Phase 2 optional:

- evidence drawer shows:
  - `Used in datasheet: BP ESG Datasheet`

Derived via:

- evidence -> data point -> assignment/shared_element -> datasheet item

---

## 13. Tests

## 13.1. Backend tests

New test file:

- `backend/tests/test_custom_datasheets.py`

Scenarios:

- create datasheet
- list datasheets by project
- add framework metric item
- add existing custom metric item
- create new custom metric item
- duplicate item context blocked
- assignment reused when exists
- assignment auto-created when missing
- remove item does not delete assignment/shared_element

## 13.2. Frontend tests

New Playwright file:

- `frontend/e2e/custom-datasheet.spec.ts`

Scenarios:

- create datasheet from project settings
- add framework metric to datasheet
- create custom metric in datasheet flow
- open created item in collection
- remove item from datasheet without deleting metric runtime

---

## 14. Safe rollout by PR / phase

## PR1 — Backend Foundation

Scope:

- migrations
- SQLAlchemy models
- schemas
- repository
- service skeleton
- basic CRUD datasheet endpoints

Acceptance:

- datasheet can be created/listed/read/updated
- no frontend yet required

## PR2 — Item Orchestration

Scope:

- search options endpoint
- add framework metric item
- add existing custom metric item
- assignment reuse/create logic
- backend tests

Acceptance:

- datasheet item can reference existing metric and assignment context

## PR3 — Create New Custom Metric

Scope:

- `create-custom` endpoint
- shared element custom creation through datasheet flow
- item + assignment orchestration
- backend tests

Acceptance:

- one request creates custom metric, assignment, datasheet item

## PR4 — Frontend Builder

Scope:

- project settings tab
- datasheet list
- create datasheet dialog
- builder grouped by category

Acceptance:

- user can create datasheet and inspect grouped items

## PR5 — Add Item UI

Scope:

- add-item dialog
- framework/custom search
- create new custom metric dialog
- success routing

Acceptance:

- user can complete the full `BP ESG Datasheet` pilot flow in UI

## PR6 — Polish / Deep Links

Scope:

- open in collection
- optional assignment filter links
- optional evidence/datasheet derived context
- e2e coverage

Acceptance:

- full end-to-end scenario stable

---

## 15. Execution order recommendation

Recommended build order:

1. PR1
2. PR2
3. PR3
4. Smoke-test backend with seeded live data
5. PR4
6. PR5
7. PR6

Reason:

- backend model must stabilize before UI wiring;
- custom metric creation path should be validated before builder UX depends on it;
- current repo already has live assignment/data point/evidence flows, so it is safer to plug datasheet into those than to prototype UI first.

---

## 16. Minimal MVP scope

Если нужно ещё сильнее упростить первый релиз, то MVP может быть:

- один datasheet на project
- no archive
- no item edit
- only:
  - create datasheet
  - add framework metric
  - create new custom metric
  - remove item
  - open in collection

Всё остальное можно оставить на phase 2.

---

## 17. Recommendation

Для текущего репо самый безопасный путь:

- начать с `PR1 + PR2`,
- затем сразу сделать `PR3`,
- после этого проверить на живой базе сценарий с `BP ESG Datasheet`,
- и только потом заходить во frontend builder.

Это позволит быстро подтвердить самую рискованную часть:

- custom metric definition
- assignment reuse/create
- compatibility with existing collection/evidence runtime

без лишнего frontend rework.
