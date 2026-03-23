# ESGvist — Error Model & Permission Policy

**Версия:** 1.0
**Дата:** 2026-03-22
**Статус:** Согласован

---

## 1. Error Model

### 1.1. Единый формат ошибки

Все API endpoints возвращают ошибки в едином формате:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "One or more fields are invalid.",
    "details": [
      {
        "field": "unitCode",
        "reason": "Unit is required for numeric value."
      },
      {
        "field": "dimensions[0].dimensionValue",
        "reason": "Dimension value is invalid for type 'scope'."
      }
    ],
    "requestId": "9d2d6e9d-5d7d-4d7d-9f8b-1fd8d2e0db3c"
  }
}
```

### 1.2. Поля error response

| Поле | Тип | Описание |
|------|-----|----------|
| `code` | string | Машиночитаемый код ошибки. Используется фронтом, логированием, автоматикой |
| `message` | string | Короткое человекочитаемое описание |
| `details` | array | Массив конкретных проблем (field + reason). Может быть пустым |
| `requestId` | string (UUID) | ID запроса для трассировки в логах |

### 1.3. Python типы (Pydantic)

```python
from pydantic import BaseModel


class ErrorDetail(BaseModel):
    field: str | None = None
    reason: str
    expected: str | None = None  # ожидаемое значение (опционально)


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] = []
    requestId: str


class ErrorResponse(BaseModel):
    error: ErrorBody
```

---

### 1.4. Стандартные error codes

#### Общие (HTTP-level)

| Code | HTTP Status | Описание |
|------|------------|----------|
| `BAD_REQUEST` | 400 | Запрос синтаксически или логически неверен |
| `VALIDATION_ERROR` | 400 | Одно или несколько полей невалидны |
| `UNAUTHORIZED` | 401 | Нет токена или токен невалидный |
| `FORBIDDEN` | 403 | Пользователь аутентифицирован, но не имеет прав |
| `NOT_FOUND` | 404 | Объект не найден |
| `CONFLICT` | 409 | Конфликт состояния |
| `RATE_LIMITED` | 429 | Превышен лимит запросов |
| `INTERNAL_ERROR` | 500 | Неожиданная серверная ошибка |

#### Доменные (бизнес-логика)

| Code | HTTP Status | Описание |
|------|------------|----------|
| `INVALID_WORKFLOW_TRANSITION` | 422 | Недопустимый переход статуса (например submitted → draft) |
| `DATA_POINT_LOCKED` | 422 | DataPoint заблокирован для редактирования (approved/submitted/in_review) |
| `REUSE_IDENTITY_MISMATCH` | 422 | Identity Rule не совпадает для reuse |
| `ASSIGNMENT_ROLE_CONFLICT` | 409 | Collector и reviewer совпадают |
| `MERGE_CONFIGURATION_INVALID` | 422 | Невалидная конфигурация merge |
| `COMPLETENESS_RECALCULATION_FAILED` | 500 | Ошибка при пересчёте completeness |
| `EXPORT_BLOCKED_BY_MISSING_REQUIREMENTS` | 422 | Экспорт невозможен: есть blocking issues |
| `STANDARD_ALREADY_ADDED` | 409 | Стандарт уже добавлен в проект |
| `BASE_STANDARD_REQUIRED` | 422 | Нужен хотя бы один базовый стандарт |
| `REVIEW_COMMENT_REQUIRED` | 422 | Комментарий обязателен при reject/needs_revision |
| `EVIDENCE_REQUIRED` | 422 | Требуется evidence для данного requirement_item |
| `STANDARD_IN_USE` | 409 | Стандарт нельзя удалить, есть привязанные данные |
| `PROJECT_LOCKED` | 422 | Проект в статусе review/published — редактирование заблокировано |
| `AI_RATE_LIMITED` | 429 | Превышен лимит AI-запросов для роли пользователя |
| `AI_TOOL_FORBIDDEN` | 403 | AI tool недоступен для роли пользователя |
| `AI_PROMPT_INJECTION` | 400 | Обнаружена попытка prompt injection |
| `AI_UNAVAILABLE` | 503 | AI сервис недоступен, используется fallback |
| `PLATFORM_ADMIN_REQUIRED` | 403 | Требуется роль platform_admin |
| `TENANT_SUSPENDED` | 403 | Tenant приостановлен — доступ заблокирован |
| `TENANT_ARCHIVED` | 410 | Tenant архивирован — данные read-only |
| `CANNOT_ASSIGN_PLATFORM_ROLE` | 403 | Tenant admin не может назначить platform_admin |
| `LAST_ADMIN_CANNOT_LEAVE` | 422 | Нельзя удалить единственного admin из tenant |
| `ORG_HEADER_REQUIRED` | 400 | Заголовок X-Organization-Id обязателен для tenant endpoints |

---

### 1.5. HTTP Status Mapping

| HTTP Status | Когда используется | Примеры |
|------------|-------------------|---------|
| **400** Bad Request | Запрос синтаксически неверен | Отсутствует обязательное поле, некорректный enum, invalid JSON |
| **401** Unauthorized | Нет/невалидный токен | Expired JWT, missing Authorization header |
| **403** Forbidden | Нет прав | Collector → merge view, auditor → approve, reviewer → edit standard |
| **404** Not Found | Объект не найден | projectId не существует, dataPointId не найден |
| **409** Conflict | Конфликт состояния | Стандарт уже в проекте, duplicate mapping, collector = reviewer |
| **422** Unprocessable Entity | Бизнес-валидация | Нельзя submit без required fields, нельзя approve без evidence |
| **429** Rate Limited | Слишком много запросов | > 100 req/min per user |
| **500** Internal Server Error | Непредвиденная ошибка | Database timeout, service crash |

---

### 1.6. Примеры доменных ошибок

#### Нельзя submit data point

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Data point cannot be submitted.",
    "details": [
      { "field": "unitCode", "reason": "Required for valueType=number." },
      { "field": "dimensions", "reason": "Missing required dimension 'scope'." }
    ],
    "requestId": "req_123"
  }
}
```

#### Нельзя approve без evidence

```json
{
  "error": {
    "code": "EVIDENCE_REQUIRED",
    "message": "This data point requires supporting evidence before approval.",
    "details": [
      { "field": "evidence", "reason": "At least one evidence is required (requires_evidence=true)." }
    ],
    "requestId": "req_124"
  }
}
```

#### Недопустимый workflow transition

```json
{
  "error": {
    "code": "INVALID_WORKFLOW_TRANSITION",
    "message": "Transition from 'submitted' to 'draft' is not allowed.",
    "details": [
      { "reason": "Allowed transitions from 'submitted': ['in_review']." }
    ],
    "requestId": "req_125"
  }
}
```

#### Collector и reviewer совпадают

```json
{
  "error": {
    "code": "ASSIGNMENT_ROLE_CONFLICT",
    "message": "Collector and reviewer cannot be the same person.",
    "details": [
      { "field": "collectorId", "reason": "Must differ from reviewerId." }
    ],
    "requestId": "req_126"
  }
}
```

#### DataPoint заблокирован

```json
{
  "error": {
    "code": "DATA_POINT_LOCKED",
    "message": "Cannot edit data point in status 'approved'.",
    "details": [
      { "reason": "Contact ESG manager to rollback status before editing." }
    ],
    "requestId": "req_127"
  }
}
```

#### Экспорт заблокирован

```json
{
  "error": {
    "code": "EXPORT_BLOCKED_BY_MISSING_REQUIREMENTS",
    "message": "Cannot generate report: 2 mandatory disclosures are missing.",
    "details": [
      { "field": "GRI 305-3", "reason": "Status: missing. No data submitted." },
      { "field": "GRI 401-1", "reason": "Status: partial. Evidence not attached." }
    ],
    "requestId": "req_128"
  }
}
```

---

### 1.7. OpenAPI reusable components

```yaml
components:
  schemas:
    ErrorResponse:
      type: object
      required: [error]
      properties:
        error:
          type: object
          required: [code, message, requestId]
          properties:
            code:
              type: string
              description: Machine-readable error code
              example: VALIDATION_ERROR
            message:
              type: string
              description: Human-readable error description
              example: One or more fields are invalid.
            details:
              type: array
              items:
                type: object
                properties:
                  field:
                    type: string
                    description: Field that caused the error
                  reason:
                    type: string
                    description: Explanation of the error
                  expected:
                    type: string
                    description: Expected value (optional)
            requestId:
              type: string
              format: uuid
              description: Request ID for tracing

  responses:
    BadRequest:
      description: Bad request
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
    Unauthorized:
      description: Unauthorized
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
    Forbidden:
      description: Forbidden
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
    NotFound:
      description: Not found
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
    Conflict:
      description: Conflict
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
    UnprocessableEntity:
      description: Business validation error
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
    InternalError:
      description: Internal server error
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
```

---

## 2. Permission Policy

### 2.1. Принцип: RBAC + Object-Level Checks

```
Layer 0: Platform Scope
         platform_admin — доступ ко всем tenants и platform endpoints

Layer 1: Role-Based Access Control (RBAC)
         Tenant-scoped роль определяет базовый доступ к endpoint

Layer 2: Object-Level Checks
         Дополнительная проверка по объекту:
         - assignment принадлежит пользователю
         - project в нужном статусе
         - организация совпадает (tenant isolation)
```

> **Полная модель ролей:** см. TZ-PlatformAdmin.md — scope-aware role_bindings, JWT без роли, X-Organization-Id header.

---

### 2.2. Общие правила по ролям

#### platform_admin (platform scope)

**Полный доступ на уровне платформы:**
- создание / управление tenants
- назначение tenant admins
- просмотр всех организаций
- platform-level settings
- support override (с audit log)

**Не является рабочей tenant-ролью.** Подробнее: TZ-PlatformAdmin.md.

#### admin (level 100, tenant scope)

**Полный доступ внутри своей организации:**
- standards, sections, disclosure requirements, requirement items
- shared elements, mappings
- users, assignments
- merge, projects, audit, settings

**Ограничения:**
- approve/reject как override action (с audit log)
- **не может** создавать tenants, видеть другие организации

#### esg_manager (level 80)

**Доступ к:**
- projects (CRUD), assignments (CRUD), merge view (full)
- completeness, readiness check, exports
- impact preview, project workflow transitions
- read access к data points
- rollback approved → draft (с обоснованием)

**Не может:**
- менять структуру стандартов, mapping, disclosure catalog

#### collector (level 40)

**Доступ к:**
- свои assignments, свои data points
- create/update draft, submit
- upload evidence (файлы/ссылки)
- read/reply comments

**Не может:**
- approve/reject
- видеть merge view
- менять assignments, проект, стандарты

#### reviewer (level 60)

**Доступ к:**
- review queue (assigned data points)
- approve/reject/request revision
- comments, read merge view, read completeness (assigned scope)

**Не может:**
- редактировать data points как collector
- менять structure/catalog, назначать пользователей, публиковать

#### auditor (level 20)

**Read-only доступ к:**
- projects, data points, merge view, completeness
- audit log, comments, exports

**Не может:**
- submit, approve/reject, edit anything

---

### 2.3. Endpoint-Level Permission Matrix

#### Standards / Catalog

| Endpoint | admin | esg_manager | collector | reviewer | auditor |
|----------|:---:|:---:|:---:|:---:|:---:|
| `GET /standards` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `POST /standards` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `PATCH /standards/:id` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `GET /standards/:id/sections` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `POST /disclosure-requirements` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `POST /disclosures/:id/items` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `PATCH /requirement-items/:id` | ✅ | ❌ | ❌ | ❌ | ❌ |

#### Shared Layer / Mapping

| Endpoint | admin | esg_manager | collector | reviewer | auditor |
|----------|:---:|:---:|:---:|:---:|:---:|
| `GET /shared-elements` | ✅ | ✅ | ⚠️ assigned | ✅ | ✅ |
| `POST /shared-elements` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `PATCH /shared-elements/:id` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `GET /items/:id/mappings` | ✅ | ✅ | ❌ | ✅ | ✅ |
| `POST /items/:id/mappings` | ✅ | ❌ | ❌ | ❌ | ❌ |

#### Projects / Assignments

| Endpoint | admin | esg_manager | collector | reviewer | auditor |
|----------|:---:|:---:|:---:|:---:|:---:|
| `GET /projects` | ✅ | ✅ | ⚠️ assigned | ⚠️ assigned | ✅ |
| `POST /projects` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `PATCH /projects/:id` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `PUT /projects/:id/standards` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `GET /projects/:id/assignments` | ✅ | ✅ | ⚠️ own | ⚠️ own review | ✅ |
| `POST /projects/:id/assignments` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `PATCH /assignments/:id` | ✅ | ✅ | ❌ | ❌ | ❌ |

#### Data Points

| Endpoint | admin | esg_manager | collector | reviewer | auditor |
|----------|:---:|:---:|:---:|:---:|:---:|
| `GET /projects/:id/data-points` | ✅ | ✅ | ⚠️ own/assigned | ⚠️ assigned review | ✅ |
| `POST /projects/:id/data-points` | ✅ | ✅ | ⚠️ assigned | ❌ | ❌ |
| `PATCH /data-points/:id` | ✅ | ⚠️ limited | ⚠️ own + draft/revision | ❌ | ❌ |
| `GET /data-points/:id` | ✅ | ✅ | ⚠️ own | ⚠️ assigned | ✅ |
| `GET /data-points/find-reuse` | ✅ | ✅ | ⚠️ own draft | ❌ | ❌ |
| `POST /data-points/:id/submit` | ✅ | ✅ | ⚠️ own draft | ❌ | ❌ |
| `POST /data-points/:id/evidences` | ✅ | ✅ | ⚠️ own editable | ❌ | ❌ |

#### Review

| Endpoint | admin | esg_manager | collector | reviewer | auditor |
|----------|:---:|:---:|:---:|:---:|:---:|
| `GET /review/queue` | ✅ | ✅ | ❌ | ✅ | ❌ |
| `POST /review/:id/approve` | ⚠️ override | ❌ | ❌ | ⚠️ assigned | ❌ |
| `POST /review/:id/reject` | ⚠️ override | ❌ | ❌ | ⚠️ assigned | ❌ |
| `POST /review/:id/request-revision` | ⚠️ override | ❌ | ❌ | ⚠️ assigned | ❌ |
| `POST /comments` | ✅ | ✅ | ⚠️ own scope | ⚠️ assigned | ❌ |

#### Merge / Completeness / Reporting

| Endpoint | admin | esg_manager | collector | reviewer | auditor |
|----------|:---:|:---:|:---:|:---:|:---:|
| `GET /projects/:id/merge` | ✅ | ✅ | ❌ | ✅ RO | ✅ RO |
| `POST /projects/:id/merge/preview` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `GET /projects/:id/completeness` | ✅ | ✅ | ⚠️ own scope | ⚠️ assigned | ✅ |
| `POST /projects/:id/completeness/recalculate` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `GET /projects/:id/readiness-check` | ✅ | ✅ | ❌ | ✅ RO | ✅ RO |
| `POST /projects/:id/exports` | ✅ | ✅ | ❌ | ❌ | ⚠️ RO export |

#### Admin / Users

| Endpoint | admin | esg_manager | collector | reviewer | auditor |
|----------|:---:|:---:|:---:|:---:|:---:|
| `GET /admin/users` | ✅ | ⚠️ limited | ❌ | ❌ | ❌ |
| `POST /admin/users` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `PATCH /admin/users/:id` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `GET /audit-log` | ✅ | ✅ | ❌ | ❌ | ✅ |

**Легенда:**
- ✅ — полный доступ
- ❌ — нет доступа
- ⚠️ — условный доступ (object-level check)
- RO — read-only

---

### 2.4. Object-Level Permission Rules

```python
# app/policies/auth_policy.py

# Rule 1: Tenant isolation
def check_tenant_isolation(user, resource) -> bool:
    return user.organization_id == resource.organization_id

# Rule 2: Collector ownership
def can_collector_edit_data_point(user, data_point, assignment) -> bool:
    return (
        user.role == "collector"
        and assignment.collector_id == user.id
        and data_point.status in ("draft", "rejected", "needs_revision")
    )

# Rule 3: Reviewer scope
def can_reviewer_approve(user, data_point, assignment) -> bool:
    return (
        user.role == "reviewer"
        and assignment.reviewer_id == user.id
        and data_point.status in ("submitted", "in_review")
    )

# Rule 4: Merge visibility
def can_view_merge(user) -> bool:
    return user.role in ("admin", "esg_manager", "reviewer", "auditor")

# Rule 5: Project lock
def can_edit_in_project(user, project) -> bool:
    if project.status == "published":
        return user.role == "admin"  # override only
    if project.status == "review":
        return user.role in ("admin", "esg_manager")
    return True

# Rule 6: Approved lock
def can_edit_approved_data_point(user) -> bool:
    return user.role in ("admin", "esg_manager")
    # ESG-manager must explicitly rollback status first
```

---

### 2.5. Policy Layer Implementation

**Рекомендуемый подход:** централизованный policy layer, не разбросанный по контроллерам.

```python
# app/core/permissions.py
from dataclasses import dataclass, field
from typing import Callable
from app.core.exceptions import AppError


@dataclass
class PermissionCheck:
    roles: list[str]
    object_rules: list[Callable] = field(default_factory=list)


PERMISSIONS: dict[str, PermissionCheck] = {
    "POST /standards": PermissionCheck(
        roles=["admin"],
    ),
    "GET /projects/{id}/merge": PermissionCheck(
        roles=["admin", "esg_manager", "reviewer", "auditor"],
        object_rules=[check_tenant_isolation],
    ),
    "POST /data-points/{id}/submit": PermissionCheck(
        roles=["admin", "esg_manager", "collector"],
        object_rules=[check_tenant_isolation, can_collector_edit_data_point],
    ),
    "POST /review/{id}/approve": PermissionCheck(
        roles=["admin", "reviewer"],
        object_rules=[check_tenant_isolation, can_reviewer_approve],
    ),
}


# Usage as FastAPI dependency
async def authorize(endpoint: str, user, resource=None):
    permission = PERMISSIONS.get(endpoint)
    if not permission:
        raise AppError("FORBIDDEN", 403, "Access denied")

    # Layer 1: Role check
    if user.role not in permission.roles:
        raise AppError("FORBIDDEN", 403, "Access denied")

    # Layer 2: Object-level checks
    if resource and permission.object_rules:
        for rule in permission.object_rules:
            if not rule(user, resource):
                raise AppError("FORBIDDEN", 403, "Access denied")
```

> **Подробная реализация policy layer** — см. TZ-BackendArchitecture.md раздел 5.6.

---

### 2.6. JWT Claims

```python
# app/core/security.py
from pydantic import BaseModel


class JWTPayload(BaseModel):
    sub: int                  # user.id
    email: str
    role: str                 # 'admin' | 'esg_manager' | 'collector' | 'reviewer' | 'auditor'
    organization_id: int
    iat: int                  # issued at
    exp: int                  # expiration
```

---

### 2.7. OpenAPI x-permissions extension

```yaml
/projects/{projectId}/merge:
  get:
    tags: [Merge]
    summary: Get merge view for project
    x-permissions:
      roles: [admin, esg_manager, reviewer, auditor]
      objectRules:
        - user.organizationId == project.organizationId
        - collector role is not allowed

/data-points/{dataPointId}/submit:
  post:
    tags: [Data Points]
    summary: Submit data point for review
    x-permissions:
      roles: [admin, esg_manager, collector]
      objectRules:
        - user.organizationId == dataPoint.organizationId
        - collector must own assignment
        - dataPoint.status in [draft, rejected, needs_revision]
```

---

## 3. Summary

Документ фиксирует два критических слоя для backend implementation:

| Слой | Что определяет |
|------|---------------|
| **Error Model** | Единый формат ошибок (code + message + details + requestId), 13 общих + доменных кодов, HTTP status mapping, reusable OpenAPI components |
| **Permission Policy** | RBAC (5 ролей) + object-level checks (6 правил), endpoint-level matrix (~40 endpoints), centralized policy layer, JWT claims |

**Связь с другими документами:**
- Роли → TZ-ESGvist-v1 раздел 6
- Workflow transitions → ARCHITECTURE.md раздел 3.5
- Error codes → соответствуют бизнес-правилам из всех TZ документов
