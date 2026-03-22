# ESGvist — System Architecture

**Версия:** 1.0
**Дата:** 2026-03-22
**Статус:** На согласовании

---

## 1. Общая архитектура

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React SPA)                  │
│          Next.js · TypeScript · TailwindCSS              │
└────────────────────────┬────────────────────────────────┘
                         │ HTTPS
┌────────────────────────▼────────────────────────────────┐
│                   API Gateway (REST)                     │
│              Auth · Rate Limiting · CORS                 │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                  Core Services Layer                     │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Standard    │  │   Mapping    │  │    Merge     │  │
│  │   Service     │  │   Service    │  │   Engine     │  │
│  └──────────────┘  └──────────────┘  └──────┬───────┘  │
│                                              │          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────▼───────┐  │
│  │    Data      │  │  Workflow    │  │ Completeness │  │
│  │   Service    │──│   Service    │──│   Engine     │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Review     │  │ Notification │  │  Reporting   │  │
│  │   Service    │  │   Service    │  │   Service    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                          │
│  ┌──────────────┐                                       │
│  │    Audit     │                                       │
│  │   Service    │                                       │
│  └──────────────┘                                       │
└─────────┬───────────────────┬───────────────┬───────────┘
          │                   │               │
┌─────────▼─────────┐ ┌──────▼──────┐ ┌──────▼──────┐
│    PostgreSQL      │ │ File Storage│ │  Event Bus  │
│   (primary DB)     │ │  (S3/MinIO) │ │ (in-process)│
└────────────────────┘ └─────────────┘ └─────────────┘
```

---

## 2. Technology Stack (предварительно)

| Layer | Technology | Обоснование |
|-------|-----------|-------------|
| **Frontend** | React + Next.js + TypeScript | SPA с SSR, типизация, экосистема |
| **Styling** | Tailwind CSS | Utility-first, быстрая разработка |
| **State** | Zustand или React Query | Серверный state → React Query; клиентский → Zustand |
| **API** | REST (JSON) | Простота, достаточно для MVP |
| **Backend** | Node.js + TypeScript | Единый язык с фронтом, производительность |
| **ORM** | Prisma | Type-safe queries, миграции, introspection |
| **Auth** | JWT + bcrypt | MVP; SSO (SAML/OAuth) в Phase 3 |
| **DB** | PostgreSQL 15+ | JSONB, CTE, window functions, GIN indexes |
| **File Storage** | MinIO (dev) / S3 (prod) | S3-совместимый API, self-hosted для dev |
| **Event Bus** | In-process EventEmitter (MVP) | Простота; Kafka/RabbitMQ в Phase 3 при необходимости |
| **Testing** | Jest + Playwright | Unit + integration + E2E |
| **CI/CD** | GitHub Actions | Автоматизация тестов и деплоя |

> **Открытый вопрос:** финальный выбор стека требует согласования (см. TZ-ESGvist-v1 раздел 14, вопросы 1–2).

---

## 3. Сервисы (Core Services Layer)

### 3.1. Standard Service

**Ответственность:**
- CRUD для `standards`, `standard_sections`
- CRUD для `disclosure_requirements`
- CRUD для `requirement_items`, `requirement_item_dependencies`
- Версионирование стандартов
- Import структуры стандарта (JSON/CSV)

**API endpoints:**
```
GET/POST       /api/standards
GET/PUT/DELETE /api/standards/:id
GET/POST       /api/standards/:id/sections
GET/POST       /api/standards/:id/disclosures
GET/POST       /api/disclosures/:id/items
GET/POST       /api/items/:id/dependencies
```

**Events emitted:**
- `StandardCreated`
- `StandardDeactivated`
- `RequirementItemChanged` → triggers Completeness Engine

---

### 3.2. Mapping Service

**Ответственность:**
- CRUD для `shared_elements`, `shared_element_dimensions`
- CRUD для `requirement_item_shared_elements` (mappings)
- Версионирование маппингов (version, is_current, valid_from/valid_to)
- Impact analysis при изменении mapping
- Query: «shared elements used by multiple standards»

**API endpoints:**
```
GET/POST       /api/shared-elements
GET/PUT        /api/shared-elements/:id
GET/POST       /api/shared-elements/:id/dimensions
GET/POST       /api/mappings
GET            /api/mappings/cross-standard   — элементы в нескольких стандартах
GET            /api/mappings/impact-preview   — preview влияния изменения
```

**Events emitted:**
- `MappingCreated`
- `MappingChanged` → triggers Merge Engine + Completeness Engine

---

### 3.3. Merge Engine

**Ключевой сервис.** Объединение стандартов через shared layer.

**Ответственность:**
- Алгоритм merge (5 шагов: collect → group → classify → find orphans → build view)
- Расчёт intersection (common elements)
- Расчёт delta (unique + overrides)
- Генерация MergedView response
- Impact preview при добавлении стандарта

**Алгоритм:**

```
Input: reporting_project_id

Step 1: SELECT all requirement_items
        FROM standards linked to project
        (via reporting_project_standards)

Step 2: GROUP BY shared_element_id
        (via requirement_item_shared_elements)

Step 3: For each shared_element:
        - required_by: [list of standards]
        - is_common: required_by.length > 1
        - deltas: requirement_deltas for this context
        - overrides: requirement_item_overrides

Step 4: Find orphans
        (requirement_items WITHOUT mapping to any shared_element)

Step 5: Build MergedView response
        + attach current data_points (if exist)
        + attach requirement_item_statuses
```

**API endpoints:**
```
GET  /api/projects/:id/merge             — full merged view
GET  /api/projects/:id/merge/coverage    — coverage per standard
POST /api/projects/:id/merge/preview     — impact preview добавления стандарта
```

**Events consumed:**
- `StandardAdded` → run merge
- `MappingChanged` → recalculate merge

**Events emitted:**
- `MergeCompleted` → triggers Completeness Engine

---

### 3.4. Data Service

**Ответственность:**
- CRUD для `data_points`, `data_point_dimensions`
- CRUD для `attachments` (evidence)
- CRUD для `methodologies`, `boundaries`, `source_records`
- **Identity Rule** — определение reuse
- Binding management (`requirement_item_data_points`)

**Identity Rule (reuse detection):**

```typescript
interface IdentityKey {
  shared_element_id: number;
  organization_id: number;
  reporting_period_id: number;
  unit_code: string;
  boundary_id: number | null;
  methodology_id: number | null;
  dimensions: Map<string, string>; // полный match
}

function findReusableDataPoint(key: IdentityKey): DataPoint | null {
  // Поиск существующего DataPoint с идентичными параметрами
  // Если найден → предложить reuse
  // Если не найден → создать новый
}
```

**Правила:**
- Если все 7 параметров совпадают → reuse (создаётся binding, не DataPoint)
- Если хотя бы один отличается → новый DataPoint
- При редактировании multi-bound DataPoint → warning с impact list

**API endpoints:**
```
GET/POST       /api/data-points
GET/PUT        /api/data-points/:id
GET/POST       /api/data-points/:id/dimensions
GET            /api/data-points/find-reuse?...   — поиск по Identity Rule
POST           /api/data-points/:id/bind         — создать binding
GET/POST       /api/attachments
POST           /api/attachments/:id/bind
```

**Events emitted:**
- `DataPointCreated`
- `DataPointUpdated` → triggers Completeness Engine
- `DataPointBound` → triggers Completeness Engine
- `AttachmentUploaded`

---

### 3.5. Workflow Service

**Ответственность:**
- State machine для `data_points.status`
- Валидация переходов
- Ограничения редактирования по статусу
- Откат approved → draft (ESG-manager only)

**State Machine:**

```
         ┌──────────┐
         │  draft    │ ←───── created / rollback
         └────┬──────┘
              │ submit (collector)
         ┌────▼──────┐
         │ submitted  │
         └────┬──────┘
              │ auto (reviewer assigned)
         ┌────▼───────┐
         │  in_review  │
         └────┬───────┘
              │
    ┌─────────┼──────────────┐
    │         │              │
┌───▼────┐ ┌─▼──────────┐ ┌─▼────────────┐
│approved│ │  rejected   │ │needs_revision│
└────────┘ └──────┬──────┘ └──────┬───────┘
                  │               │
                  └───── fix ─────┘
                         │
                  ┌──────▼───┐
                  │ submitted │
                  └──────────┘
```

**Transition rules:**

```typescript
const TRANSITIONS: Record<Status, AllowedTransition[]> = {
  draft:           [{ to: 'submitted',      role: ['collector', 'esg_manager'] }],
  submitted:       [{ to: 'in_review',      role: ['system'] }],
  in_review:       [{ to: 'approved',       role: ['reviewer', 'esg_manager'] },
                    { to: 'rejected',        role: ['reviewer', 'esg_manager'], requireComment: true },
                    { to: 'needs_revision',  role: ['reviewer', 'esg_manager'], requireComment: true }],
  approved:        [{ to: 'draft',           role: ['esg_manager'], requireComment: true }],
  rejected:        [{ to: 'submitted',       role: ['collector'] }],
  needs_revision:  [{ to: 'submitted',       role: ['collector'] }],
};
```

**Locking rules:**

| Status | Can edit value | Can edit metadata |
|--------|:---:|:---:|
| draft | ✅ | ✅ |
| submitted | ❌ | ❌ |
| in_review | ❌ | ❌ |
| approved | ❌ | ❌ |
| rejected | ✅ | ✅ |
| needs_revision | ✅ | ✅ |

**API endpoints:**
```
POST /api/data-points/:id/submit
POST /api/data-points/:id/approve
POST /api/data-points/:id/reject          — requires comment
POST /api/data-points/:id/request-revision — requires comment
POST /api/data-points/:id/rollback        — esg_manager only, requires comment
```

**Events emitted:**
- `DataPointSubmitted` → notification to reviewer
- `DataPointApproved` → notification to collector + Completeness Engine
- `DataPointRejected` → notification to collector
- `DataPointRolledBack` → Completeness Engine

---

### 3.6. Review Service

**Ответственность:**
- Split panel review UI data preparation
- Comments (threaded, typed)
- Batch operations (approve/reject multiple)
- Review consistency (reuse count, impact of approval)

**API endpoints:**
```
GET  /api/review/pending                 — данные на ревью (с фильтрами)
GET  /api/review/:data_point_id/context  — полный контекст для правой панели
POST /api/review/batch-approve           — массовое утверждение
POST /api/review/batch-reject            — массовое отклонение (comment обязателен)
GET/POST /api/comments
PATCH    /api/comments/:id/resolve
```

**Batch rules:**
- Batch reject: comment **обязателен** (единый для всех)
- Batch approve: comment опционален
- Summary preview перед batch action обязателен

---

### 3.7. Completeness Engine

**Самый важный сервис.** Рассчитывает статус покрытия требований.

**Input:**
```
data_points + bindings (requirement_item_data_points)
requirement_items + rules (validation_rule, granularity_rule)
mapping (requirement_item_shared_elements)
```

**Output:**
```
requirement_item_statuses   (missing / partial / complete / not_applicable)
disclosure_requirement_statuses  (missing / partial / complete + completion_percent)
```

**Trigger events (when to recalculate):**

| Event | Action |
|-------|--------|
| `DataPointCreated` | Recalculate items bound to this data_point |
| `DataPointUpdated` | Recalculate items bound to this data_point |
| `DataPointApproved` | Recalculate → status may become `complete` |
| `DataPointRejected` | Recalculate → status may become `partial` |
| `DataPointRolledBack` | Recalculate → status may become `partial` |
| `DataPointBound` | Recalculate newly bound item |
| `StandardAdded` | Full recalculate for all new requirement_items |
| `MappingChanged` | Recalculate affected items |
| `RequirementItemChanged` | Recalculate affected item + cascade to disclosure |

**Algorithm:**

```typescript
async function calculateItemStatus(
  projectId: number,
  requirementItemId: number
): Promise<'missing' | 'partial' | 'complete' | 'not_applicable'> {

  // 1. Find bindings
  const bindings = await db.requirementItemDataPoints.findMany({
    where: { reporting_project_id: projectId, requirement_item_id: requirementItemId }
  });

  if (bindings.length === 0) return 'missing';

  // 2. Check data_point status
  const dataPoints = await Promise.all(
    bindings.map(b => db.dataPoints.findUnique({ where: { id: b.data_point_id } }))
  );

  const hasApproved = dataPoints.some(dp => dp.status === 'approved');
  if (!hasApproved) return 'partial'; // data exists but not approved

  // 3. Check dimension rules
  const item = await db.requirementItems.findUnique({ where: { id: requirementItemId } });
  const dimensionsSatisfied = await checkDimensionRules(item.granularity_rule, dataPoints);
  if (!dimensionsSatisfied) return 'partial';

  // 4. Check evidence (if item_type = 'document')
  if (item.item_type === 'document') {
    const attachments = await db.attachments.count({
      where: { requirement_item_id: requirementItemId }
    });
    if (attachments === 0) return 'partial';
  }

  // 5. Check validation rules
  const validationPassed = await checkValidationRules(item.validation_rule, dataPoints);
  if (!validationPassed) return 'partial';

  return 'complete';
}

async function aggregateDisclosureStatus(
  projectId: number,
  disclosureId: number
): Promise<{ status: string, completion_percent: number }> {

  const items = await db.requirementItems.findMany({
    where: { disclosure_requirement_id: disclosureId, is_required: true }
  });

  const statuses = await Promise.all(
    items.map(i => db.requirementItemStatuses.findUnique({
      where: { reporting_project_id_requirement_item_id: { reporting_project_id: projectId, requirement_item_id: i.id } }
    }))
  );

  const complete = statuses.filter(s => s?.status === 'complete').length;
  const total = statuses.filter(s => s?.status !== 'not_applicable').length;

  return {
    status: complete === total ? 'complete' : complete > 0 ? 'partial' : 'missing',
    completion_percent: total > 0 ? (complete / total) * 100 : 0
  };
}
```

**Performance requirements:**
- < 100ms per requirement_item
- < 5s per full project recalculation
- Async execution (не блокирует UI)

---

### 3.8. Notification Service

**Ответственность:**
- In-app notifications (`notifications` table)
- Email notifications (async)
- SLA breach alerts
- Deadline reminders

**Notification triggers:**

| Event | Recipient | Channel |
|-------|-----------|---------|
| Metric assigned | Collector | in-app + email |
| DataPoint submitted | Reviewer | in-app + email |
| DataPoint approved | Collector | in-app |
| DataPoint rejected | Collector | in-app + email |
| Deadline -3 days | Collector | in-app + email |
| Deadline breached | Collector + ESG-manager | in-app + email |
| SLA Level 1 (+3 days) | Backup + ESG-manager | in-app + email |
| SLA Level 2 (+7 days) | Admin | in-app + email |
| Standard added | ESG-manager | in-app |
| 100% completeness | ESG-manager | in-app |

**API endpoints:**
```
GET   /api/notifications              — список для текущего пользователя
PATCH /api/notifications/:id/read     — отметить прочитанным
POST  /api/notifications/read-all     — отметить все прочитанными
```

---

### 3.9. Reporting Service

**Ответственность:**
- Readiness check (blocking issues, warnings, score)
- GRI Content Index generation
- Export (PDF, Excel)
- Publish flow (lock data, snapshot)

**API endpoints:**
```
GET  /api/projects/:id/export/readiness     — готовность к экспорту
POST /api/projects/:id/export/gri-index     — GRI Content Index (PDF/Excel)
POST /api/projects/:id/export/report        — Full report
POST /api/projects/:id/publish              — Publish (lock all data)
```

---

### 3.10. Audit Service

**Ответственность:**
- Запись всех действий в `audit_log`
- Версионирование DataPoint (`data_point_versions`)
- Query с фильтрами (entity_type, user, date range)

**Logged actions:**
- create, update, delete
- submit, approve, reject, request_revision, rollback
- export, publish
- login, logout
- assignment changes

**API endpoints:**
```
GET /api/audit-log     — с фильтрами (entity_type, entity_id, user_id, date_from, date_to)
```

---

## 4. Event-Driven Layer

### 4.1. Architecture

```
MVP: In-process EventEmitter (synchronous-ish, same Node.js process)
Phase 3: External event bus (Kafka/RabbitMQ) if needed for scale
```

### 4.2. Event Flow

```
┌─────────────┐     DataPointUpdated     ┌──────────────────┐
│ Data Service │ ─────────────────────── │ Completeness     │
│              │                         │ Engine           │
└─────────────┘                         └────────┬─────────┘
                                                  │ StatusChanged
                                         ┌────────▼─────────┐
                                         │ Notification     │
                                         │ Service          │
                                         └──────────────────┘
```

```
┌─────────────┐     StandardAdded        ┌──────────────────┐
│ Project      │ ────────────────────── │ Merge Engine     │
│ Service      │                         └────────┬─────────┘
└─────────────┘                                   │ MergeCompleted
                                         ┌────────▼─────────┐
                                         │ Completeness     │
                                         │ Engine           │
                                         └──────────────────┘
```

```
┌─────────────┐     MappingChanged       ┌──────────────────┐
│ Mapping      │ ────────────────────── │ Merge Engine     │
│ Service      │                         │ + Completeness   │
└─────────────┘                         └──────────────────┘
```

### 4.3. Event Types

```typescript
// Core events
type DomainEvent =
  | { type: 'DataPointCreated';      payload: { dataPointId: number; projectId: number } }
  | { type: 'DataPointUpdated';      payload: { dataPointId: number; changedFields: string[] } }
  | { type: 'DataPointSubmitted';    payload: { dataPointId: number; submittedBy: number } }
  | { type: 'DataPointApproved';     payload: { dataPointId: number; reviewedBy: number } }
  | { type: 'DataPointRejected';     payload: { dataPointId: number; reviewedBy: number; comment: string } }
  | { type: 'DataPointRolledBack';   payload: { dataPointId: number; rolledBackBy: number; reason: string } }
  | { type: 'DataPointBound';        payload: { dataPointId: number; requirementItemId: number; projectId: number } }
  | { type: 'StandardAdded';         payload: { projectId: number; standardId: number } }
  | { type: 'StandardRemoved';       payload: { projectId: number; standardId: number } }
  | { type: 'MappingChanged';        payload: { mappingId: number; changeType: 'created' | 'updated' | 'deleted' } }
  | { type: 'MergeCompleted';        payload: { projectId: number } }
  | { type: 'RequirementItemChanged';payload: { itemId: number; changedFields: string[] } }
  | { type: 'AssignmentCreated';     payload: { assignmentId: number; collectorId: number } }
  | { type: 'DeadlineApproaching';   payload: { assignmentId: number; daysRemaining: number } }
  | { type: 'SLABreached';           payload: { assignmentId: number; level: 1 | 2 } };
```

---

## 5. Data Flow (основные сценарии)

### 5.1. Ввод данных (основной flow)

```
User inputs data in wizard
         │
         ▼
    Data Service
    ├── validate fields (field-level)
    ├── check Identity Rule → reuse or create new
    ├── save data_point (status: draft)
    └── emit DataPointCreated
         │
         ▼
    User clicks "Submit"
         │
         ▼
    Workflow Service
    ├── validate transition (draft → submitted)
    ├── check record-level validation
    ├── update status
    ├── create data_point_version
    └── emit DataPointSubmitted
         │
         ▼
    Notification Service
    └── notify reviewer (in-app + email)
         │
         ▼
    Completeness Engine
    ├── recalculate requirement_item_status
    ├── aggregate disclosure_status
    └── emit StatusChanged
```

### 5.2. Добавление стандарта

```
ESG Manager adds IFRS S2 to project
         │
         ▼
    Project Service
    ├── insert reporting_project_standards
    └── emit StandardAdded
         │
         ▼
    Merge Engine
    ├── collect all requirement_items (GRI + IFRS)
    ├── group by shared_element
    ├── find intersections, deltas, orphans
    ├── generate impact preview:
    │   "12/18 covered, 3 deltas, 3 new"
    └── emit MergeCompleted
         │
         ▼
    Completeness Engine
    ├── create requirement_item_statuses for new items
    ├── mark reused items as 'complete' (if data approved)
    ├── mark new items as 'missing'
    └── recalculate disclosure_statuses
```

### 5.3. Review flow

```
Reviewer opens /validation
         │
         ▼
    Review Service
    ├── GET pending data_points (assigned to reviewer)
    ├── load context: value, prev year, evidence, comments
    └── display split panel
         │
         ▼
    Reviewer clicks "Approve"
         │
         ▼
    Workflow Service
    ├── validate transition (in_review → approved)
    ├── update status
    ├── create data_point_version
    └── emit DataPointApproved
         │
         ├──▶ Notification Service → notify collector
         │
         └──▶ Completeness Engine
              ├── recalculate item status → 'complete'
              ├── recalculate disclosure status
              └── if all disclosures complete → notify ESG-manager
```

---

## 6. Database Architecture

### 6.1. Schema overview

```
┌─── Standards ───────────────────────────────────────┐
│ standards ← standard_sections                        │
│ standards ← disclosure_requirements ← requirement_items │
│                                      ← requirement_item_dependencies │
└──────────────────────────────────────────────────────┘
        │
        │ requirement_item_shared_elements (mapping)
        ▼
┌─── Shared Layer ────────────────────────────────────┐
│ shared_elements ← shared_element_dimensions          │
└──────────────────────────────────────────────────────┘
        │
        │ data_points.shared_element_id
        ▼
┌─── Data Layer ──────────────────────────────────────┐
│ data_points ← data_point_dimensions                  │
│ data_points ← attachments                            │
│ data_points ← data_point_versions                    │
│ data_points ← comments                               │
│ methodologies, boundaries, source_records            │
└──────────────────────────────────────────────────────┘
        │
        │ requirement_item_data_points (binding)
        ▼
┌─── Completeness ────────────────────────────────────┐
│ requirement_item_statuses                            │
│ disclosure_requirement_statuses                      │
└──────────────────────────────────────────────────────┘

┌─── Project ─────────────────────────────────────────┐
│ organizations ← reporting_periods ← reporting_projects │
│ reporting_projects ← reporting_project_standards     │
│ reporting_projects ← metric_assignments              │
└──────────────────────────────────────────────────────┘

┌─── Users & System ──────────────────────────────────┐
│ users, notifications, audit_log                      │
│ requirement_deltas, requirement_item_overrides        │
│ calculation_rules, derived_data_points               │
└──────────────────────────────────────────────────────┘
```

### 6.2. Key indexes

См. TZ-ESGvist-v1.md раздел 3.10 — 15+ индексов.

### 6.3. Connection pooling

- MVP: PgBouncer (transaction pooling)
- Max connections: 50 per service instance
- Statement timeout: 30s

---

## 7. Security Architecture

### 7.1. Authentication

```
MVP:
  email + password → bcrypt hash → JWT (access + refresh)
  access_token: 15 min TTL
  refresh_token: 7 days TTL

Phase 3:
  + SSO (SAML 2.0 / OAuth 2.0)
  + 2FA (TOTP)
```

### 7.2. Authorization (RBAC)

```typescript
const ROLES = {
  admin:       { level: 100, description: 'Full system access' },
  esg_manager: { level: 80,  description: 'Project + assignment + publish' },
  reviewer:    { level: 60,  description: 'Review + approve/reject' },
  collector:   { level: 40,  description: 'Data entry (assigned only)' },
  auditor:     { level: 20,  description: 'Read-only + audit log' },
};
```

**Row-level security:**
- Collector sees only assigned metrics (`metric_assignments.collector_id = user.id`)
- Reviewer sees only assigned reviews (`metric_assignments.reviewer_id = user.id`)
- ESG-manager sees all project data
- Auditor sees all data (read-only)

### 7.3. API security

- HTTPS only (TLS 1.3)
- CORS whitelist
- Rate limiting: 100 req/min per user
- Input validation: Zod schemas on all endpoints
- SQL injection: Prisma parameterized queries
- File upload: type + size validation, virus scan (Phase 3)

---

## 8. Deployment Architecture

### 8.1. MVP (single server)

```
┌────────────────────────────────────────┐
│            Docker Compose              │
│                                        │
│  ┌──────────┐  ┌──────────┐           │
│  │ Next.js  │  │ Node.js  │           │
│  │ Frontend │  │ API      │           │
│  │ :3000    │  │ :4000    │           │
│  └──────────┘  └──────────┘           │
│                                        │
│  ┌──────────┐  ┌──────────┐           │
│  │ Postgres │  │  MinIO   │           │
│  │ :5432    │  │  :9000   │           │
│  └──────────┘  └──────────┘           │
│                                        │
│  ┌──────────┐                         │
│  │  Nginx   │ (reverse proxy)         │
│  │  :443    │                         │
│  └──────────┘                         │
└────────────────────────────────────────┘
```

### 8.2. Production (Phase 3)

```
CDN (CloudFront)
  │
  ▼
Load Balancer (ALB)
  │
  ├── Frontend (ECS/EKS × 2)
  │
  ├── API (ECS/EKS × 2)
  │
  ├── Worker (background jobs × 1)
  │
  ▼
RDS PostgreSQL (Multi-AZ)
  │
S3 (file storage)
  │
ElastiCache Redis (sessions, cache)
```

---

## 9. Monitoring & Observability

### 9.1. Logging

- Structured JSON logs (pino / winston)
- Log levels: error, warn, info, debug
- Request/response logging (API gateway)
- Audit log (business events → `audit_log` table)

### 9.2. Metrics (Phase 2+)

- API response times (p50, p95, p99)
- Completeness Engine execution time
- Database query times
- Error rates
- Active users

### 9.3. Health checks

```
GET /api/health         — basic (API alive)
GET /api/health/db      — database connectivity
GET /api/health/storage — file storage connectivity
```

---

## 10. Folder Structure (предварительно)

```
esgvist/
├── apps/
│   ├── web/                    # Next.js frontend
│   │   ├── app/               # App router pages
│   │   ├── components/        # React components
│   │   ├── lib/               # Utilities, hooks
│   │   └── styles/            # Tailwind config
│   │
│   └── api/                    # Node.js backend
│       ├── src/
│       │   ├── modules/
│       │   │   ├── standards/  # Standard Service
│       │   │   ├── mapping/    # Mapping Service
│       │   │   ├── merge/      # Merge Engine
│       │   │   ├── data/       # Data Service
│       │   │   ├── workflow/   # Workflow Service
│       │   │   ├── review/     # Review Service
│       │   │   ├── completeness/ # Completeness Engine
│       │   │   ├── reporting/  # Reporting Service
│       │   │   ├── notifications/ # Notification Service
│       │   │   └── audit/      # Audit Service
│       │   ├── common/         # Shared utilities
│       │   ├── events/         # Event bus
│       │   └── middleware/     # Auth, validation, error handling
│       ├── prisma/
│       │   ├── schema.prisma  # DB schema
│       │   ├── migrations/    # Migration files
│       │   └── seed/          # Seed data
│       └── tests/
│
├── packages/
│   └── shared/                 # Shared types, constants
│
├── docker-compose.yml
├── .github/workflows/          # CI/CD
└── docs/                       # TZ, Architecture, Backlog
```
