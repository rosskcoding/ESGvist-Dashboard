# ТЗ: Модуль управления структурой компании и периметрами отчётности

**Модуль:** Company Structure & Boundary Manager
**Версия:** 1.0
**Дата:** 2026-03-22
**Статус:** Согласован

---

## 1. Цель

Обеспечить в системе функциональность для моделирования простой и сложной организационной структуры компании, включая:

- головную компанию;
- дочерние общества;
- совместные предприятия;
- ассоциированные компании;
- объекты с прямым и косвенным владением;
- разные типы контроля и владения;
- разные boundary для ESG-отчётности.

Модуль должен позволять определять, какие сущности входят в периметр отчётности:

- по умолчанию — по периметру финансовой отчётности;
- альтернативно — по другим правилам boundary:
  - operational control;
  - financial control;
  - equity share;
  - custom reporting boundary.

---

## 2. Область применения

Модуль используется для:

- определения состава компаний и активов в группе;
- настройки структуры владения;
- расчёта прямого и косвенного участия;
- определения boundary для ESG-отчётности;
- выбора сущностей, включаемых в конкретный reporting project;
- корректного распределения и агрегации data points;
- объяснимости расчётов coverage и completeness.

---

## 3. Основные принципы

### 3.1. Организационная структура должна моделироваться отдельно от reporting boundary

Структура группы и boundary не должны быть одной и той же сущностью.

### 3.2. Одна и та же структура может использоваться для разных boundary

Например:

- financial reporting boundary;
- operational control boundary;
- climate boundary;
- water boundary;
- custom project boundary.

### 3.3. Boundary должен быть переопределяемым на уровне проекта

Для каждого проекта отчётности должна быть возможность использовать:

- boundary по умолчанию;
- альтернативный boundary;
- комбинацию boundary по темам.

### 3.4. Должна поддерживаться сложная ownership chain

Система должна уметь хранить:

- прямое владение;
- косвенное владение;
- дробные доли;
- перекрёстное владение в допустимых пределах;
- effective ownership.

### 3.5. Финансовый периметр — default, но не единственный

Система должна по умолчанию предлагать boundary:

- `financial_reporting_default`

Но пользователь должен иметь возможность выбрать другой boundary.

---

## 4. Основные сущности

Модуль должен поддерживать следующие сущности:

| Сущность | Описание |
|----------|----------|
| **Organization / Group** | Корневая организация (группа компаний) |
| **Legal Entity** | Юридическое лицо в структуре группы |
| **Operational Entity / Asset / Facility** | Операционный актив, объект, площадка |
| **Ownership Link** | Связь владения между сущностями |
| **Control Link** | Связь контроля между сущностями |
| **Boundary Definition** | Определение boundary (правила включения) |
| **Boundary Membership** | Членство сущности в boundary |
| **Reporting Project Boundary Snapshot** | Иммутабельный снимок boundary для проекта |

---

## 5. Функциональные требования

### 5.1. Управление сущностями группы

Система должна позволять создавать и редактировать сущности следующих типов:

| Тип | Описание |
|-----|----------|
| `parent_company` | Головная компания |
| `legal_entity` | Юридическое лицо |
| `branch` | Филиал |
| `joint_venture` | Совместное предприятие |
| `associate` | Ассоциированная компания |
| `facility` | Производственный объект / операционный актив |
| `business_unit` | Бизнес-юнит |

Для каждой сущности должны задаваться:

- наименование;
- код / internal id;
- страна;
- юрисдикция;
- тип сущности;
- статус: `active` / `inactive` / `disposed`;
- дата начала / окончания владения или участия.

**Связь с БД:** `company_entities`

### 5.2. Управление связями владения

Система должна позволять создавать связи владения между сущностями.

Для каждой связи должны задаваться:

- parent entity;
- child entity;
- ownership percentage (0–100%);
- ownership type: `direct` / `indirect` / `beneficial`;
- valid from / valid to;
- комментарий.

**Правила:**

- несколько владельцев у одной сущности;
- дробное владение (например, 33.33%);
- совместное владение;
- историчность связей (valid_from / valid_to).

**Связь с БД:** `ownership_links`

### 5.3. Управление связями контроля

Система должна позволять задавать отдельно от ownership связи контроля.

Для каждой связи контроля должны задаваться:

- controlling entity;
- controlled entity;
- control type: `financial_control` / `operational_control` / `management_control` / `significant_influence`;
- is_controlled: true/false;
- valid from / valid to;
- комментарий / обоснование.

**Связь с БД:** `control_links`

### 5.4. Автоматический расчёт effective ownership

Система должна уметь рассчитывать:

- direct ownership — прямая доля;
- indirect ownership — через промежуточные сущности;
- effective ownership — агрегированная доля через всю цепочку;
- aggregated ownership through chain.

**Алгоритм:**

```
effective_ownership(A → C) =
  direct_ownership(A → C) +
  Σ (ownership(A → B_i) × effective_ownership(B_i → C))
  для всех промежуточных B_i
```

**Правила:**

- Алгоритм обходит граф владения (DFS/BFS);
- Циклы обнаруживаются и блокируются с ошибкой `OWNERSHIP_CYCLE_DETECTED`;
- Результат кэшируется и пересчитывается при изменении ownership links;
- Результат должен быть виден пользователю в UI рядом с каждой сущностью.

**Связь с БД:** расчётное поле `effective_ownership_percent` в `company_entities` (или materialized view)

### 5.5. Определение boundary

Система должна позволять создавать boundary definitions следующих типов:

| Тип | Описание | Правило включения по умолчанию |
|-----|----------|-------------------------------|
| `financial_reporting_default` | Периметр финансовой отчётности | Все сущности с financial control |
| `financial_control` | По финансовому контролю | `control_type = financial_control AND is_controlled = true` |
| `operational_control` | По операционному контролю | `control_type = operational_control AND is_controlled = true` |
| `equity_share` | По доле участия | `effective_ownership >= threshold` |
| `custom` | Пользовательский | Задаётся вручную |

Для каждого boundary должны задаваться:

- название;
- тип;
- описание;
- правило inclusion (JSON);
- правило consolidation (JSON);
- default flag (`is_default`).

**Связь с БД:** `boundary_definitions`

### 5.6. Boundary membership

Система должна позволять определять, какие сущности входят в boundary.

**Поддерживаемые режимы:**

| Режим | Описание |
|-------|----------|
| **Автоматический** | На основе правил: financial control, operational control, ownership threshold, equity share |
| **Ручной** | Пользователь вручную включает / исключает сущности |
| **Гибридный** | Система предлагает состав автоматически, пользователь корректирует вручную |

Для каждого membership записывается:

- entity_id;
- included: true/false;
- inclusion_reason (текст);
- inclusion_source: `automatic` / `manual` / `override`;
- consolidation_method: `full` / `proportional` / `equity_share`.

**Связь с БД:** `boundary_memberships`

### 5.7. Boundary rules

Система должна поддерживать следующие правила включения:

| Правило | Описание |
|---------|----------|
| `include_if_financially_controlled` | Включить, если `financial_control = true` |
| `include_if_operationally_controlled` | Включить, если `operational_control = true` |
| `include_if_ownership_gte_threshold` | Включить, если `effective_ownership >= threshold` |
| `include_proportionally_by_equity` | Включить пропорционально доле |
| `include_manually` | Включить вручную |
| `exclude_manually` | Исключить вручную |

**Правила хранятся в JSON:**

```json
{
  "rules": [
    {
      "type": "include_if_financially_controlled",
      "consolidation": "full"
    },
    {
      "type": "include_if_ownership_gte_threshold",
      "threshold": 50,
      "consolidation": "proportional"
    }
  ],
  "defaultExclude": true
}
```

### 5.8. Snapshot boundary для проекта

Для каждого reporting project система должна сохранять snapshot boundary на дату проекта.

**Зачем:**

- последующие изменения структуры группы не ломают прошлую отчётность;
- сохраняется воспроизводимость расчётов;
- аудитор может проверить, какой boundary был актуален на момент публикации.

**Snapshot включает:**

- копию boundary definition;
- копию boundary memberships;
- effective ownership на дату snapshot;
- дату создания и автора.

**Правила:**

- Snapshot иммутабелен после сохранения;
- Для `published` проектов snapshot **обязателен**;
- Изменение snapshot после публикации запрещено (только через откат проекта).

**Связь с БД:** `boundary_snapshots`, `boundary_snapshot_memberships`

### 5.9. Отображение структуры в UI

Система должна предоставлять экран, на котором пользователь может:

- видеть дерево группы компаний;
- видеть ownership links с процентами;
- видеть control links с типами;
- видеть доли владения (direct + effective);
- видеть, входит ли сущность в boundary;
- фильтровать по типу boundary;
- переключаться между boundary view.

**UI:** `/settings/company-structure`

### 5.10. Режимы отображения экрана

Экран должен поддерживать минимум 3 режима:

| Режим | Описание |
|-------|----------|
| **Structure View** | Организационная структура и связи владения |
| **Control View** | Контроль и тип контроля |
| **Boundary View** | Какие сущности входят в конкретный boundary |

### 5.11. Действия пользователя на экране

Пользователь с правами (admin / esg_manager) должен иметь возможность:

- создать сущность;
- создать связь владения;
- создать связь контроля;
- изменить долю владения;
- включить / исключить сущность из boundary;
- выбрать boundary по умолчанию;
- применить boundary к reporting project;
- сохранить snapshot.

### 5.12. Проверки и валидации

Система должна проверять:

| Проверка | Описание | Error Code |
|----------|----------|------------|
| Сумма ownership | Сумма ownership долей одной сущности не превышает 100% | `OWNERSHIP_EXCEEDS_100` |
| Циклы | Отсутствие недопустимых циклов в графе владения | `OWNERSHIP_CYCLE_DETECTED` |
| Даты | Корректность дат действия связей (valid_from < valid_to) | `INVALID_DATE_RANGE` |
| Parent company | Наличие parent company для групповой структуры | `PARENT_COMPANY_REQUIRED` |
| Default boundary | Наличие хотя бы одного default boundary | `DEFAULT_BOUNDARY_REQUIRED` |
| Boundary mismatch | Предупреждение, если boundary отличается от financial reporting default | Warning (не блокирует) |
| Self-ownership | Сущность не может владеть собой | `SELF_OWNERSHIP_NOT_ALLOWED` |
| Published snapshot | Нельзя менять snapshot опубликованного проекта | `SNAPSHOT_IMMUTABLE` |

### 5.13. Использование boundary в других модулях

Модуль должен интегрироваться с:

| Модуль | Интеграция |
|--------|-----------|
| **Data Collection** | Фильтрация data points по сущностям внутри boundary. Data points привязываются к entity_id |
| **Completeness Engine** | Оценка полноты только по entity scope текущего boundary. Requirement items, не относящиеся к сущностям за пределами boundary, помечаются `not_applicable` |
| **Merge / Reporting** | Формирование отчёта только по сущностям в выбранном boundary. Export включает boundary description |
| **Review / Audit** | Пояснение, почему конкретное значение вошло или не вошло в отчёт. Аудитор видит snapshot boundary |

---

## 6. Модель данных (PostgreSQL)

### 6.1. company_entities

```sql
create table company_entities (
    id                  bigserial primary key,
    organization_id     bigint not null references organizations(id) on delete cascade,
    parent_entity_id    bigint references company_entities(id) on delete set null,
    name                text not null,
    code                text,
    entity_type         text not null check (entity_type in (
                            'parent_company', 'legal_entity', 'branch',
                            'joint_venture', 'associate', 'facility', 'business_unit'
                        )),
    country             text,
    jurisdiction        text,
    status              text not null default 'active' check (status in ('active', 'inactive', 'disposed')),
    valid_from          date,
    valid_to            date,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now()
);
```

### 6.2. ownership_links

```sql
create table ownership_links (
    id                  bigserial primary key,
    parent_entity_id    bigint not null references company_entities(id) on delete cascade,
    child_entity_id     bigint not null references company_entities(id) on delete cascade,
    ownership_percent   numeric(7, 4) not null check (ownership_percent >= 0 and ownership_percent <= 100),
    ownership_type      text not null default 'direct' check (ownership_type in ('direct', 'indirect', 'beneficial')),
    valid_from          date,
    valid_to            date,
    comment             text,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now(),

    constraint chk_no_self_ownership check (parent_entity_id != child_entity_id)
);
```

### 6.3. control_links

```sql
create table control_links (
    id                      bigserial primary key,
    controlling_entity_id   bigint not null references company_entities(id) on delete cascade,
    controlled_entity_id    bigint not null references company_entities(id) on delete cascade,
    control_type            text not null check (control_type in (
                                'financial_control', 'operational_control',
                                'management_control', 'significant_influence'
                            )),
    is_controlled           boolean not null default true,
    valid_from              date,
    valid_to                date,
    rationale               text,
    created_at              timestamptz not null default now(),
    updated_at              timestamptz not null default now(),

    constraint chk_no_self_control check (controlling_entity_id != controlled_entity_id)
);
```

### 6.4. boundary_definitions

```sql
create table boundary_definitions (
    id                  bigserial primary key,
    organization_id     bigint not null references organizations(id) on delete cascade,
    name                text not null,
    boundary_type       text not null check (boundary_type in (
                            'financial_reporting_default', 'financial_control',
                            'operational_control', 'equity_share', 'custom'
                        )),
    description         text,
    inclusion_rules     jsonb,
    consolidation_rules jsonb,
    is_default          boolean not null default false,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now()
);
```

### 6.5. boundary_memberships

```sql
create table boundary_memberships (
    id                      bigserial primary key,
    boundary_definition_id  bigint not null references boundary_definitions(id) on delete cascade,
    entity_id               bigint not null references company_entities(id) on delete cascade,
    included                boolean not null default true,
    inclusion_reason        text,
    inclusion_source        text not null default 'automatic' check (inclusion_source in ('automatic', 'manual', 'override')),
    consolidation_method    text check (consolidation_method in ('full', 'proportional', 'equity_share')),
    created_at              timestamptz not null default now(),
    updated_at              timestamptz not null default now(),

    unique (boundary_definition_id, entity_id)
);
```

### 6.6. boundary_snapshots

```sql
create table boundary_snapshots (
    id                      bigserial primary key,
    reporting_project_id    bigint not null references reporting_projects(id) on delete cascade,
    boundary_definition_id  bigint not null references boundary_definitions(id) on delete restrict,
    snapshot_data           jsonb not null,
    created_by              bigint references users(id) on delete set null,
    created_at              timestamptz not null default now(),

    unique (reporting_project_id)
);
```

**`snapshot_data` JSON structure:**

```json
{
  "boundary": {
    "id": 1,
    "name": "Financial Reporting Default",
    "boundaryType": "financial_reporting_default",
    "inclusionRules": { ... },
    "consolidationRules": { ... }
  },
  "memberships": [
    {
      "entityId": 10,
      "entityName": "SubCo Alpha",
      "entityType": "legal_entity",
      "included": true,
      "inclusionSource": "automatic",
      "consolidationMethod": "full",
      "effectiveOwnership": 100.0
    },
    {
      "entityId": 11,
      "entityName": "JV Beta",
      "entityType": "joint_venture",
      "included": true,
      "inclusionSource": "manual",
      "consolidationMethod": "proportional",
      "effectiveOwnership": 50.0
    }
  ],
  "snapshotDate": "2026-03-22T00:00:00Z"
}
```

### 6.7. Индексы

```sql
create index idx_company_entities_org on company_entities(organization_id);
create index idx_company_entities_parent on company_entities(parent_entity_id);
create index idx_company_entities_type on company_entities(entity_type);
create index idx_company_entities_status on company_entities(status);

create index idx_ownership_links_parent on ownership_links(parent_entity_id);
create index idx_ownership_links_child on ownership_links(child_entity_id);

create index idx_control_links_controlling on control_links(controlling_entity_id);
create index idx_control_links_controlled on control_links(controlled_entity_id);

create index idx_boundary_definitions_org on boundary_definitions(organization_id);
create index idx_boundary_definitions_default on boundary_definitions(organization_id, is_default) where is_default = true;

create index idx_boundary_memberships_boundary on boundary_memberships(boundary_definition_id);
create index idx_boundary_memberships_entity on boundary_memberships(entity_id);

create index idx_boundary_snapshots_project on boundary_snapshots(reporting_project_id);
```

---

## 7. Пользовательские роли

| Действие | admin | esg_manager | collector | reviewer | auditor |
|----------|:---:|:---:|:---:|:---:|:---:|
| Создание / редактирование сущностей | ✅ | ✅ | ❌ | ❌ | ❌ |
| Управление ownership links | ✅ | ✅ | ❌ | ❌ | ❌ |
| Управление control links | ✅ | ✅ | ❌ | ❌ | ❌ |
| Создание boundary definitions | ✅ | ❌ | ❌ | ❌ | ❌ |
| Редактирование boundary memberships | ✅ | ✅ | ❌ | ❌ | ❌ |
| Просмотр структуры | ✅ | ✅ | ⚠️ assigned | ⚠️ assigned | ✅ |
| Применение boundary к проекту | ✅ | ✅ | ❌ | ❌ | ❌ |
| Сохранение snapshot | ✅ | ✅ | ❌ | ❌ | ❌ |
| Просмотр snapshots | ✅ | ✅ | ❌ | ✅ RO | ✅ RO |

---

## 8. Пользовательские сценарии

### Сценарий 1. Простая структура

1. ESG manager создаёт parent company.
2. Добавляет 3 дочерние компании.
3. Указывает 100% ownership.
4. Система автоматически строит financial boundary.
5. Boundary применяется к проекту.

**Результат:** все 4 сущности включены в boundary с consolidation = full.

### Сценарий 2. Сложная структура с JV

1. ESG manager создаёт JV entity.
2. Указывает ownership 50%.
3. Указывает operational control = true.
4. В financial boundary JV может не входить полностью.
5. В operational control boundary JV входит.

**Результат:** JV включён в operational control boundary, но в financial — proportional (50%).

### Сценарий 3. Boundary override

1. Для проекта по climate reporting ESG manager выбирает не financial default, а operational control boundary.
2. Система показывает difference preview:
   - какие сущности добавятся;
   - какие исключатся;
   - какие изменят consolidation method.
3. ESG manager подтверждает.
4. Сохраняется snapshot.

**Результат:** проект использует operational control boundary, различия зафиксированы.

### Сценарий 4. Historical snapshot

1. После публикации проекта структура группы меняется (новое приобретение).
2. Старый project snapshot не меняется — данные воспроизводимы.
3. Новый project использует обновлённую структуру.

**Результат:** immutable snapshot сохраняет целостность прошлой отчётности.

---

## 9. Экран: Company Structure & Boundary Manager

### 9.1. Цель экрана

Дать ESG manager / admin визуальный инструмент для:

- моделирования структуры компании;
- работы со связями владения и контроля;
- настройки boundary;
- просмотра differences между boundary;
- сохранения boundary snapshot для проекта.

### 9.2. Основные зоны экрана

#### Левая панель — дерево структуры

Показывает:

- parent company (корень);
- subsidiaries;
- JV;
- facilities.

Содержит:

- поиск по названию / коду;
- фильтр по типу сущности;
- фильтр по статусу (active / inactive / disposed).

#### Центральная панель — визуализация

**Режимы:**

| Режим | Отображение |
|-------|------------|
| Structure | Узлы сущностей + ownership % + иерархия |
| Control | Узлы + control type + is_controlled |
| Boundary | Узлы + inclusion state (included / excluded) + consolidation method |

**Визуальные элементы:**

- Узлы сущностей (цвет по типу);
- Линии связей (ownership %, control type);
- Индикаторы boundary inclusion (зелёный = included, серый = excluded);
- Badge с effective ownership;
- Подсветка изменённых элементов при compare mode.

#### Правая панель — карточка выбранной сущности

Показывает:

- атрибуты сущности (name, code, type, country, status);
- ownership links (все входящие и исходящие);
- control links;
- boundary membership (в каких boundary включена);
- effective ownership;
- history изменений;
- comments / rationale.

#### Верхняя панель — boundary toolbar

Содержит:

- selector boundary (dropdown);
- selector reporting project (dropdown);
- compare mode toggle;
- кнопка "Apply boundary" — применить к проекту;
- кнопка "Save snapshot" — сохранить иммутабельный snapshot;
- кнопка "Difference preview" — показать добавленные / удалённые сущности.

### 9.3. Функции экрана

| Функция | Описание |
|---------|----------|
| Create entity | Создание сущности (модальная форма) |
| Edit entity | Редактирование атрибутов в правой панели |
| Link ownership | Создание связи владения (drag-and-drop или модальная форма) |
| Link control | Создание связи контроля |
| Include / exclude in boundary | Ручное включение / исключение сущности |
| Compare boundaries | Сравнение двух boundary side-by-side |
| Preview impact on project | Показ изменений при смене boundary для проекта |
| Save snapshot | Сохранение иммутабельного snapshot |
| Export structure map | Экспорт дерева структуры (PDF / PNG) |

---

## 10. API Endpoints

### 10.1. Company Entities

```
GET    /api/entities                          — список сущностей (с фильтрами: entityType, status, search)
POST   /api/entities                          — создать сущность
GET    /api/entities/:id                      — детали сущности
PATCH  /api/entities/:id                      — обновить сущность
GET    /api/entities/tree                     — дерево структуры (иерархическое)
GET    /api/entities/:id/effective-ownership  — расчёт effective ownership
```

### 10.2. Ownership Links

```
GET    /api/ownership-links                   — список связей владения (с фильтрами)
POST   /api/ownership-links                   — создать связь владения
PATCH  /api/ownership-links/:id               — обновить связь
DELETE /api/ownership-links/:id               — удалить связь
```

### 10.3. Control Links

```
GET    /api/control-links                     — список связей контроля
POST   /api/control-links                     — создать связь контроля
PATCH  /api/control-links/:id                 — обновить связь
DELETE /api/control-links/:id                 — удалить связь
```

### 10.4. Boundary Definitions

```
GET    /api/boundaries                        — список boundary definitions
POST   /api/boundaries                        — создать boundary definition
GET    /api/boundaries/:id                    — детали boundary
PATCH  /api/boundaries/:id                    — обновить boundary
```

### 10.5. Boundary Memberships

```
GET    /api/boundaries/:id/memberships        — список memberships для boundary
PUT    /api/boundaries/:id/memberships        — обновить memberships (replace overrides)
POST   /api/boundaries/:id/recalculate        — пересчитать automatic memberships
```

### 10.6. Project Boundary

```
GET    /api/projects/:id/boundary             — текущий boundary проекта
PUT    /api/projects/:id/boundary             — применить boundary к проекту
POST   /api/projects/:id/boundary/preview     — preview изменений при смене boundary
POST   /api/projects/:id/boundary/snapshot    — сохранить иммутабельный snapshot
GET    /api/projects/:id/boundary/snapshot    — получить snapshot
```

---

## 11. OpenAPI Schema Patch

### 11.1. Новые схемы

```yaml
components:
  schemas:
    EntityType:
      type: string
      enum:
        - parent_company
        - legal_entity
        - branch
        - joint_venture
        - associate
        - facility
        - business_unit

    EntityStatus:
      type: string
      enum: [active, inactive, disposed]

    CompanyEntity:
      type: object
      required: [id, name, entityType, status]
      properties:
        id:
          type: integer
          format: int64
        organizationId:
          type: integer
          format: int64
        parentEntityId:
          type: integer
          format: int64
          nullable: true
        name:
          type: string
        code:
          type: string
          nullable: true
        entityType:
          $ref: '#/components/schemas/EntityType'
        country:
          type: string
          nullable: true
        jurisdiction:
          type: string
          nullable: true
        status:
          $ref: '#/components/schemas/EntityStatus'
        validFrom:
          type: string
          format: date
          nullable: true
        validTo:
          type: string
          format: date
          nullable: true
        effectiveOwnership:
          type: number
          description: Calculated effective ownership percentage
          nullable: true
        createdAt:
          type: string
          format: date-time
        updatedAt:
          type: string
          format: date-time

    OwnershipLink:
      type: object
      required: [id, parentEntityId, childEntityId, ownershipPercent]
      properties:
        id:
          type: integer
          format: int64
        parentEntityId:
          type: integer
          format: int64
        childEntityId:
          type: integer
          format: int64
        ownershipPercent:
          type: number
          minimum: 0
          maximum: 100
        ownershipType:
          type: string
          enum: [direct, indirect, beneficial]
        validFrom:
          type: string
          format: date
          nullable: true
        validTo:
          type: string
          format: date
          nullable: true
        comment:
          type: string
          nullable: true

    ControlType:
      type: string
      enum:
        - financial_control
        - operational_control
        - management_control
        - significant_influence

    ControlLink:
      type: object
      required: [id, controllingEntityId, controlledEntityId, controlType, isControlled]
      properties:
        id:
          type: integer
          format: int64
        controllingEntityId:
          type: integer
          format: int64
        controlledEntityId:
          type: integer
          format: int64
        controlType:
          $ref: '#/components/schemas/ControlType'
        isControlled:
          type: boolean
        validFrom:
          type: string
          format: date
          nullable: true
        validTo:
          type: string
          format: date
          nullable: true
        rationale:
          type: string
          nullable: true

    BoundaryType:
      type: string
      enum:
        - financial_reporting_default
        - financial_control
        - operational_control
        - equity_share
        - custom

    BoundaryDefinition:
      type: object
      required: [id, name, boundaryType]
      properties:
        id:
          type: integer
          format: int64
        organizationId:
          type: integer
          format: int64
        name:
          type: string
        boundaryType:
          $ref: '#/components/schemas/BoundaryType'
        description:
          type: string
          nullable: true
        inclusionRules:
          type: object
          description: JSON rules for automatic membership calculation
        consolidationRules:
          type: object
          description: JSON rules for consolidation method assignment
        isDefault:
          type: boolean

    BoundaryMembership:
      type: object
      required: [entityId, included]
      properties:
        entityId:
          type: integer
          format: int64
        entityName:
          type: string
        entityType:
          $ref: '#/components/schemas/EntityType'
        included:
          type: boolean
        inclusionReason:
          type: string
          nullable: true
        inclusionSource:
          type: string
          enum: [automatic, manual, override]
          nullable: true
        consolidationMethod:
          type: string
          enum: [full, proportional, equity_share]
          nullable: true
        effectiveOwnership:
          type: number
          nullable: true

    BoundarySnapshot:
      type: object
      required: [id, reportingProjectId, boundaryId, createdAt]
      properties:
        id:
          type: integer
          format: int64
        reportingProjectId:
          type: integer
          format: int64
        boundaryId:
          type: integer
          format: int64
        snapshotData:
          type: object
          description: Immutable copy of boundary + memberships + effective ownership
        createdAt:
          type: string
          format: date-time
        createdBy:
          type: integer
          format: int64
          nullable: true

    BoundaryPreview:
      type: object
      properties:
        addedEntities:
          type: array
          items:
            $ref: '#/components/schemas/BoundaryMembership'
        removedEntities:
          type: array
          items:
            $ref: '#/components/schemas/BoundaryMembership'
        changedConsolidation:
          type: array
          items:
            type: object
            properties:
              entityId:
                type: integer
                format: int64
              entityName:
                type: string
              oldMethod:
                type: string
              newMethod:
                type: string

    CompanyEntityListResponse:
      type: object
      required: [items, meta]
      properties:
        items:
          type: array
          items:
            $ref: '#/components/schemas/CompanyEntity'
        meta:
          $ref: '#/components/schemas/ListMeta'
```

### 11.2. Endpoint Permission Matrix

| Endpoint | admin | esg_manager | collector | reviewer | auditor |
|----------|:---:|:---:|:---:|:---:|:---:|
| `GET /entities` | ✅ | ✅ | ⚠️ assigned | ⚠️ assigned | ✅ |
| `POST /entities` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `PATCH /entities/:id` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `GET /entities/tree` | ✅ | ✅ | ❌ | ✅ RO | ✅ RO |
| `POST /ownership-links` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `POST /control-links` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `GET /boundaries` | ✅ | ✅ | ❌ | ✅ RO | ✅ RO |
| `POST /boundaries` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `PATCH /boundaries/:id` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `GET /boundaries/:id/memberships` | ✅ | ✅ | ❌ | ✅ RO | ✅ RO |
| `PUT /boundaries/:id/memberships` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `PUT /projects/:id/boundary` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `POST /projects/:id/boundary/preview` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `POST /projects/:id/boundary/snapshot` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `GET /projects/:id/boundary/snapshot` | ✅ | ✅ | ❌ | ✅ RO | ✅ RO |

---

## 12. Бизнес-правила для API

### 12.1. Apply boundary to project

`PUT /projects/{projectId}/boundary`

- Если проект в статусе `published` → **запрещено** (`PROJECT_LOCKED`, 422)
- Если проект в статусе `review` → только `admin` / `esg_manager`
- Перед применением рекомендуется вызвать preview

### 12.2. Save snapshot

`POST /projects/{projectId}/boundary/snapshot`

- Создаёт **иммутабельный** snapshot
- Если snapshot уже существует и проект `published` → **запрещено** (`SNAPSHOT_IMMUTABLE`, 409)
- Если snapshot существует и проект не published → перезаписывается (с audit log)
- Snapshot обязателен перед переводом проекта в `published`

### 12.3. Preview

`POST /projects/{projectId}/boundary/preview`

- Возвращает:
  - `addedEntities` — сущности, которые будут добавлены;
  - `removedEntities` — сущности, которые будут удалены;
  - `changedConsolidation` — сущности с изменённым методом консолидации.
- Не вносит изменений, только расчёт

### 12.4. Ownership validation

`POST /ownership-links`

- `parent_entity_id != child_entity_id` → `SELF_OWNERSHIP_NOT_ALLOWED` (422)
- Сумма ownership долей child entity <= 100% → `OWNERSHIP_EXCEEDS_100` (422)
- Проверка на циклы → `OWNERSHIP_CYCLE_DETECTED` (422)
- `valid_from < valid_to` (если оба заданы) → `INVALID_DATE_RANGE` (400)

### 12.5. Control link validation

`POST /control-links`

- `controlling_entity_id != controlled_entity_id` → `SELF_CONTROL_NOT_ALLOWED` (422)
- Дубликат (controlling + controlled + control_type) → `CONTROL_LINK_EXISTS` (409)

---

## 13. Events (Event-Driven Layer)

```python
# app/events/types.py (расширение)

@dataclass
class EntityCreated(DomainEvent):
    entity_id: int = 0
    entity_type: str = ""

@dataclass
class EntityUpdated(DomainEvent):
    entity_id: int = 0
    changed_fields: list[str] = field(default_factory=list)

@dataclass
class EntityDisposed(DomainEvent):
    entity_id: int = 0

@dataclass
class OwnershipLinkCreated(DomainEvent):
    link_id: int = 0
    parent_id: int = 0
    child_id: int = 0
    percent: float = 0.0

@dataclass
class OwnershipLinkUpdated(DomainEvent):
    link_id: int = 0
    changed_fields: list[str] = field(default_factory=list)

@dataclass
class OwnershipLinkDeleted(DomainEvent):
    link_id: int = 0

@dataclass
class ControlLinkCreated(DomainEvent):
    link_id: int = 0
    control_type: str = ""

@dataclass
class ControlLinkUpdated(DomainEvent):
    link_id: int = 0
    changed_fields: list[str] = field(default_factory=list)

@dataclass
class ControlLinkDeleted(DomainEvent):
    link_id: int = 0

@dataclass
class BoundaryMembershipChanged(DomainEvent):
    boundary_id: int = 0
    entity_id: int = 0
    included: bool = True

@dataclass
class BoundaryAppliedToProject(DomainEvent):
    project_id: int = 0
    boundary_id: int = 0

@dataclass
class BoundarySnapshotCreated(DomainEvent):
    project_id: int = 0
    snapshot_id: int = 0
```

**Trigger chains:**

- `OwnershipLinkCreated/Updated/Deleted` → пересчёт effective ownership → пересчёт automatic boundary memberships
- `ControlLinkCreated/Updated/Deleted` → пересчёт automatic boundary memberships
- `BoundaryMembershipChanged` → Completeness Engine recalculate (entity scope changed)
- `BoundaryAppliedToProject` → Completeness Engine full recalculate
- `BoundarySnapshotCreated` → Audit log

---

## 14. Error Codes

| Code | HTTP | Описание |
|------|------|----------|
| `OWNERSHIP_EXCEEDS_100` | 422 | Сумма ownership долей превышает 100% |
| `OWNERSHIP_CYCLE_DETECTED` | 422 | Обнаружен цикл в графе владения |
| `SELF_OWNERSHIP_NOT_ALLOWED` | 422 | Сущность не может владеть собой |
| `SELF_CONTROL_NOT_ALLOWED` | 422 | Сущность не может контролировать себя |
| `CONTROL_LINK_EXISTS` | 409 | Связь контроля уже существует |
| `INVALID_DATE_RANGE` | 400 | valid_from >= valid_to |
| `PARENT_COMPANY_REQUIRED` | 422 | Групповая структура требует parent company |
| `DEFAULT_BOUNDARY_REQUIRED` | 422 | Необходим хотя бы один default boundary |
| `SNAPSHOT_IMMUTABLE` | 409 | Нельзя изменить snapshot опубликованного проекта |
| `BOUNDARY_NOT_FOUND` | 404 | Boundary с указанным id не найден |
| `ENTITY_NOT_FOUND` | 404 | Entity с указанным id не найден |
| `ENTITY_IN_USE` | 409 | Нельзя удалить сущность, привязанную к data points |

---

## 15. Ограничения

- Collector не может редактировать структуру;
- Published project должен использовать immutable snapshot;
- Нельзя менять snapshot постфактум без audit trail;
- Boundary rules должны быть объяснимыми;
- Система должна различать ownership и control — это разные сущности;
- Удаление сущности с привязанными data points запрещено (только деактивация);
- Все действия логируются в `audit_log`.

---

## 16. Критерии приёмки

Система считается принятой по модулю, если:

- [ ] Можно создать простую структуру (parent + 3 subsidiaries, 100% ownership)
- [ ] Можно создать сложную структуру (JV, associate, indirect ownership)
- [ ] Можно задать ownership и control раздельно
- [ ] Effective ownership рассчитывается автоматически через цепочку
- [ ] Можно создать несколько boundary definitions
- [ ] Financial boundary доступен по умолчанию
- [ ] Автоматический расчёт membership работает по правилам
- [ ] Можно вручную скорректировать boundary (override)
- [ ] Можно сохранить project snapshot (immutable)
- [ ] Boundary влияет на reporting scope (Completeness Engine учитывает entity scope)
- [ ] Preview показывает added / removed / changed entities при смене boundary
- [ ] Auditor может проследить, почему сущность вошла в отчёт
- [ ] Дерево структуры отображается в UI с ownership % и control type
- [ ] 3 режима отображения работают (Structure / Control / Boundary)
- [ ] Все действия логируются в audit_log
- [ ] Циклы владения обнаруживаются и блокируются
