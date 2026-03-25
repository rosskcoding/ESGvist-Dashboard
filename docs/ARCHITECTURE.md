# ESGvist — System Architecture

**Версия:** 2.0
**Дата:** 2026-03-22
**Статус:** Согласован (стек утверждён)

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

## 2. Technology Stack

**Статус:** Согласован (2026-03-22)

### 2.1. Backend (Python)

| Layer | Technology | Версия | Обоснование |
|-------|-----------|--------|-------------|
| **Framework** | FastAPI | 0.110+ | Async, типизация, auto-docs (OpenAPI), DI через Depends() |
| **ORM** | SQLAlchemy 2.0 (async) | 2.0+ | Mature, async support, CTE, window functions, raw SQL |
| **Migrations** | Alembic | 1.13+ | Стандарт для SQLAlchemy, autogenerate |
| **Validation** | Pydantic v2 | 2.6+ | Нативная интеграция с FastAPI, JSON Schema |
| **Auth** | python-jose + passlib | — | JWT (access 15min + refresh 7d) + bcrypt; SSO (SAML/OAuth) в Phase 3 |
| **DB Driver** | asyncpg | 0.29+ | Async PostgreSQL driver, высокая производительность |
| **File Storage** | aioboto3 | — | Async S3/MinIO client |
| **Background Tasks** | arq (MVP) → Celery (Phase 2+) | — | Redis-based task queue |
| **Event Bus** | In-process (MVP) → Redis Pub/Sub (Phase 2) | — | Простота MVP; Redis при необходимости масштабирования |
| **Logging** | structlog | 24.1+ | Structured JSON logs |
| **Linting** | ruff | 0.3+ | Fast Python linter + formatter (заменяет black + isort + flake8) |
| **Type Checking** | mypy | 1.8+ | Static type checking |
| **Testing** | pytest + pytest-asyncio + httpx | — | Async test support, API integration tests |

### 2.2. Frontend (TypeScript)

| Layer | Technology | Версия | Обоснование |
|-------|-----------|--------|-------------|
| **Framework** | React + Next.js (App Router) | 14+ | File-based routing, layouts, loading states |
| **Language** | TypeScript | 5.3+ | Типизация, developer experience |
| **Styling** | Tailwind CSS | 3.4+ | Utility-first, быстрая разработка |
| **UI Kit** | shadcn/ui | — | Копируемые компоненты, Tailwind-native, полный контроль, a11y |
| **Server State** | TanStack Query (React Query) | 5+ | Кэширование, invalidation, optimistic updates |
| **Client State** | Zustand | 4+ | UI state (sidebar, filters, modals), минимальный boilerplate |
| **Forms** | React Hook Form + Zod | — | Производительность, Zod resolver для единой валидации |
| **Tables** | TanStack Table | 8+ | Collection Table, Assignments Matrix, Review queue — headless |
| **Tree / Graph** | React Flow | 11+ | Company Structure визуализация (ownership, control, boundary) |
| **Charts** | Recharts | 2+ | Dashboard (completion bars, heatmaps, coverage charts) |
| **Testing** | Vitest + Playwright | — | Vitest для unit/integration (3-5x быстрее Jest), Playwright для E2E |

### 2.3. Infrastructure

| Layer | Technology | Обоснование |
|-------|-----------|-------------|
| **API** | REST (JSON) | Простота, достаточно для MVP; OpenAPI auto-docs через FastAPI |
| **DB** | PostgreSQL 16 | JSONB, CTE, window functions, GIN indexes, partial indexes |
| **File Storage** | MinIO (dev) / S3 (prod) | S3-совместимый API, self-hosted для dev |
| **Cache / Queue** | Redis | Сессии (Phase 2), очереди задач (arq), кэш |
| **CI/CD** | GitHub Actions | Lint + test + build на каждый PR |
| **Dev** | Docker Compose | PostgreSQL + MinIO + Redis + API + Web — одной командой |
| **Prod (MVP)** | Single VPS + Docker Compose + Nginx | Достаточно для single-tenant, 5-20 пользователей |
| **Prod (Phase 3)** | AWS: ECS + RDS + S3 + ElastiCache | Масштабирование |

### 2.4. Monorepo

| Компонент | Технология | Обоснование |
|-----------|-----------|-------------|
| **Package Manager** | pnpm | Быстрее npm, workspace support (для frontend/TS) |
| **Monorepo** | Turborepo | Кэширование сборок, параллельные таски (только frontend) |
| **Python Backend** | отдельно в том же репо | Poetry/uv для зависимостей, не входит в Turborepo pipeline |

> **Архитектурные требования к backend** — см. TZ-BackendArchitecture.md (слоение, DI, events, policies, workflows).

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
- CRUD для `methodologies`, `boundaries`, `source_records`

> **Evidence модуль** вынесен в отдельный сервис — см. TZ-Evidence.md (evidences, evidence_files, evidence_links, data_point_evidences, requirement_item_evidences).
- **Identity Rule** — определение reuse
- Binding management (`requirement_item_data_points`)

**Identity Rule (reuse detection):**

```python
@dataclass
class IdentityKey:
    shared_element_id: int
    organization_id: int
    reporting_period_id: int
    unit_code: str
    boundary_id: int | None
    methodology_id: int | None
    entity_id: int | None          # company entity scope
    facility_id: int | None        # facility scope
    dimensions: dict[str, str]     # полный match


async def find_reusable_data_point(key: IdentityKey) -> DataPoint | None:
    """Поиск существующего DataPoint с идентичными параметрами.
    Если найден → предложить reuse.
    Если не найден → создать новый.
    """
    ...
```

**Правила:**
- Если все 9 параметров совпадают → reuse (создаётся binding, не DataPoint)
- Если хотя бы один отличается → новый DataPoint
- При редактировании multi-bound DataPoint → warning с impact list

**API endpoints:**
```
GET/POST       /api/data-points
GET/PUT        /api/data-points/:id
GET/POST       /api/data-points/:id/dimensions
GET            /api/data-points/find-reuse?...   — поиск по Identity Rule
POST           /api/data-points/:id/bind         — создать binding
GET/POST       /api/evidences                 — CRUD evidence (file/link)
POST           /api/data-points/:id/evidences  — привязать evidence к data point
```

**Events emitted:**
- `DataPointCreated`
- `DataPointUpdated` → triggers Completeness Engine
- `DataPointBound` → triggers Completeness Engine
- `EvidenceCreated`
- `EvidenceLinkedToDP`

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

```python
# app/domain/workflow_state.py

TRANSITIONS: dict[str, list[dict]] = {
    "draft":           [{"to": "submitted",      "roles": ["collector", "esg_manager"]}],
    "submitted":       [{"to": "in_review",      "roles": ["system"]}],
    "in_review":       [{"to": "approved",       "roles": ["reviewer", "esg_manager"]},
                        {"to": "rejected",        "roles": ["reviewer", "esg_manager"], "require_comment": True},
                        {"to": "needs_revision",  "roles": ["reviewer", "esg_manager"], "require_comment": True}],
    "approved":        [{"to": "draft",           "roles": ["esg_manager"], "require_comment": True}],
    "rejected":        [{"to": "submitted",       "roles": ["collector"]}],
    "needs_revision":  [{"to": "submitted",       "roles": ["collector"]}],
}
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

```python
# app/services/completeness_service.py

async def calculate_item_status(
    self,
    project_id: int,
    requirement_item_id: int,
) -> str:  # 'missing' | 'partial' | 'complete' | 'not_applicable'

    # 1. Find bindings
    bindings = await self.binding_repo.find_by_project_and_item(
        project_id, requirement_item_id
    )
    if not bindings:
        return "missing"

    # 2. Check data_point status
    data_points = await self.data_point_repo.get_by_ids(
        [b.data_point_id for b in bindings]
    )
    has_approved = any(dp.status == "approved" for dp in data_points)
    if not has_approved:
        return "partial"  # data exists but not approved

    # 3. Check dimension rules
    item = await self.requirement_item_repo.get_by_id(requirement_item_id)
    if not await self._check_dimension_rules(item.granularity_rule, data_points):
        return "partial"

    # 4. Check evidence (if requires_evidence or item_type = 'document')
    if item.requires_evidence or item.item_type == "document":
        evidence_count = await self.evidence_repo.count_for_item(
            requirement_item_id, [b.data_point_id for b in bindings]
        )
        if evidence_count == 0:
            return "partial"

    # 5. Check validation rules
    if not await self._check_validation_rules(item.validation_rule, data_points):
        return "partial"

    return "complete"


async def aggregate_disclosure_status(
    self,
    project_id: int,
    disclosure_id: int,
) -> dict:  # {"status": str, "completion_percent": float}

    items = await self.requirement_item_repo.find_required_by_disclosure(disclosure_id)

    statuses = []
    for item in items:
        status = await self.status_repo.get_item_status(project_id, item.id)
        statuses.append(status)

    complete = sum(1 for s in statuses if s and s.status == "complete")
    total = sum(1 for s in statuses if not s or s.status != "not_applicable")

    if total == 0:
        return {"status": "complete", "completion_percent": 100.0}

    return {
        "status": "complete" if complete == total else ("partial" if complete > 0 else "missing"),
        "completion_percent": (complete / total) * 100,
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
MVP: In-process async event bus (Python asyncio, same FastAPI process)
Phase 2: Redis Pub/Sub for cross-process events
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

```python
# app/events/types.py

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class DomainEvent:
    timestamp: datetime = field(default_factory=datetime.utcnow)

# Data Point events
@dataclass
class DataPointCreated(DomainEvent):
    data_point_id: int = 0
    project_id: int = 0

@dataclass
class DataPointUpdated(DomainEvent):
    data_point_id: int = 0
    changed_fields: list[str] = field(default_factory=list)

@dataclass
class DataPointSubmitted(DomainEvent):
    data_point_id: int = 0
    submitted_by: int = 0

@dataclass
class DataPointApproved(DomainEvent):
    data_point_id: int = 0
    reviewed_by: int = 0

@dataclass
class DataPointRejected(DomainEvent):
    data_point_id: int = 0
    reviewed_by: int = 0
    comment: str = ""

@dataclass
class DataPointRolledBack(DomainEvent):
    data_point_id: int = 0
    rolled_back_by: int = 0
    reason: str = ""

@dataclass
class DataPointBound(DomainEvent):
    data_point_id: int = 0
    requirement_item_id: int = 0
    project_id: int = 0

# Standard / Mapping events
@dataclass
class StandardAdded(DomainEvent):
    project_id: int = 0
    standard_id: int = 0

@dataclass
class StandardRemoved(DomainEvent):
    project_id: int = 0
    standard_id: int = 0

@dataclass
class MappingChanged(DomainEvent):
    mapping_id: int = 0
    change_type: str = ""  # 'created' | 'updated' | 'deleted'

@dataclass
class MergeCompleted(DomainEvent):
    project_id: int = 0

@dataclass
class RequirementItemChanged(DomainEvent):
    item_id: int = 0
    changed_fields: list[str] = field(default_factory=list)

# Assignment / SLA events
@dataclass
class AssignmentCreated(DomainEvent):
    assignment_id: int = 0
    collector_id: int = 0

@dataclass
class DeadlineApproaching(DomainEvent):
    assignment_id: int = 0
    days_remaining: int = 0

@dataclass
class SLABreached(DomainEvent):
    assignment_id: int = 0
    level: int = 1  # 1 or 2
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
│ data_points ← data_point_evidences ← evidences       │
│                                      ← evidence_files│
│                                      ← evidence_links│
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
  browser auth:
    access_token + refresh_token → HttpOnly cookies
    csrf_token → readable cookie mirrored into X-CSRF-Token
    Origin / Referer / Sec-Fetch-Site enforced for unsafe cookie-auth requests
    access_token: 15 min TTL
    refresh_token: 7 days TTL
    refresh sessions persisted server-side with immediate revoke via session binding
  API / integration auth:
    Authorization: Bearer remains supported for tests, API clients and non-browser callers
    bearer requests do not require CSRF
    browser routes should prefer cookie-first auth

Phase 3:
  + SSO (SAML 2.0 / OAuth 2.0)
  + 2FA (TOTP)
```

**Supported auth modes:**

- `Browser session mode` is the default for the Next.js UI. Tokens stay in cookies, refresh rotation is server-side, and unsafe requests must pass CSRF plus trusted-origin checks.
- `Bearer mode` is intentionally still supported for automated clients, selected backend tests and non-browser integrations. This is an explicit dual-mode model, not an accident.
- New unsafe browser-facing endpoints must be designed for cookie-auth first and must not be added to the CSRF exempt allowlist unless they are true auth bootstrap paths (`login`, `register`, SSO start/callback).

**Support mode rules:**

- `support_session_id` is a server-issued cookie; the UI treats `/api/platform/support-session/current` as the source of truth.
- Client-side support-mode cache is best-effort UI state only and is cleared when the backend no longer confirms the session.
- While support mode is active, tenant-scoped platform routes such as `/api/platform/tenants/{tenant_id}/...` must stay pinned to the support tenant. Crossing tenants requires ending the support session first.

### 7.2. Authorization (RBAC)

```python
# app/domain/roles.py

ROLES = {
    "admin":       {"level": 100, "description": "Full system access"},
    "esg_manager": {"level": 80,  "description": "Project + assignment + publish"},
    "reviewer":    {"level": 60,  "description": "Review + approve/reject"},
    "collector":   {"level": 40,  "description": "Data entry (assigned only)"},
    "auditor":     {"level": 20,  "description": "Read-only + audit log"},
}
```

**Row-level security:**
- Collector sees only assigned metrics (`metric_assignments.collector_id = user.id`)
- Reviewer sees only assigned reviews (`metric_assignments.reviewer_id = user.id`)
- ESG-manager sees all project data
- Auditor sees all data (read-only)

> **Подробная реализация RBAC + object-level policies** — см. TZ-BackendArchitecture.md раздел 5.6 и ERROR-MODEL.md раздел 2.

### 7.3. API security

- HTTPS only (TLS 1.3)
- CORS whitelist
- Rate limiting: 100 req/min per user
- Input validation: Pydantic v2 schemas on all endpoints
- SQL injection: SQLAlchemy parameterized queries
- File upload: type + size validation, virus scan (Phase 3)

---

## 8. Deployment Architecture

### 8.1. MVP (single server)

```
┌────────────────────────────────────────┐
│            Docker Compose              │
│                                        │
│  ┌──────────┐  ┌──────────┐           │
│  │ Next.js  │  │ FastAPI  │           │
│  │ Frontend │  │ API      │           │
│  │ :3000    │  │ :8000    │           │
│  └──────────┘  └──────────┘           │
│                                        │
│  ┌──────────┐  ┌──────────┐           │
│  │ Postgres │  │  MinIO   │           │
│  │ :5432    │  │  :9000   │           │
│  └──────────┘  └──────────┘           │
│                                        │
│  ┌──────────┐  ┌──────────┐           │
│  │  Redis   │  │  Nginx   │           │
│  │  :6379   │  │  :443    │           │
│  └──────────┘  └──────────┘           │
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

- Structured JSON logs (structlog)
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

## 10. Folder Structure

```
esgvist/
├── backend/                         # Python (FastAPI)
│   ├── app/
│   │   ├── api/                     # HTTP layer (routers)
│   │   │   └── routes/
│   │   │       ├── auth.py
│   │   │       ├── standards.py
│   │   │       ├── disclosures.py
│   │   │       ├── shared_elements.py
│   │   │       ├── data_points.py
│   │   │       ├── evidence.py
│   │   │       ├── review.py
│   │   │       ├── projects.py
│   │   │       ├── assignments.py
│   │   │       ├── entities.py      # company structure
│   │   │       ├── boundaries.py    # boundary management
│   │   │       ├── merge.py
│   │   │       ├── completeness.py
│   │   │       ├── reporting.py
│   │   │       ├── notifications.py
│   │   │       └── audit.py
│   │   ├── schemas/                 # Pydantic DTOs
│   │   ├── domain/                  # Business entities & invariants
│   │   ├── services/                # Business logic
│   │   ├── repositories/            # Data access (SQLAlchemy)
│   │   ├── policies/                # Access rules & validations
│   │   ├── workflows/               # Multi-step processes
│   │   ├── events/                  # Event bus + handlers
│   │   ├── infrastructure/          # S3, email, queue
│   │   ├── db/
│   │   │   ├── models/              # SQLAlchemy ORM models
│   │   │   ├── migrations/          # Alembic migrations
│   │   │   └── seed/                # Seed data
│   │   ├── core/                    # Config, security, DI, exceptions
│   │   └── main.py                  # FastAPI app factory
│   ├── tests/
│   ├── pyproject.toml               # Poetry/uv dependencies
│   └── alembic.ini
│
├── frontend/                        # TypeScript (Next.js)
│   ├── app/                         # App Router pages
│   │   ├── (auth)/                  # Login, register
│   │   ├── dashboard/               # Overview
│   │   ├── collection/              # Data entry + wizard
│   │   ├── validation/              # Review split panel
│   │   ├── merge/                   # Merge View
│   │   ├── report/                  # Export + readiness check
│   │   ├── evidence/                # Evidence repository
│   │   └── settings/
│   │       ├── standards/           # Standard catalog
│   │       ├── company-structure/   # Company Structure & Boundary
│   │       ├── assignments/         # Assignment matrix
│   │       ├── projects/            # Project settings
│   │       └── users/               # User management
│   ├── components/
│   │   ├── ui/                      # shadcn/ui components
│   │   ├── layout/                  # Topbar, sidebar, context bar
│   │   ├── tables/                  # TanStack Table wrappers
│   │   ├── tree/                    # Recursive tree component
│   │   ├── graph/                   # React Flow wrappers
│   │   └── charts/                  # Recharts wrappers
│   ├── lib/
│   │   ├── api/                     # API client (fetch + React Query)
│   │   ├── hooks/                   # Custom hooks
│   │   ├── stores/                  # Zustand stores
│   │   └── utils/                   # Helpers
│   ├── package.json
│   └── tsconfig.json
│
├── packages/
│   └── shared/                      # Shared types, constants, Zod schemas
│
├── docker-compose.yml               # PostgreSQL + MinIO + Redis + API + Web
├── docker-compose.prod.yml
├── turbo.json                       # Turborepo config (frontend only)
├── pnpm-workspace.yaml              # pnpm workspaces (frontend + packages)
├── .github/workflows/               # CI/CD
│   ├── backend.yml                  # Python: ruff + mypy + pytest
│   ├── frontend.yml                 # TS: lint + vitest + build
│   └── e2e.yml                      # Playwright E2E
└── docs/                            # TZ, Architecture, Backlog
```

> **Подробная структура backend** — см. TZ-BackendArchitecture.md раздел 4.

---

## 11. Связь с документацией

| Документ | Описание |
|----------|----------|
| **TZ-ESGvist-v1.md** | Полное ТЗ: PostgreSQL-схема (40+ таблиц), бизнес-правила |
| **TZ-BackendArchitecture.md** | Layered architecture (FastAPI): routers, services, repos, policies, workflows, events |
| **TZ-PlatformAdmin.md** | Platform admin, role_bindings, tenant management, scope-aware roles |
| **TZ-PermissionMatrix.md** | Master Role & Permission Matrix (16 матриц, 6 ролей) |
| **TZ-WorkflowGateMatrix.md** | Gate Engine: 26 gate codes, transitions для всех сущностей |
| **TZ-CompanyStructure.md** | Company Structure & Boundary Manager: entities, ownership, control, boundary |
| **TZ-BoundaryIntegration.md** | Интеграция boundary со всеми экранами (10 экранов) |
| **TZ-OrgSetup.md** | Onboarding: Organization Setup Wizard (5 шагов) |
| **TZ-AIAssistance.md** | AI Layer: explain, copilot, review assist, 8 AI Gates |
| **TZ-Evidence.md** | Evidence модуль: evidences, files, links, привязки M:N, requires_evidence |
| **TZ-Admin.md** | ТЗ администратора: стандарты, shared elements, mapping, impact analysis |
| **TZ-ESGManager.md** | ТЗ ESG-менеджера: проекты, assignments, мониторинг, SLA, export |
| **TZ-Reviewer.md** | ТЗ ревьюера: split panel, approve/reject, batch, threaded comments |
| **TZ-User.md** | ТЗ сборщика: ввод данных, reuse, дельты, workflow |
| **TZ-Notifications.md** | Notifications & Events: in-app, email, webhooks (Phase 2) |
| **TZ-NFR.md** | Non-Functional Requirements: latency SLA, security, observability |
| **ERROR-MODEL.md** | Unified error model + Permission Policy (RBAC + object-level) |
| **SPRINT-PLAN.md** | 22 спринта, 3 фазы, ~970 SP |
| **BACKLOG.md** | 8+ эпиков, 22+ фич, ~80+ тасок |
