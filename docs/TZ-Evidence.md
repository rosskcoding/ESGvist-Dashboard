# ТЗ: Модуль Evidence

**Модуль:** доказательная база ESG-данных
**Версия:** 1.0
**Статус:** На согласовании

---

## 1. Цель

Обеспечить полноценную поддержку доказательной базы для ESG-данных:

- подтверждение значений (data_points) и раскрытий (requirement_items);
- прохождение внутреннего и внешнего аудита;
- разделение технического файла (attachment) и бизнес-сущности (evidence);
- использование evidence в workflow, review и completeness.

---

## 2. Область применения

- подтверждение data_points;
- подтверждение requirement_items;
- хранение supporting documents и ссылок;
- проверка обязательности доказательств перед approve;
- отображение доказательной базы в review и audit режимах.

---

## 3. Основные принципы

### 3.1. Evidence — отдельная доменная сущность

Evidence существует как самостоятельный объект, не как вложение в attachment. Это позволяет:
- переиспользовать одно evidence для нескольких data_points и requirement_items;
- отслеживать жизненный цикл evidence независимо от данных;
- строить audit trail по evidence отдельно.

### 3.2. Attachment ≠ Evidence

| Концепция | Описание |
|-----------|----------|
| **Attachment** (файл) | Технический носитель: file_name, file_uri, mime_type, file_size |
| **Evidence** (доказательство) | Бизнес-сущность: title, description, type (file/link), source_type, привязки |

Evidence может быть:
- **файлом** (PDF, Excel, изображение) — хранится через `evidence_files`;
- **ссылкой** (URL на внешний ресурс) — хранится через `evidence_links`.

### 3.3. Reuse evidence

Один объект Evidence может быть привязан к нескольким data_points и requirement_items одновременно (через таблицы связей `data_point_evidences` и `requirement_item_evidences`).

### 3.4. Requirement-driven logic

Если `requirement_item.requires_evidence = true`:
- система блокирует approve без evidence;
- completeness engine учитывает наличие evidence;
- UI показывает индикатор "Evidence required".

---

## 4. Функциональные требования

### 4.1. Управление сущностью Evidence

Система должна позволять создавать и хранить Evidence:

| Атрибут | Тип | Описание |
|---------|-----|----------|
| `id` | bigserial | Primary key |
| `organization_id` | FK → organizations | Tenant isolation |
| `type` | enum: `file` / `link` | Тип evidence |
| `title` | text | Название (человекочитаемое) |
| `description` | text (nullable) | Описание / пояснение |
| `source_type` | enum: `manual` / `upload` / `integration` | Источник |
| `created_by` | FK → users | Кто создал |
| `created_at` | timestamptz | Дата создания |
| `updated_at` | timestamptz | Дата обновления |

**Связь с БД:** `evidences`

### 4.2. Evidence типа file

Для `type = 'file'` хранится дополнительная информация в `evidence_files`:

| Атрибут | Тип | Описание |
|---------|-----|----------|
| `evidence_id` | FK → evidences (PK) | 1:1 связь |
| `file_name` | text | Имя файла |
| `file_uri` | text | S3/MinIO path |
| `mime_type` | text (nullable) | MIME type |
| `file_size` | integer (nullable) | Размер в bytes |

**File storage:** MinIO (dev) / S3 (prod)

### 4.3. Evidence типа link

Для `type = 'link'` хранится дополнительная информация в `evidence_links`:

| Атрибут | Тип | Описание |
|---------|-----|----------|
| `evidence_id` | FK → evidences (PK) | 1:1 связь |
| `url` | text | URL ссылки |
| `label` | text (nullable) | Отображаемый текст |
| `access_note` | text (nullable) | Пояснение по доступу (логин, VPN) |

### 4.4. Привязка Evidence к DataPoint

Связь M:N через таблицу `data_point_evidences`:

| Атрибут | Тип | Описание |
|---------|-----|----------|
| `data_point_id` | FK → data_points | DataPoint |
| `evidence_id` | FK → evidences | Evidence |
| `linked_by` | FK → users | Кто привязал |
| `linked_at` | timestamptz | Когда привязано |

**Constraint:** `unique(data_point_id, evidence_id)` — нельзя привязать одно evidence дважды к одному DataPoint.

**Операции:**
- Привязать evidence к data_point;
- Отвязать evidence от data_point;
- Просмотреть все evidence для data_point.

### 4.5. Привязка Evidence к RequirementItem

Связь M:N через таблицу `requirement_item_evidences`:

| Атрибут | Тип | Описание |
|---------|-----|----------|
| `requirement_item_id` | FK → requirement_items | RequirementItem |
| `evidence_id` | FK → evidences | Evidence |
| `linked_by` | FK → users | Кто привязал |
| `linked_at` | timestamptz | Когда привязано |

**Constraint:** `unique(requirement_item_id, evidence_id)`

**Use case:** Evidence как подтверждение требования в целом (например, политика anti-corruption подтверждает disclosure GRI 205-1), а не конкретного значения.

### 4.6. Обязательность evidence

Поле `requires_evidence` добавляется в таблицу `requirement_items`:

```sql
ALTER TABLE requirement_items
    ADD COLUMN requires_evidence boolean NOT NULL DEFAULT false;
```

**Логика:**

```
IF requirement_item.requires_evidence = true:
    IF count(linked evidences) = 0:
        → блокировать approve
        → completeness status = partial (не complete)
        → UI показывает "⚠ Evidence required"
    ELSE:
        → evidence check passed
        → completeness может быть complete (если остальные условия выполнены)
```

**Связь с Completeness Engine:**

```typescript
// В calculateItemStatus добавить проверку:
if (item.requiresEvidence) {
  const evidenceCount = await db.dataPointEvidences.count({
    where: { dataPointId: binding.dataPointId }
  }) + await db.requirementItemEvidences.count({
    where: { requirementItemId: item.id }
  });

  if (evidenceCount === 0) return 'partial';
}
```

**Связь с Workflow Service:**

```typescript
// В approve transition добавить проверку:
if (requirementItem.requiresEvidence) {
  const hasEvidence = await checkEvidenceExists(dataPointId, requirementItemId);
  if (!hasEvidence) {
    throw new AppError('EVIDENCE_REQUIRED', 422,
      'This data point requires supporting evidence before approval.');
  }
}
```

### 4.7. Evidence в Review UI

Ревьюер видит в split panel (правая панель):

```
Evidence (3)
├── 📄 emissions_report_2025.pdf      ✓ File · 2.4 MB · Uploaded Mar 10
├── 📊 carbon_calculation_sheet.xlsx   ✓ File · 845 KB · Uploaded Mar 10
└── 🔗 kazenergo.kz/policy            ✓ Link · Public page

⚠ Evidence required for this metric
```

**Действия ревьюера:**
- Просмотреть/скачать файл;
- Открыть ссылку;
- Отклонить данные при недостаточности evidence (reject/request-revision);
- Комментарий: "Please attach audit certificate".

### 4.8. Evidence в Completeness Engine

Completeness Engine учитывает evidence как обязательный элемент:

| Ситуация | requires_evidence | Evidence есть | Результат |
|----------|:-:|:-:|----------|
| Данные approved, evidence есть | true | ✅ | `complete` |
| Данные approved, evidence нет | true | ❌ | `partial` (reason: "Missing required evidence") |
| Данные approved, evidence не требуется | false | — | `complete` (evidence не влияет) |
| Данных нет | — | — | `missing` |

### 4.9. Audit / traceability

Все операции с evidence логируются в `audit_log`:

| Действие | entity_type | Что записывается |
|----------|------------|-----------------|
| Создание evidence | Evidence | title, type, source_type |
| Привязка к data_point | DataPointEvidence | data_point_id, evidence_id, linked_by |
| Отвязка от data_point | DataPointEvidence | data_point_id, evidence_id |
| Привязка к requirement_item | RequirementItemEvidence | requirement_item_id, evidence_id |
| Удаление evidence | Evidence | evidence_id (если разрешено) |

**Аудитор** видит:
- Все evidence в read-only режиме;
- Историю привязок;
- Кто загрузил, когда, к чему привязано.

---

## 5. Роли и права

| Действие | admin | esg_manager | collector | reviewer | auditor |
|----------|:---:|:---:|:---:|:---:|:---:|
| Настройка requires_evidence | ✅ | ❌ | ❌ | ❌ | ❌ |
| Создание evidence | ✅ | ✅ | ✅ assigned | ❌ | ❌ |
| Привязка evidence к data_point | ✅ | ✅ | ✅ own dp | ❌ | ❌ |
| Привязка evidence к requirement_item | ✅ | ✅ | ❌ | ❌ | ❌ |
| Просмотр evidence | ✅ | ✅ | ✅ own | ✅ assigned | ✅ |
| Скачивание файла | ✅ | ✅ | ✅ own | ✅ assigned | ✅ |
| Удаление evidence | ✅ | ⚠️ если не approved | ⚠️ own, до approve | ❌ | ❌ |
| Аудит привязок | ✅ | ✅ | ❌ | ❌ | ✅ |

---

## 6. API Endpoints

### Evidence CRUD

```
GET    /api/evidences                           — список (с фильтрами: type, source_type, unlinked)
GET    /api/evidences/:id                       — детали evidence (+ файл/ссылка + привязки)
POST   /api/evidences                           — создать evidence (file или link)
PUT    /api/evidences/:id                       — обновить title, description
DELETE /api/evidences/:id                       — удалить (если не используется в approved scope)
```

### File upload

```
POST   /api/evidences/upload                    — upload файла → создаёт evidence типа file
```

**Request:** `multipart/form-data` с полями: `file`, `title`, `description`

### Привязки

```
POST   /api/data-points/:id/evidences           — привязать evidence к data_point
DELETE /api/data-points/:id/evidences/:evidenceId — отвязать
GET    /api/data-points/:id/evidences           — список evidence для data_point

POST   /api/requirement-items/:id/evidences     — привязать evidence к requirement_item
DELETE /api/requirement-items/:id/evidences/:evidenceId — отвязать
GET    /api/requirement-items/:id/evidences     — список evidence для requirement_item
```

### Поиск

```
GET    /api/evidences?type=file&unlinked=true   — файлы без привязок
GET    /api/evidences?dataPointId=123           — evidence для конкретного DataPoint
GET    /api/evidences?requirementItemId=456     — evidence для конкретного RequirementItem
```

---

## 7. Модель данных (PostgreSQL)

### 7.1. Изменение в requirement_items

```sql
ALTER TABLE requirement_items
    ADD COLUMN requires_evidence boolean NOT NULL DEFAULT false;
```

### 7.2. evidences

```sql
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
```

### 7.3. evidence_files

```sql
create table evidence_files (
    evidence_id         bigint primary key references evidences(id) on delete cascade,
    file_name           text not null,
    file_uri            text not null,
    mime_type           text,
    file_size           integer
);
```

### 7.4. evidence_links

```sql
create table evidence_links (
    evidence_id         bigint primary key references evidences(id) on delete cascade,
    url                 text not null,
    label               text,
    access_note         text
);
```

### 7.5. data_point_evidences

```sql
create table data_point_evidences (
    id                  bigserial primary key,
    data_point_id       bigint not null references data_points(id) on delete cascade,
    evidence_id         bigint not null references evidences(id) on delete cascade,
    linked_by           bigint references users(id) on delete set null,
    linked_at           timestamptz not null default now(),
    unique (data_point_id, evidence_id)
);
```

### 7.6. requirement_item_evidences

```sql
create table requirement_item_evidences (
    id                  bigserial primary key,
    requirement_item_id bigint not null references requirement_items(id) on delete cascade,
    evidence_id         bigint not null references evidences(id) on delete cascade,
    linked_by           bigint references users(id) on delete set null,
    linked_at           timestamptz not null default now(),
    unique (requirement_item_id, evidence_id)
);
```

### 7.7. Индексы

```sql
create index idx_evidences_org on evidences(organization_id);
create index idx_evidences_type on evidences(type);
create index idx_evidences_created_by on evidences(created_by);
create index idx_dpe_data_point on data_point_evidences(data_point_id);
create index idx_dpe_evidence on data_point_evidences(evidence_id);
create index idx_rie_requirement_item on requirement_item_evidences(requirement_item_id);
create index idx_rie_evidence on requirement_item_evidences(evidence_id);
```

---

## 8. Связь с другими модулями

### 8.1. Completeness Engine (TZ-ESGvist-v1, раздел 5)

Добавить проверку evidence в `calculateItemStatus`:

```
IF item.requires_evidence == true
   AND count(data_point_evidences + requirement_item_evidences) == 0:
   → status = 'partial'
   → status_reason = "Missing required evidence"
```

### 8.2. Workflow Service (ARCHITECTURE.md, раздел 3.5)

Добавить проверку evidence в transition `in_review → approved`:

```
IF any linked requirement_item.requires_evidence == true
   AND evidence count == 0:
   → reject transition
   → return error EVIDENCE_REQUIRED (422)
```

### 8.3. Review Service (TZ-Reviewer.md)

В split panel (правая панель) добавить секцию "Evidence" с:
- Списком привязанных evidence (файлы + ссылки);
- Индикатором обязательности;
- Кнопками просмотра/скачивания.

### 8.4. Data Entry Wizard (mockup-v3, s-wizard-qn)

В форме ввода данных показывать:
- Секцию "Evidence" с drag-and-drop upload;
- Индикатор `⚠ Evidence required` если `requires_evidence = true`;
- Список уже привязанных evidence с возможностью отвязать.

### 8.5. Evidence Repository (mockup-v3, s-evidence)

Экран `/evidence` показывает:
- Полный список evidence организации;
- Фильтры: type (file/link), binding status (bound/unbound), date;
- Для каждого evidence: к каким data_points и requirement_items привязано;
- Unbound evidence — подсветка (⚠ не привязан к метрике).

### 8.6. Audit Log (TZ-ESGvist-v1, раздел 3.8)

Все операции с evidence записываются в `audit_log`:
- create, update, delete evidence;
- link/unlink evidence to data_point or requirement_item.

---

## 9. Events (Event-Driven Layer)

```typescript
type EvidenceEvent =
  | { type: 'EvidenceCreated';         payload: { evidenceId: number; type: 'file' | 'link' } }
  | { type: 'EvidenceUpdated';         payload: { evidenceId: number; changedFields: string[] } }
  | { type: 'EvidenceDeleted';         payload: { evidenceId: number } }
  | { type: 'EvidenceLinkedToDP';      payload: { evidenceId: number; dataPointId: number } }
  | { type: 'EvidenceUnlinkedFromDP';  payload: { evidenceId: number; dataPointId: number } }
  | { type: 'EvidenceLinkedToRI';      payload: { evidenceId: number; requirementItemId: number } }
  | { type: 'EvidenceUnlinkedFromRI';  payload: { evidenceId: number; requirementItemId: number } };
```

**Trigger chains:**
- `EvidenceLinkedToDP` → Completeness Engine recalculate (если requires_evidence)
- `EvidenceUnlinkedFromDP` → Completeness Engine recalculate
- `EvidenceCreated` → Audit log
- `EvidenceDeleted` → Audit log + check if used in approved scope

---

## 10. Ограничения

- Нельзя approve data_point, если `requires_evidence = true` и evidence отсутствует;
- Collector не может изменять evidence после approve (только через rollback ESG-manager);
- Удаление evidence, используемого в approved scope, **запрещено** (error `EVIDENCE_IN_USE`, 409);
- Один файл = один evidence (если нужен тот же файл для другого контекста — создаётся новый evidence, ссылающийся на тот же file_uri);
- Максимальный размер файла: 10 MB (настраивается);
- Допустимые типы файлов: PDF, XLSX, XLS, DOC, DOCX, JPG, PNG, CSV (настраивается).

---

## 11. Error Codes

| Code | HTTP | Описание |
|------|------|----------|
| `EVIDENCE_REQUIRED` | 422 | Нельзя approve без evidence (requires_evidence = true) |
| `EVIDENCE_IN_USE` | 409 | Нельзя удалить evidence, используемое в approved scope |
| `EVIDENCE_NOT_FOUND` | 404 | Evidence с указанным id не найден |
| `EVIDENCE_ALREADY_LINKED` | 409 | Evidence уже привязан к этому data_point/requirement_item |
| `EVIDENCE_FILE_TOO_LARGE` | 422 | Файл превышает максимальный размер |
| `EVIDENCE_FILE_TYPE_NOT_ALLOWED` | 422 | Недопустимый тип файла |

---

## 12. Критерии приёмки

- [ ] Можно создать evidence типа file (upload + metadata)
- [ ] Можно создать evidence типа link (url + label)
- [ ] Можно привязать evidence к data_point (M:N)
- [ ] Можно привязать evidence к requirement_item (M:N)
- [ ] Одно evidence переиспользуется в нескольких привязках
- [ ] `requires_evidence = true` блокирует approve без evidence
- [ ] `requires_evidence` учитывается в Completeness Engine (partial без evidence)
- [ ] Reviewer видит evidence в split panel
- [ ] Auditor видит evidence в read-only
- [ ] Удаление evidence в approved scope заблокировано (409)
- [ ] Все операции записываются в audit_log
- [ ] Evidence Repository показывает bound/unbound файлы
- [ ] Wizard показывает drag-and-drop upload + "Evidence required" badge
