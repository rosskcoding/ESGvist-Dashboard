# ТЗ: Интеграция модуля Company Structure & Boundary с экранами системы

**Модуль:** Boundary Integration Layer
**Версия:** 1.0
**Дата:** 2026-03-22
**Статус:** Согласован
**Зависимости:** TZ-CompanyStructure.md, ARCHITECTURE.md, TZ-ESGvist-v1.md

---

## 1. Общий принцип

Модуль Company Structure & Boundary **не живёт изолированно**. Он является **сквозным контекстом** для всей системы.

**Интеграционное правило:**

> Модуль Organizational Structure & Boundary Management должен быть встроен во все ключевые пользовательские контуры системы. Для каждого reporting project выбранный boundary и его snapshot должны определять:
> - набор сущностей, входящих в scope проекта;
> - набор данных, подлежащих сбору;
> - набор assignments;
> - логику completeness;
> - состав report output;
> - контекст review и audit.

**Boundary как глобальный контекст:**

- Структура компании определяет, **по каким сущностям** собираются данные;
- Boundary определяет, **какие сущности** входят в отчёт;
- Snapshot boundary фиксирует, **какой именно периметр** использовался в проекте;
- Все ключевые экраны должны уметь:
  - показывать boundary context;
  - фильтровать по entity scope;
  - объяснять inclusion / exclusion.

---

## 2. Интеграция по экранам

### 2.1. Project Setup / Project Settings

**UI:** `/settings/projects/:id`

#### Что добавляется

Новый блок **"Reporting Boundary"** в настройках проекта:

| Поле | Тип | Описание |
|------|-----|----------|
| Selected boundary | dropdown | Выбранный boundary (default / alternative) |
| Boundary type | badge | `financial_reporting_default` / `operational_control` / `equity_share` / `custom` |
| Snapshot status | status | `not_created` / `draft` / `locked` |
| Snapshot date | date | Дата последнего snapshot |
| Snapshot approved by | user | Кто утвердил snapshot |
| Entities in scope | number | Количество включённых сущностей |

#### Действия по ролям

| Действие | admin | esg_manager | collector | reviewer | auditor |
|----------|:---:|:---:|:---:|:---:|:---:|
| Выбрать boundary для проекта | ✅ | ✅ | ❌ | ❌ | ❌ |
| Переключить boundary | ✅ | ✅ | ❌ | ❌ | ❌ |
| Открыть preview differences | ✅ | ✅ | ❌ | ❌ | ❌ |
| Сохранить snapshot | ✅ | ✅ | ❌ | ❌ | ❌ |
| Заблокировать boundary (при review/publish) | ✅ | ✅ | ❌ | ❌ | ❌ |
| Видеть, какой boundary применён | ✅ | ✅ | ⚠️ текст | ✅ RO | ✅ RO |
| Открыть boundary details | ✅ | ✅ | ❌ | ✅ RO | ✅ RO |

**Для collector** отображается только текстовый контекст:

```
Вы работаете в boundary: Operational Control
Entities in scope: 6
```

Без доступа к полному редактору структуры.

#### Зачем

Project setup сразу определяет:

- scope отчётности;
- scope assignments;
- scope completeness;
- scope exports.

#### Связь с БД

Расширение `reporting_projects`:

```sql
ALTER TABLE reporting_projects
    ADD COLUMN boundary_definition_id  bigint REFERENCES boundary_definitions(id) ON DELETE SET NULL,
    ADD COLUMN boundary_snapshot_id    bigint REFERENCES boundary_snapshots(id) ON DELETE SET NULL;
```

---

### 2.2. Merge View

**UI:** `/merge`

Это **критическая интеграция**. Merge View сейчас показывает пересечения стандартов, reused элементы, delta-требования. Теперь он должен **ещё учитывать boundary scope**.

#### Boundary Scope Layer

Для каждого элемента Merge View должен показывать:

- по каким entity / facilities данные должны быть собраны;
- входит ли entity в текущий boundary;
- есть ли gap из-за того, что сущность вне периметра.

#### Что добавить в Merge View

**Новые колонки / фильтры:**

| Колонка / фильтр | Описание |
|-------------------|----------|
| Boundary | Используемый boundary проекта |
| Entities in scope | Количество entity, по которым ожидаются данные |
| Excluded entities | Количество entity вне boundary |
| Consolidation method | `full` / `proportional` / `equity_share` |

**Новые статусы requirement_item:**

| Статус | Описание |
|--------|----------|
| `missing_in_boundary` | Данные отсутствуют для entity внутри boundary |
| `excluded_by_boundary` | Entity не входит в boundary — данные не требуются |
| `partially_included` | Часть entity включена, часть нет |

#### Пример

Если Scope 1 total собирается по 8 заводам, а в boundary вошли только 6:

```
Scope 1 Total (GRI 305-1):
├── 6 entities included (boundary: Operational Control)
│   ├── Plant A: 320 tCO2e ✅ approved
│   ├── Plant B: 180 tCO2e ✅ approved
│   ├── Plant C: missing ⚠️
│   ├── Plant D: 95 tCO2e 📋 submitted
│   ├── Plant E: 410 tCO2e ✅ approved
│   └── Plant F: 150 tCO2e ✅ approved
├── 2 entities excluded
│   ├── Plant G: excluded_by_boundary
│   └── Plant H: excluded_by_boundary
└── Consolidation: full
```

#### Польза

Merge View отвечает не только на вопрос *«какие стандарты требуют этот элемент?»*, но и *«по какому организационному периметру он считается?»*

---

### 2.3. Data Collection / Collection Table / Wizard

**UI:** `/collection`, `/collection/wizard`

Интеграция **обязательна** — сборщик должен понимать контекст entity.

#### Что меняется для collector

Сборщик видит не просто метрику, а:

- **по какой entity / facility** он вводит данные;
- **входит ли** эта сущность в boundary проекта;
- используется ли **full / proportional** consolidation;
- **не исключена ли** сущность из проекта.

#### Что добавить в Collection Table

**Новые поля:**

| Поле | Описание |
|------|----------|
| Entity | Название юр. лица / актива |
| Facility / Business Unit | Операционный актив |
| Boundary status | `included` / `excluded` / `partial` |
| Consolidation mode | `full` / `proportional` / `equity_share` |

**Фильтры:**

- only in boundary;
- excluded by boundary;
- by entity;
- by facility;
- by country.

#### Что добавить в Data Entry Wizard

На шаге выбора контекста или в header карточки метрики:

```
Project boundary: Operational Control
Entity: Plant A
Included in scope: ✅ Yes
Consolidation: Full
```

**Если сущность исключена:**

- ввод блокируется; **или**
- allowed as reference only, но не входит в отчёт (с пометкой).

#### Зачем

Чтобы сборщик понимал:

- почему именно по этой сущности у него задача;
- почему по другой сущности задачи нет;
- почему сумма не совпадает с «полной группой».

---

### 2.4. Assignments Matrix

**UI:** `/settings/assignments`

#### Расширение модели assignment

С введением boundary assignment становится:

```
assignment = shared_element + entity/facility + project
```

Вместо прежнего:

```
assignment = shared_element + project
```

#### Изменения в БД

```sql
ALTER TABLE metric_assignments
    ADD COLUMN entity_id   bigint REFERENCES company_entities(id) ON DELETE SET NULL,
    ADD COLUMN facility_id bigint REFERENCES company_entities(id) ON DELETE SET NULL;
```

#### Что добавить в матрицу назначений

| Колонка | Описание |
|---------|----------|
| Entity | Юридическое лицо |
| Facility | Производственный объект |
| Boundary included | Входит ли entity в boundary |
| Consolidation method | Метод консолидации |

#### Новая логика при смене boundary

При нажатии **"Apply Boundary"** система показывает impact preview:

```
Boundary change impact:
├── 12 assignments removed (entities excluded from new boundary)
├── 8 new assignments created (entities added to new boundary)
└── 4 assignments require reassignment (consolidation method changed)
```

ESG Manager обязан подтвердить перед применением.

#### API расширение

```
POST /api/projects/:id/boundary/assignments-preview
```

Response:

```json
{
  "removedAssignments": [
    { "assignmentId": 101, "entityName": "Plant G", "sharedElementCode": "GHG_SCOPE_1_TOTAL" }
  ],
  "newAssignments": [
    { "entityName": "Facility X", "sharedElementCode": "GHG_SCOPE_1_TOTAL", "suggestedCollector": null }
  ],
  "changedAssignments": [
    { "assignmentId": 105, "entityName": "JV Beta", "oldConsolidation": "full", "newConsolidation": "proportional" }
  ]
}
```

---

### 2.5. Review / Validation

**UI:** `/validation`

#### Что добавить в split panel (правая панель)

| Поле | Описание |
|------|----------|
| Entity | Юридическое лицо / актив, по которому собраны данные |
| Facility | Производственный объект |
| Boundary used | Boundary проекта |
| Inclusion reason | Почему entity включена (automatic / manual / override) |
| Consolidation method | `full` / `proportional` / `equity_share` |
| Snapshot version | ID и дата snapshot |

#### Новые review reason codes

| Code | Описание |
|------|----------|
| `OUT_OF_BOUNDARY_SCOPE` | Данные собраны по entity, не входящей в boundary проекта |
| `WRONG_CONSOLIDATION_CONTEXT` | Данные собраны с неверным методом консолидации |

#### Сценарий

Ревьюер может отклонить значение **не потому, что оно неверное**, а потому что:

- *«Сущность не входит в boundary»*
- *«Для этого проекта нужна operational control boundary, а вы загрузили данные по financial perimeter»*

При reject с reason = `OUT_OF_BOUNDARY_SCOPE`:

```json
{
  "action": "reject",
  "comment": "Data submitted for Plant G which is excluded from project boundary (Operational Control).",
  "reasonCode": "OUT_OF_BOUNDARY_SCOPE"
}
```

---

### 2.6. Overview Dashboard / ESG Manager Dashboard

**UI:** `/dashboard`

#### Новый блок: Boundary Summary

```
Boundary Summary
├── Selected: Operational Control
├── Entities in scope: 6
├── Excluded entities: 2
├── Manual overrides: 1
├── Snapshot: locked (2026-03-20)
└── Last updated by: Иванов А.Б.
```

#### Новый блок: Boundary Impact on Completeness

| Метрика | Значение |
|---------|----------|
| Missing due to excluded entities | 0 |
| Metrics affected by boundary change | 4 |
| Entities without assigned owners inside boundary | 1 |

#### Drill-down

Из dashboard ESG manager должен перейти к:

- boundary preview;
- excluded entities;
- assignments affected by boundary;
- entities without owners.

---

### 2.7. Completeness / Coverage экран

**UI:** `/completeness`

Completeness **считается только внутри boundary**.

#### Что добавить в summary

| Поле | Описание |
|------|----------|
| Completeness calculated for | Boundary name |
| Snapshot date | Дата snapshot |
| Included entities | Количество entity в scope |

#### Что добавить в detail

Для каждого disclosure / metric:

| Поле | Описание |
|------|----------|
| Covered entities | Entity с submitted / approved данными |
| Missing entities in scope | Entity в boundary без данных |
| Excluded entities out of scope | Entity вне boundary (информативно) |

#### Новый тип объяснения

**Было:**

```
Disclosure incomplete
```

**Стало:**

```
Disclosure incomplete: 2 included facilities (Plant C, Plant D)
have no submitted data within boundary "Operational Control"
```

#### Расширение Completeness Engine

```python
# app/services/completeness_service.py (расширение)

async def calculate_item_status_with_boundary(
    self,
    project_id: int,
    requirement_item_id: int,
    boundary_snapshot: BoundarySnapshot,
) -> str:  # 'missing' | 'partial' | 'complete' | 'not_applicable'

    # 1. Get entities in boundary scope
    entities_in_scope = [
        m.entity_id for m in boundary_snapshot.memberships if m.included
    ]

    # 2. Find bindings filtered by entity scope
    bindings = await self.binding_repo.find_by_project_item_entities(
        project_id, requirement_item_id, entities_in_scope
    )

    if not bindings:
        return "missing"

    # 3. Check if all entities in scope have data
    covered_entity_ids = {b.data_point.entity_id for b in bindings}
    required_entity_ids = await self._get_required_entities(
        requirement_item_id, entities_in_scope
    )

    if any(eid not in covered_entity_ids for eid in required_entity_ids):
        return "partial"  # some entities in scope have no data

    # 4. Continue with standard approval/dimension/evidence checks...
    # (existing logic from ARCHITECTURE.md section 3.7)

    return "complete"
```

---

### 2.8. Report / Export экран

**UI:** `/report`

#### Что добавить в readiness check

Новый блок **"Boundary Validation":**

| Проверка | Статус |
|----------|--------|
| Selected boundary | Operational Control |
| Snapshot locked | ✅ Yes |
| Entities in scope | 6 |
| Manual overrides | 1 |
| Unresolved structure issues | 0 |

**Blocking rules:**

- Snapshot не создан → **блокирует** publish (`BOUNDARY_SNAPSHOT_REQUIRED`, 422)
- Есть entities в scope без данных → **warning** (не блокирует, но отображается)
- Boundary отличается от financial_reporting_default → **warning** (информативно)

#### В export metadata

Каждый экспорт (PDF, Excel, GRI Content Index) включает:

| Поле | Значение |
|------|----------|
| Boundary type | Operational Control |
| Snapshot ID | snap_42 |
| Snapshot date | 2026-03-20 |
| Entities in scope | 6 (Plant A, Plant B, ...) |
| Exclusions | 2 (Plant G, Plant H) |
| Consolidation logic | Full consolidation for all included entities |

#### Воспроизводимость

Отчёт должен быть **воспроизводим**:

- почему именно эти entities вошли;
- какой метод консолидации использовался;
- какая версия boundary была актуальна на момент публикации.

---

### 2.9. Audit Log / Notifications

#### Audit Log — новые записи

| Действие | entity_type | Описание |
|----------|------------|----------|
| Create entity | CompanyEntity | Создание юр. лица / актива |
| Update ownership | OwnershipLink | Изменение доли владения |
| Update control | ControlLink | Изменение типа контроля |
| Create boundary | BoundaryDefinition | Создание boundary |
| Apply boundary to project | ReportingProject | Применение boundary к проекту |
| Save snapshot | BoundarySnapshot | Сохранение snapshot |
| Manual include/exclude | BoundaryMembership | Ручное переключение включения entity |
| Boundary recalculated | BoundaryDefinition | Автоматический пересчёт membership |

#### Notifications — новые триггеры

| Событие | Получатель | Канал |
|---------|-----------|-------|
| Boundary changed for project | ESG Manager, Reviewers | in-app + email |
| Snapshot created | ESG Manager | in-app |
| Assignments changed because of boundary | Affected collectors | in-app + email |
| Completeness recalculated due to boundary change | ESG Manager | in-app |
| Entity added to / removed from boundary | ESG Manager | in-app |

---

### 2.10. Evidence / Data Provenance

#### Интеграция

Evidence и data points должны быть привязаны к:

- **entity** (юридическое лицо / актив);
- **facility** (производственный объект);
- **boundary context** проекта.

#### Зачем

Чтобы можно было доказать:

> *«Этот файл (emissions_report_2025.pdf) подтверждает данные именно по entity Plant A, которая входит в boundary Operational Control проекта ESG Report 2025»*

#### Расширение data_points

```sql
ALTER TABLE data_points
    ADD COLUMN entity_id   bigint REFERENCES company_entities(id) ON DELETE SET NULL,
    ADD COLUMN facility_id bigint REFERENCES company_entities(id) ON DELETE SET NULL;
```

#### Расширение evidence привязки

В `data_point_evidences` контекст entity уже derivable через `data_points.entity_id`. Дополнительных изменений в схеме evidence не требуется — достаточно, чтобы data point имел entity context.

---

## 3. Изменения в модели данных

### 3.1. Расширение metric_assignments

```sql
ALTER TABLE metric_assignments
    ADD COLUMN entity_id   bigint REFERENCES company_entities(id) ON DELETE SET NULL,
    ADD COLUMN facility_id bigint REFERENCES company_entities(id) ON DELETE SET NULL;
```

**Новая логика assignment:**

```
assignment = shared_element + entity + facility + project
```

**Unique constraint:**

```sql
ALTER TABLE metric_assignments
    ADD CONSTRAINT uq_assignment_scope
    UNIQUE (reporting_project_id, shared_element_id, entity_id);
```

### 3.2. Расширение data_points

```sql
ALTER TABLE data_points
    ADD COLUMN entity_id   bigint REFERENCES company_entities(id) ON DELETE SET NULL,
    ADD COLUMN facility_id bigint REFERENCES company_entities(id) ON DELETE SET NULL;
```

### 3.3. Расширение reporting_projects

```sql
ALTER TABLE reporting_projects
    ADD COLUMN boundary_definition_id  bigint REFERENCES boundary_definitions(id) ON DELETE SET NULL,
    ADD COLUMN boundary_snapshot_id    bigint REFERENCES boundary_snapshots(id) ON DELETE SET NULL;
```

### 3.4. Расширение Identity Rule для reuse

С введением entity scope Identity Rule (TZ-ESGvist-v1, раздел Data Service) расширяется:

```python
@dataclass
class IdentityKey:
    shared_element_id: int
    organization_id: int
    reporting_period_id: int
    unit_code: str
    boundary_id: int | None
    methodology_id: int | None
    entity_id: int | None          # NEW
    facility_id: int | None        # NEW
    dimensions: dict[str, str]
```

**Правило:**

- Если `entity_id` совпадает → reuse возможен;
- Если `entity_id` отличается → создаётся новый DataPoint (разные юр. лица = разные данные).

### 3.5. Новые индексы

```sql
create index idx_metric_assignments_entity on metric_assignments(entity_id);
create index idx_metric_assignments_facility on metric_assignments(facility_id);
create index idx_data_points_entity on data_points(entity_id);
create index idx_data_points_facility on data_points(facility_id);
create index idx_reporting_projects_boundary on reporting_projects(boundary_definition_id);
```

---

## 4. Новые UI-паттерны

### 4.1. Boundary Badge

Показывается на всех экранах, где есть контекст проекта:

| Badge | Вид | Когда |
|-------|-----|-------|
| `Financial Default` | Серый badge | Стандартный boundary |
| `Operational Control` | Синий badge | Альтернативный boundary |
| `Custom Boundary` | Фиолетовый badge | Пользовательский |
| `Equity Share` | Зелёный badge | По доле участия |

### 4.2. Inclusion Badge

Показывается рядом с entity в таблицах и деревьях:

| Badge | Вид | Описание |
|-------|-----|----------|
| `Included` | ✅ зелёный | Entity в boundary |
| `Excluded` | ⬜ серый | Entity вне boundary |
| `Partial` | 🟡 жёлтый | Частично включена (proportional) |
| `Override` | 🔵 синий | Ручное переключение |

### 4.3. Impact Preview Modal

При смене boundary показывается модальное окно:

```
Boundary Change Impact
━━━━━━━━━━━━━━━━━━━━━
From: Financial Reporting Default
To:   Operational Control

Entities:
├── Added: 2 (JV Alpha, Facility X)
├── Removed: 1 (Associate Beta)
└── Changed consolidation: 1 (JV Gamma: full → proportional)

Assignments:
├── New: 8 (require collector assignment)
├── Removed: 4 (will be deactivated)
└── Changed: 2 (consolidation method updated)

Completeness:
├── Disclosures affected: 12
└── Estimated coverage change: 72% → 68%

[Cancel]  [Apply Boundary]
```

---

## 5. Новые Events (расширение Event-Driven Layer)

```python
# app/events/types.py (расширение)

@dataclass
class BoundaryAppliedToProject(DomainEvent):
    project_id: int = 0
    boundary_id: int = 0
    previous_boundary_id: int | None = None

@dataclass
class BoundarySnapshotLocked(DomainEvent):
    project_id: int = 0
    snapshot_id: int = 0

@dataclass
class AssignmentsAffectedByBoundary(DomainEvent):
    project_id: int = 0
    added: int = 0
    removed: int = 0
    changed: int = 0

@dataclass
class CompletenessRecalculatedForBoundary(DomainEvent):
    project_id: int = 0
    boundary_id: int = 0

@dataclass
class EntityExcludedFromProject(DomainEvent):
    project_id: int = 0
    entity_id: int = 0
    reason: str = ""

@dataclass
class DataPointOutOfBoundary(DomainEvent):
    data_point_id: int = 0
    entity_id: int = 0
    project_id: int = 0
```

**Trigger chains:**

```
BoundaryAppliedToProject
  ├── → Recalculate assignments (add/remove/change)
  │     └── → AssignmentsAffectedByBoundary
  │           └── → Notify affected collectors
  ├── → Completeness Engine full recalculate with entity scope
  │     └── → CompletenessRecalculatedForBoundary
  │           └── → Notify ESG Manager
  └── → Audit log entry

BoundarySnapshotLocked
  ├── → Audit log entry
  └── → Notify ESG Manager
```

---

## 6. Новые Error Codes (расширение ERROR-MODEL.md)

| Code | HTTP | Описание |
|------|------|----------|
| `BOUNDARY_SNAPSHOT_REQUIRED` | 422 | Невозможно опубликовать проект без locked boundary snapshot |
| `OUT_OF_BOUNDARY_SCOPE` | 422 | Данные собраны по entity, не входящей в boundary проекта |
| `WRONG_CONSOLIDATION_CONTEXT` | 422 | Данные собраны с неверным методом консолидации |
| `BOUNDARY_LOCKED_FOR_PROJECT` | 422 | Boundary заблокирован (проект в review/published) |
| `ENTITY_NOT_IN_BOUNDARY` | 422 | Entity не входит в boundary — действие невозможно |
| `ASSIGNMENT_ENTITY_MISMATCH` | 422 | Assignment создаётся для entity вне boundary |

---

## 7. Новые API Endpoints (расширение)

### 7.1. Assignments preview при смене boundary

```
POST /api/projects/:id/boundary/assignments-preview
```

**Response:**

```json
{
  "removedAssignments": [
    {
      "assignmentId": 101,
      "entityName": "Plant G",
      "sharedElementCode": "GHG_SCOPE_1_TOTAL",
      "collectorName": "Иванов А.Б."
    }
  ],
  "newAssignments": [
    {
      "entityName": "Facility X",
      "sharedElementCode": "GHG_SCOPE_1_TOTAL",
      "suggestedCollector": null,
      "suggestedReviewer": null
    }
  ],
  "changedAssignments": [
    {
      "assignmentId": 105,
      "entityName": "JV Beta",
      "oldConsolidation": "full",
      "newConsolidation": "proportional"
    }
  ]
}
```

### 7.2. Completeness с boundary context

```
GET /api/projects/:id/completeness?boundaryContext=true
```

**Response расширяется:**

```json
{
  "overall": {
    "completionPercent": 72,
    "boundaryName": "Operational Control",
    "entitiesInScope": 6,
    "snapshotDate": "2026-03-20T00:00:00Z"
  },
  "disclosures": [
    {
      "disclosureCode": "GRI 305-1",
      "status": "partial",
      "completionPercent": 67,
      "entityBreakdown": {
        "coveredEntities": 4,
        "missingEntities": 2,
        "excludedEntities": 2,
        "missingEntityNames": ["Plant C", "Plant D"]
      }
    }
  ]
}
```

### 7.3. Readiness check с boundary validation

```
GET /api/projects/:id/export/readiness
```

**Response расширяется блоком `boundaryValidation`:**

```json
{
  "overallReady": false,
  "completionPercent": 72,
  "blockingIssues": [...],
  "warnings": [...],
  "boundaryValidation": {
    "selectedBoundary": "Operational Control",
    "snapshotLocked": true,
    "entitiesInScope": 6,
    "manualOverrides": 1,
    "unresolvedStructureIssues": 0,
    "boundaryDiffersFromDefault": true,
    "entitiesWithoutData": ["Plant C", "Plant D"]
  }
}
```

---

## 8. Endpoint Permission Matrix (расширение)

| Endpoint | admin | esg_manager | collector | reviewer | auditor |
|----------|:---:|:---:|:---:|:---:|:---:|
| `POST /projects/:id/boundary/assignments-preview` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `GET /projects/:id/completeness?boundaryContext` | ✅ | ✅ | ⚠️ own scope | ⚠️ assigned | ✅ RO |

---

## 9. Связь с существующими документами

### 9.1. Изменения в ARCHITECTURE.md

**Раздел 3.4 (Data Service) — расширение Identity Rule:**

Добавить `entity_id` и `facility_id` в Identity Key.

**Раздел 3.7 (Completeness Engine) — boundary-aware calculation:**

Добавить `calculateItemStatusWithBoundary` (см. раздел 2.7 этого документа).

**Раздел 3.5 (Workflow Service) — boundary validation:**

При `submit` проверять, что `data_point.entity_id` входит в boundary проекта.

### 9.2. Изменения в TZ-ESGvist-v1.md

**Раздел 3 (PostgreSQL-схема):**

Добавить таблицы из TZ-CompanyStructure.md (company_entities, ownership_links, control_links, boundary_definitions, boundary_memberships, boundary_snapshots).

Добавить ALTER TABLE для metric_assignments, data_points, reporting_projects.

### 9.3. Изменения в TZ-ESGManager.md

**Раздел 3.1 (Управление проектом):**

Добавить шаг выбора boundary при создании проекта.

**Раздел 3.3 (Мониторинг прогресса):**

Добавить Boundary Summary и Boundary Impact on Completeness.

**Раздел 3.7 (Экспорт и публикация):**

Добавить Boundary Validation в readiness check.

### 9.4. Изменения в TZ-Reviewer.md

**Раздел 3.2 (Review UI):**

Добавить boundary context в правую панель split view.

**Раздел 3.3 (Действия ревьюера):**

Добавить reason codes: `OUT_OF_BOUNDARY_SCOPE`, `WRONG_CONSOLIDATION_CONTEXT`.

### 9.5. Изменения в TZ-User.md

**Раздел 3.3 (Ввод данных):**

Добавить entity / facility context в Data Entry Wizard.

**Раздел 3.4 (Reuse):**

Расширить Identity Rule полями entity_id, facility_id.

### 9.6. Изменения в TZ-Evidence.md

Data points получают entity context → evidence наследует entity привязку через data_point.

### 9.7. Изменения в ERROR-MODEL.md

Добавить 6 новых error codes (см. раздел 6 этого документа).

Добавить в Permission Matrix новые endpoints (см. раздел 8).

### 9.8. Изменения в SPRINT-PLAN.md

Рекомендуется добавить спринт(ы) для реализации модуля:

- **Sprint N** — Company Structure: entities, ownership, control (Backend + DB)
- **Sprint N+1** — Boundary: definitions, memberships, snapshot (Backend + DB)
- **Sprint N+2** — Boundary Integration: assignments, completeness, merge view (Backend)
- **Sprint N+3** — UI: Company Structure screen, boundary toolbar, integration into existing screens (Frontend)

### 9.9. Изменения в BACKLOG.md

Рекомендуется добавить:

- **EPIC-9: Company Structure & Boundary** (Phase 2)
  - Feature 9.1 — Company Entities Management
  - Feature 9.2 — Ownership & Control Links
  - Feature 9.3 — Boundary Definitions & Membership
  - Feature 9.4 — Boundary Snapshot & Project Integration
  - Feature 9.5 — Boundary Integration with Existing Screens

---

## 10. Критерии приёмки интеграции

- [ ] Project Setup показывает блок Reporting Boundary с selector и snapshot status
- [ ] Merge View показывает entity scope: included / excluded / consolidation method
- [ ] Collection Table фильтруется по entity / boundary
- [ ] Data Entry Wizard показывает entity context (name, inclusion, consolidation)
- [ ] Assignments Matrix включает entity / facility колонки
- [ ] При смене boundary показывается assignments impact preview
- [ ] Review split panel показывает boundary context (entity, inclusion reason, snapshot)
- [ ] Reviewer может reject с reason `OUT_OF_BOUNDARY_SCOPE`
- [ ] Dashboard показывает Boundary Summary и Boundary Impact on Completeness
- [ ] Completeness Engine считает только entity в scope boundary
- [ ] Completeness detail объясняет «какие entity в scope не имеют данных»
- [ ] Readiness check включает Boundary Validation блок
- [ ] Export metadata включает boundary type, snapshot date, entities in scope
- [ ] Audit log записывает все boundary-related действия
- [ ] Notifications отправляются при boundary change, snapshot creation, assignment changes
- [ ] data_points имеют entity_id / facility_id
- [ ] metric_assignments имеют entity_id / facility_id
- [ ] Identity Rule учитывает entity_id при reuse
- [ ] Collector видит текстовый boundary context без доступа к редактору
- [ ] Auditor видит snapshot read-only с полным boundary context
