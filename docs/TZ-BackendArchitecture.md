# ТЗ: Архитектурные требования к backend (FastAPI)

**Модуль:** Backend Architecture
**Версия:** 1.0
**Дата:** 2026-03-22
**Статус:** Согласован

---

## 1. Цель

Обеспечить единообразную, масштабируемую и поддерживаемую архитектуру backend-системы на базе **FastAPI**, исключающую хаотичную организацию кода и обеспечивающую:

- чёткое разделение ответственности;
- предсказуемую структуру проекта;
- изоляцию доменной логики от API;
- возможность масштабирования команды и функционала;
- соответствие enterprise-level требованиям к ESG-системе.

---

## 2. Область применения

Требования распространяются на:

- все backend-сервисы системы;
- все доменные модули (projects, data-points, evidence, org-boundary и др.);
- все новые и существующие endpoints;
- все workflow и background процессы.

---

## 3. Основные принципы архитектуры

### 3.1. API ≠ бизнес-логика

FastAPI используется **только** как слой доставки (delivery layer):

- маршруты (routers) **не содержат** бизнес-логики;
- вся бизнес-логика реализуется в service/domain слоях.

### 3.2. Обязательное слоение архитектуры

Система должна быть разделена на следующие слои:

| Слой | Назначение |
|------|-----------|
| **API (routers)** | HTTP endpoints |
| **Schemas** | DTO / Pydantic модели |
| **Services** | Бизнес-логика |
| **Domain** | Доменные правила и модели |
| **Repositories** | Доступ к данным |
| **Policies** | Правила доступа и валидации |
| **Workflows** | Сложные бизнес-процессы |
| **Events** | События системы |

### 3.3. Dependency direction (направление зависимостей)

**Разрешённые зависимости:**

```
API → Services → Domain
                → Repositories → DB
Services → Policies
Services → Workflows
Workflows → Services
Events → Services (через handlers)
```

**Запрещено:**

- Domain → API
- Repositories → Services
- API → DB напрямую
- API → Domain напрямую (без service слоя)

```
                    ┌─────────┐
                    │   API   │ (routers)
                    └────┬────┘
                         │ вызывает
                    ┌────▼────┐
              ┌─────│ Services│─────┐
              │     └────┬────┘     │
              │          │          │
         ┌────▼───┐ ┌───▼────┐ ┌───▼──────┐
         │Policies│ │ Domain │ │Workflows │
         └────────┘ └────────┘ └──────────┘
                         │
                  ┌──────▼──────┐
                  │Repositories │
                  └──────┬──────┘
                         │
                    ┌────▼────┐
                    │   DB    │
                    └─────────┘
```

---

## 4. Структура проекта

### 4.1. Общая структура

```
app/
├── api/                          # HTTP layer
│   └── routes/
│       ├── __init__.py
│       ├── auth.py
│       ├── standards.py
│       ├── disclosures.py
│       ├── shared_elements.py
│       ├── data_points.py
│       ├── evidence.py
│       ├── review.py
│       ├── projects.py
│       ├── assignments.py
│       ├── entities.py           # company structure
│       ├── boundaries.py         # boundary management
│       ├── merge.py
│       ├── completeness.py
│       ├── reporting.py
│       ├── notifications.py
│       └── audit.py
│
├── schemas/                      # Pydantic DTOs
│   ├── __init__.py
│   ├── auth.py
│   ├── standards.py
│   ├── data_points.py
│   ├── evidence.py
│   ├── review.py
│   ├── projects.py
│   ├── entities.py
│   ├── boundaries.py
│   ├── merge.py
│   ├── completeness.py
│   ├── common.py                 # ErrorResponse, ListMeta, pagination
│   └── events.py
│
├── domain/                       # Business entities & rules
│   ├── __init__.py
│   ├── standard.py
│   ├── disclosure.py
│   ├── requirement_item.py
│   ├── shared_element.py
│   ├── data_point.py
│   ├── evidence.py
│   ├── company_entity.py
│   ├── ownership.py
│   ├── boundary.py
│   ├── assignment.py
│   ├── workflow_state.py         # state machine definitions
│   └── identity_rule.py          # reuse detection
│
├── services/                     # Business operations
│   ├── __init__.py
│   ├── auth_service.py
│   ├── standard_service.py
│   ├── mapping_service.py
│   ├── data_point_service.py
│   ├── evidence_service.py
│   ├── review_service.py
│   ├── project_service.py
│   ├── assignment_service.py
│   ├── entity_service.py
│   ├── boundary_service.py
│   ├── merge_service.py
│   ├── completeness_service.py
│   ├── reporting_service.py
│   ├── notification_service.py
│   └── audit_service.py
│
├── repositories/                 # Data access
│   ├── __init__.py
│   ├── base.py                   # BaseRepository with common CRUD
│   ├── standard_repo.py
│   ├── disclosure_repo.py
│   ├── requirement_item_repo.py
│   ├── shared_element_repo.py
│   ├── data_point_repo.py
│   ├── evidence_repo.py
│   ├── project_repo.py
│   ├── assignment_repo.py
│   ├── entity_repo.py
│   ├── boundary_repo.py
│   ├── user_repo.py
│   ├── notification_repo.py
│   └── audit_repo.py
│
├── policies/                     # Access rules & business validations
│   ├── __init__.py
│   ├── auth_policy.py            # role checks, tenant isolation
│   ├── data_point_policy.py      # can_edit, can_submit, is_locked
│   ├── review_policy.py          # can_approve, can_reject, requires_comment
│   ├── evidence_policy.py        # requires_evidence, can_delete_evidence
│   ├── boundary_policy.py        # boundary_inclusion_check, snapshot_immutable
│   ├── project_policy.py         # project_locked, can_publish
│   ├── assignment_policy.py      # collector_reviewer_conflict
│   └── standard_policy.py        # can_deactivate, in_use_check
│
├── workflows/                    # Multi-step business processes
│   ├── __init__.py
│   ├── data_point_workflow.py    # submit → review → approve/reject
│   ├── review_workflow.py        # batch approve, batch reject
│   ├── completeness_workflow.py  # full recalculation pipeline
│   ├── boundary_workflow.py      # apply boundary + regenerate assignments
│   ├── merge_workflow.py         # collect → group → classify → build view
│   ├── export_workflow.py        # readiness check → generate → publish
│   ├── standard_add_workflow.py  # add standard → merge → completeness
│   └── escalation_workflow.py    # SLA breach → notifications chain
│
├── events/                       # Event system
│   ├── __init__.py
│   ├── bus.py                    # EventBus implementation
│   ├── types.py                  # Event type definitions
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── completeness_handler.py
│   │   ├── notification_handler.py
│   │   ├── audit_handler.py
│   │   └── boundary_handler.py
│   └── publishers.py            # Helper to emit events
│
├── infrastructure/               # External integrations
│   ├── __init__.py
│   ├── storage.py                # S3/MinIO client
│   ├── email.py                  # Email sender
│   ├── queue.py                  # Background task queue (arq/celery)
│   └── cache.py                  # Redis cache (Phase 2)
│
├── db/                           # Database layer
│   ├── __init__.py
│   ├── session.py                # AsyncSession factory
│   ├── models/                   # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── standard.py
│   │   ├── disclosure.py
│   │   ├── requirement_item.py
│   │   ├── shared_element.py
│   │   ├── data_point.py
│   │   ├── evidence.py
│   │   ├── project.py
│   │   ├── assignment.py
│   │   ├── company_entity.py
│   │   ├── boundary.py
│   │   ├── notification.py
│   │   └── audit_log.py
│   └── migrations/               # Alembic migrations
│       ├── env.py
│       └── versions/
│
├── core/                         # Cross-cutting concerns
│   ├── __init__.py
│   ├── config.py                 # Settings (pydantic-settings)
│   ├── security.py               # JWT, password hashing
│   ├── dependencies.py           # FastAPI dependency injection
│   ├── exceptions.py             # AppError, error codes
│   ├── middleware.py              # request_id, CORS, rate limiting
│   └── logging.py                # Structured logging (structlog)
│
├── main.py                       # FastAPI app factory
└── __init__.py
```

### 4.2. Структура модуля (пример: evidence)

```
Один модуль пронизывает все слои:

api/routes/evidence.py        → HTTP endpoints
schemas/evidence.py            → Pydantic DTOs
domain/evidence.py             → Business entity & invariants
services/evidence_service.py   → Business operations
repositories/evidence_repo.py  → Data access
policies/evidence_policy.py    → Access rules
events/types.py                → EvidenceCreated, EvidenceLinked, ...
db/models/evidence.py          → SQLAlchemy model
```

---

## 5. Описание слоёв

### 5.1. API layer (routers)

**Назначение:**

- объявление HTTP endpoints;
- валидация входных данных (через Pydantic schemas);
- вызов service слоя;
- формирование response.

**Запрещено:**

- писать бизнес-логику;
- обращаться к БД напрямую;
- реализовывать workflow;
- содержать if/else по бизнес-правилам.

**Разрешено:**

- dependency injection;
- auth context extraction;
- request/response mapping;
- HTTP status code выбор.

**Пример:**

```python
# app/api/routes/evidence.py

from fastapi import APIRouter, Depends, status
from app.schemas.evidence import EvidenceCreate, EvidenceResponse, EvidenceListResponse
from app.services.evidence_service import EvidenceService
from app.core.dependencies import get_current_user, get_evidence_service

router = APIRouter(prefix="/api/evidences", tags=["Evidence"])


@router.post(
    "",
    response_model=EvidenceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_evidence(
    payload: EvidenceCreate,
    user=Depends(get_current_user),
    service: EvidenceService = Depends(get_evidence_service),
):
    """Create a new evidence record."""
    evidence = await service.create(payload, user)
    return evidence


@router.get("", response_model=EvidenceListResponse)
async def list_evidences(
    type: str | None = None,
    unlinked: bool | None = None,
    page: int = 1,
    page_size: int = 20,
    user=Depends(get_current_user),
    service: EvidenceService = Depends(get_evidence_service),
):
    """List evidences with filters."""
    return await service.list(
        user=user,
        type_filter=type,
        unlinked=unlinked,
        page=page,
        page_size=page_size,
    )
```

### 5.2. Schemas (Pydantic)

**Назначение:**

- описание входных и выходных DTO;
- валидация данных на границе API;
- сериализация / десериализация.

**Требования:**

- не содержат бизнес-логики;
- могут содержать только базовую валидацию (формат, длина, enum);
- используются **только на границе API**;
- domain models и schemas — **разные сущности**.

**Пример:**

```python
# app/schemas/evidence.py

from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class EvidenceType(str, Enum):
    file = "file"
    link = "link"


class SourceType(str, Enum):
    manual = "manual"
    upload = "upload"
    integration = "integration"


class EvidenceCreate(BaseModel):
    type: EvidenceType
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    source_type: SourceType = SourceType.manual

    # For type=file
    file_name: str | None = None
    file_uri: str | None = None
    mime_type: str | None = None
    file_size: int | None = None

    # For type=link
    url: str | None = None
    label: str | None = None
    access_note: str | None = None


class EvidenceResponse(BaseModel):
    id: int
    type: EvidenceType
    title: str
    description: str | None
    source_type: SourceType
    created_by: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EvidenceListResponse(BaseModel):
    items: list[EvidenceResponse]
    meta: "ListMeta"
```

### 5.3. Domain layer

**Назначение:**

- описание бизнес-сущностей;
- инварианты (правила, которые **всегда** должны выполняться);
- базовые правила домена;
- value objects.

**Требования:**

- **не зависит** от FastAPI;
- **не зависит** от БД (SQLAlchemy);
- **не зависит** от инфраструктуры;
- содержит **чистую** бизнес-логику;
- может использовать только стандартные Python типы и dataclasses.

**Пример:**

```python
# app/domain/evidence.py

from dataclasses import dataclass
from enum import Enum


class EvidenceType(str, Enum):
    FILE = "file"
    LINK = "link"


@dataclass
class Evidence:
    id: int
    organization_id: int
    type: EvidenceType
    title: str
    description: str | None = None

    def is_file(self) -> bool:
        return self.type == EvidenceType.FILE

    def is_link(self) -> bool:
        return self.type == EvidenceType.LINK


# app/domain/workflow_state.py

from enum import Enum


class DataPointStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


ALLOWED_TRANSITIONS: dict[DataPointStatus, list[dict]] = {
    DataPointStatus.DRAFT: [
        {"to": DataPointStatus.SUBMITTED, "roles": ["collector", "esg_manager"]},
    ],
    DataPointStatus.SUBMITTED: [
        {"to": DataPointStatus.IN_REVIEW, "roles": ["system"]},
    ],
    DataPointStatus.IN_REVIEW: [
        {"to": DataPointStatus.APPROVED, "roles": ["reviewer", "esg_manager"]},
        {"to": DataPointStatus.REJECTED, "roles": ["reviewer", "esg_manager"], "require_comment": True},
        {"to": DataPointStatus.NEEDS_REVISION, "roles": ["reviewer", "esg_manager"], "require_comment": True},
    ],
    DataPointStatus.APPROVED: [
        {"to": DataPointStatus.DRAFT, "roles": ["esg_manager"], "require_comment": True},
    ],
    DataPointStatus.REJECTED: [
        {"to": DataPointStatus.SUBMITTED, "roles": ["collector"]},
    ],
    DataPointStatus.NEEDS_REVISION: [
        {"to": DataPointStatus.SUBMITTED, "roles": ["collector"]},
    ],
}


def can_transition(current: DataPointStatus, target: DataPointStatus, role: str) -> bool:
    """Check if workflow transition is allowed."""
    transitions = ALLOWED_TRANSITIONS.get(current, [])
    return any(
        t["to"] == target and role in t["roles"]
        for t in transitions
    )


def is_editable(status: DataPointStatus) -> bool:
    """Check if data point can be edited in current status."""
    return status in (
        DataPointStatus.DRAFT,
        DataPointStatus.REJECTED,
        DataPointStatus.NEEDS_REVISION,
    )
```

### 5.4. Services layer

**Назначение:**

- реализация бизнес-операций;
- orchestration domain логики;
- координация репозиториев, policies и workflows.

**Требования:**

- основной слой бизнес-логики;
- не содержит HTTP-специфики (нет Request, Response, status codes);
- работает с domain и repositories;
- вызывает policies и workflows;
- бросает доменные исключения (`AppError`), не HTTP-ошибки.

**Пример:**

```python
# app/services/evidence_service.py

from app.repositories.evidence_repo import EvidenceRepository
from app.policies.evidence_policy import EvidencePolicy
from app.events.bus import EventBus
from app.events.types import EvidenceCreated
from app.core.exceptions import AppError


class EvidenceService:
    def __init__(
        self,
        repo: EvidenceRepository,
        policy: EvidencePolicy,
        event_bus: EventBus,
    ):
        self.repo = repo
        self.policy = policy
        self.event_bus = event_bus

    async def create(self, payload, user) -> dict:
        """Create a new evidence record."""
        # Policy check
        self.policy.can_create(user)

        # Business logic
        evidence = await self.repo.create(
            organization_id=user.organization_id,
            type=payload.type,
            title=payload.title,
            description=payload.description,
            source_type=payload.source_type,
            created_by=user.id,
        )

        # Handle file/link specifics
        if payload.type == "file":
            await self.repo.create_file(
                evidence_id=evidence.id,
                file_name=payload.file_name,
                file_uri=payload.file_uri,
                mime_type=payload.mime_type,
                file_size=payload.file_size,
            )
        elif payload.type == "link":
            await self.repo.create_link(
                evidence_id=evidence.id,
                url=payload.url,
                label=payload.label,
                access_note=payload.access_note,
            )

        # Emit event
        await self.event_bus.publish(EvidenceCreated(
            evidence_id=evidence.id,
            type=payload.type,
        ))

        return evidence

    async def delete(self, evidence_id: int, user) -> None:
        """Delete evidence if not in approved scope."""
        evidence = await self.repo.get_or_raise(evidence_id)

        # Policy checks
        self.policy.can_delete(user, evidence)
        await self.policy.not_in_approved_scope(evidence_id)

        await self.repo.delete(evidence_id)
```

### 5.5. Repositories

**Назначение:**

- доступ к данным (PostgreSQL);
- абстракция поверх ORM (SQLAlchemy async);
- сложные запросы (CTE, joins, aggregations).

**Требования:**

- не содержат бизнес-логики;
- только CRUD и query;
- не знают о FastAPI;
- не знают о workflow;
- используют SQLAlchemy async session.

**Пример:**

```python
# app/repositories/evidence_repo.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.models.evidence import EvidenceModel, EvidenceFileModel, EvidenceLinkModel
from app.repositories.base import BaseRepository
from app.core.exceptions import AppError


class EvidenceRepository(BaseRepository[EvidenceModel]):
    def __init__(self, session: AsyncSession):
        super().__init__(EvidenceModel, session)

    async def get_or_raise(self, evidence_id: int) -> EvidenceModel:
        evidence = await self.get_by_id(evidence_id)
        if not evidence:
            raise AppError("EVIDENCE_NOT_FOUND", 404, f"Evidence {evidence_id} not found")
        return evidence

    async def create_file(self, evidence_id: int, **kwargs) -> EvidenceFileModel:
        file_record = EvidenceFileModel(evidence_id=evidence_id, **kwargs)
        self.session.add(file_record)
        await self.session.flush()
        return file_record

    async def create_link(self, evidence_id: int, **kwargs) -> EvidenceLinkModel:
        link_record = EvidenceLinkModel(evidence_id=evidence_id, **kwargs)
        self.session.add(link_record)
        await self.session.flush()
        return link_record

    async def is_used_in_approved_scope(self, evidence_id: int) -> bool:
        """Check if evidence is linked to any approved data point."""
        query = (
            select(func.count())
            .select_from(DataPointEvidenceModel)
            .join(DataPointModel)
            .where(
                DataPointEvidenceModel.evidence_id == evidence_id,
                DataPointModel.status == "approved",
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one() > 0

    async def list_filtered(
        self,
        organization_id: int,
        type_filter: str | None = None,
        unlinked: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[EvidenceModel], int]:
        """List evidences with filters and pagination."""
        query = select(EvidenceModel).where(
            EvidenceModel.organization_id == organization_id
        )

        if type_filter:
            query = query.where(EvidenceModel.type == type_filter)

        if unlinked:
            # Evidences not linked to any data point or requirement item
            query = query.where(
                ~EvidenceModel.id.in_(
                    select(DataPointEvidenceModel.evidence_id)
                ),
                ~EvidenceModel.id.in_(
                    select(RequirementItemEvidenceModel.evidence_id)
                ),
            )

        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_query)).scalar_one()

        # Paginate
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)

        return result.scalars().all(), total
```

### 5.6. Policies

**Назначение:**

- правила доступа (RBAC + object-level);
- бизнес-валидации;
- разрешения операций.

**Требования:**

- не зависят от API;
- вызываются из service слоя;
- возвращают `None` (success) или бросают `AppError`;
- не обращаются к БД напрямую (используют repositories, переданные через DI).

**Пример:**

```python
# app/policies/evidence_policy.py

from app.core.exceptions import AppError


class EvidencePolicy:
    def __init__(self, evidence_repo):
        self.evidence_repo = evidence_repo

    def can_create(self, user) -> None:
        """Check if user can create evidence."""
        if user.role not in ("admin", "esg_manager", "collector"):
            raise AppError("FORBIDDEN", 403, "You don't have permission to create evidence")

    def can_delete(self, user, evidence) -> None:
        """Check if user can delete evidence."""
        if user.role == "collector" and evidence.created_by != user.id:
            raise AppError("FORBIDDEN", 403, "Collectors can only delete their own evidence")
        if user.role not in ("admin", "esg_manager", "collector"):
            raise AppError("FORBIDDEN", 403, "You don't have permission to delete evidence")

    async def not_in_approved_scope(self, evidence_id: int) -> None:
        """Check evidence is not used in approved data points."""
        if await self.evidence_repo.is_used_in_approved_scope(evidence_id):
            raise AppError(
                "EVIDENCE_IN_USE", 409,
                "Cannot delete evidence used in approved data points"
            )


# app/policies/data_point_policy.py

from app.domain.workflow_state import is_editable, can_transition
from app.core.exceptions import AppError


class DataPointPolicy:
    def can_edit(self, user, data_point, assignment) -> None:
        """Check if user can edit this data point."""
        if not is_editable(data_point.status):
            raise AppError(
                "DATA_POINT_LOCKED", 422,
                f"Cannot edit data point in status '{data_point.status}'"
            )
        if user.role == "collector" and assignment.collector_id != user.id:
            raise AppError("FORBIDDEN", 403, "You can only edit your own data points")

    def can_submit(self, user, data_point, assignment) -> None:
        """Check if user can submit this data point."""
        if data_point.status not in ("draft", "rejected", "needs_revision"):
            raise AppError(
                "INVALID_WORKFLOW_TRANSITION", 422,
                f"Cannot submit data point in status '{data_point.status}'"
            )
        if user.role == "collector" and assignment.collector_id != user.id:
            raise AppError("FORBIDDEN", 403, "You can only submit your own data points")

    def can_approve(self, user, data_point, assignment) -> None:
        """Check if reviewer can approve."""
        if user.role == "reviewer" and assignment.reviewer_id != user.id:
            raise AppError("FORBIDDEN", 403, "You can only approve data points assigned to you")
        if not can_transition(data_point.status, "approved", user.role):
            raise AppError(
                "INVALID_WORKFLOW_TRANSITION", 422,
                f"Cannot approve data point in status '{data_point.status}'"
            )

    def requires_comment(self, action: str, comment: str | None) -> None:
        """Check if comment is required for this action."""
        if action in ("reject", "needs_revision", "rollback") and not comment:
            raise AppError(
                "REVIEW_COMMENT_REQUIRED", 422,
                f"Comment is required for '{action}' action"
            )
```

### 5.7. Workflows

**Назначение:**

- сложные бизнес-процессы;
- multi-step операции;
- процессы с состояниями;
- координация нескольких сервисов.

**Требования:**

- могут быть асинхронными;
- могут использовать очереди;
- управляют последовательностью действий;
- **не реализуются** в API или services напрямую;
- services вызывают workflows, не наоборот.

**Пример:**

```python
# app/workflows/boundary_workflow.py

from app.repositories.boundary_repo import BoundaryRepository
from app.repositories.assignment_repo import AssignmentRepository
from app.repositories.project_repo import ProjectRepository
from app.services.completeness_service import CompletenessService
from app.events.bus import EventBus
from app.events.types import BoundaryAppliedToProject, AssignmentsAffectedByBoundary
from app.core.exceptions import AppError


class ApplyBoundaryWorkflow:
    """
    Multi-step workflow: apply boundary to project.

    Steps:
    1. Validate project is not locked
    2. Calculate new boundary memberships
    3. Diff with current assignments
    4. Remove invalid assignments
    5. Create new assignments
    6. Update project boundary reference
    7. Recalculate completeness
    8. Emit events
    """

    def __init__(
        self,
        boundary_repo: BoundaryRepository,
        assignment_repo: AssignmentRepository,
        project_repo: ProjectRepository,
        completeness_service: CompletenessService,
        event_bus: EventBus,
    ):
        self.boundary_repo = boundary_repo
        self.assignment_repo = assignment_repo
        self.project_repo = project_repo
        self.completeness_service = completeness_service
        self.event_bus = event_bus

    async def execute(self, project_id: int, boundary_id: int, user) -> dict:
        # Step 1: Validate
        project = await self.project_repo.get_or_raise(project_id)
        if project.status in ("published",):
            raise AppError("PROJECT_LOCKED", 422, "Cannot change boundary for published project")

        boundary = await self.boundary_repo.get_or_raise(boundary_id)

        # Step 2: Calculate memberships
        memberships = await self.boundary_repo.get_memberships(boundary_id)
        included_entity_ids = [m.entity_id for m in memberships if m.included]

        # Step 3: Diff assignments
        current_assignments = await self.assignment_repo.list_by_project(project_id)
        current_entity_ids = {a.entity_id for a in current_assignments}
        new_entity_ids = set(included_entity_ids)

        to_remove = current_entity_ids - new_entity_ids
        to_add = new_entity_ids - current_entity_ids

        # Step 4: Remove invalid
        removed = await self.assignment_repo.deactivate_by_entities(
            project_id, list(to_remove)
        )

        # Step 5: Create new (unassigned, need ESG manager to assign collectors)
        added = await self.assignment_repo.create_stubs_for_entities(
            project_id, list(to_add)
        )

        # Step 6: Update project
        await self.project_repo.update(project_id, boundary_definition_id=boundary_id)

        # Step 7: Recalculate completeness
        await self.completeness_service.recalculate_project(project_id)

        # Step 8: Emit events
        await self.event_bus.publish(BoundaryAppliedToProject(
            project_id=project_id,
            boundary_id=boundary_id,
        ))
        await self.event_bus.publish(AssignmentsAffectedByBoundary(
            project_id=project_id,
            added=len(to_add),
            removed=len(to_remove),
            changed=0,
        ))

        return {
            "added": len(to_add),
            "removed": len(to_remove),
            "boundary_id": boundary_id,
        }


# app/workflows/data_point_workflow.py

class SubmitDataPointWorkflow:
    """
    Steps:
    1. Validate data point is in editable status
    2. Run field-level validation
    3. Run record-level validation
    4. Check required dimensions
    5. Update status to 'submitted'
    6. Create data_point_version
    7. Auto-transition to 'in_review' if reviewer assigned
    8. Emit DataPointSubmitted event
    9. Notify reviewer
    """

    async def execute(self, data_point_id: int, user) -> dict:
        # ... implementation
        pass
```

### 5.8. Events

**Назначение:**

- реакция на изменения;
- интеграция между модулями;
- webhooks (Phase 3).

**Требования:**

- события публикуются **после commit** (не в середине транзакции);
- обработчики **не должны ломать** основной поток;
- обработчики должны быть **idempotent**;
- каждое событие имеет строго типизированный payload.

**Пример:**

```python
# app/events/types.py

from dataclasses import dataclass
from datetime import datetime


@dataclass
class DomainEvent:
    """Base event."""
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class EvidenceCreated(DomainEvent):
    evidence_id: int = 0
    type: str = ""


@dataclass
class EvidenceLinkedToDP(DomainEvent):
    evidence_id: int = 0
    data_point_id: int = 0


@dataclass
class DataPointSubmitted(DomainEvent):
    data_point_id: int = 0
    submitted_by: int = 0


@dataclass
class DataPointApproved(DomainEvent):
    data_point_id: int = 0
    reviewed_by: int = 0


@dataclass
class BoundaryAppliedToProject(DomainEvent):
    project_id: int = 0
    boundary_id: int = 0


@dataclass
class BoundarySnapshotCreated(DomainEvent):
    project_id: int = 0
    snapshot_id: int = 0


# app/events/bus.py

from typing import Callable
from collections import defaultdict


class EventBus:
    """In-process event bus (MVP). Replace with message broker in Phase 3."""

    def __init__(self):
        self._handlers: dict[type, list[Callable]] = defaultdict(list)

    def subscribe(self, event_type: type, handler: Callable):
        self._handlers[event_type].append(handler)

    async def publish(self, event):
        handlers = self._handlers.get(type(event), [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                # Log but don't break main flow
                logger.error(f"Event handler failed: {e}", event=event)


# app/events/handlers/completeness_handler.py

class CompletenessEventHandler:
    """React to events that affect completeness."""

    def __init__(self, completeness_service):
        self.completeness_service = completeness_service

    async def on_data_point_approved(self, event: DataPointApproved):
        await self.completeness_service.recalculate_for_data_point(event.data_point_id)

    async def on_boundary_applied(self, event: BoundaryAppliedToProject):
        await self.completeness_service.recalculate_project(event.project_id)
```

---

## 6. Cross-cutting concerns

### 6.1. Dependency Injection

FastAPI `Depends()` используется для DI всех компонентов:

```python
# app/core/dependencies.py

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.repositories.evidence_repo import EvidenceRepository
from app.policies.evidence_policy import EvidencePolicy
from app.services.evidence_service import EvidenceService
from app.events.bus import get_event_bus


async def get_evidence_repo(session: AsyncSession = Depends(get_session)):
    return EvidenceRepository(session)


async def get_evidence_policy(repo: EvidenceRepository = Depends(get_evidence_repo)):
    return EvidencePolicy(repo)


async def get_evidence_service(
    repo: EvidenceRepository = Depends(get_evidence_repo),
    policy: EvidencePolicy = Depends(get_evidence_policy),
    event_bus=Depends(get_event_bus),
):
    return EvidenceService(repo, policy, event_bus)
```

### 6.2. Exception handling

Единый формат ошибок (ERROR-MODEL.md):

```python
# app/core/exceptions.py

from dataclasses import dataclass, field


@dataclass
class ErrorDetail:
    field: str | None = None
    reason: str = ""
    expected: str | None = None


@dataclass
class AppError(Exception):
    code: str = "INTERNAL_ERROR"
    status_code: int = 500
    message: str = "An unexpected error occurred"
    details: list[ErrorDetail] = field(default_factory=list)

    def to_response(self, request_id: str) -> dict:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": [
                    {"field": d.field, "reason": d.reason, "expected": d.expected}
                    for d in self.details
                ],
                "requestId": request_id,
            }
        }
```

```python
# In main.py — global exception handler
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    request_id = request.state.request_id
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_response(request_id),
    )
```

### 6.3. Middleware

```python
# app/core/middleware.py

import uuid
from starlette.middleware.base import BaseHTTPMiddleware


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.request_id = str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response
```

### 6.4. Database session management

```python
# app/db/session.py

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session():
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

---

## 7. Обязательные правила (критично)

### 7.1. Нельзя писать бизнес-логику в routers

Любая логика уровня расчётов, проверок, workflow → **только через services**.

**Нарушение (запрещено):**

```python
@router.post("/data-points/{id}/submit")
async def submit(id: int, user=Depends(get_current_user), db=Depends(get_session)):
    dp = await db.execute(select(DataPoint).where(DataPoint.id == id))
    dp = dp.scalar_one()
    if dp.status != "draft":
        raise HTTPException(422, "Cannot submit")
    dp.status = "submitted"
    await db.commit()  # ← ВСЁ НЕПРАВИЛЬНО
```

**Правильно:**

```python
@router.post("/data-points/{id}/submit")
async def submit(id: int, user=Depends(get_current_user), service=Depends(get_dp_service)):
    return await service.submit(id, user)
```

### 7.2. Нельзя обращаться к БД напрямую из API

Только через repositories.

### 7.3. Любая сложная операция = service + workflow

| Операция | Где реализуется |
|----------|----------------|
| Submit data point | `DataPointService.submit()` → `SubmitDataPointWorkflow` |
| Approve data point | `ReviewService.approve()` → `ApproveDataPointWorkflow` |
| Apply boundary | `BoundaryService.apply()` → `ApplyBoundaryWorkflow` |
| Generate report | `ReportingService.export()` → `ExportWorkflow` |
| Add standard to project | `ProjectService.add_standard()` → `StandardAddWorkflow` |

### 7.4. Все правила доступа — через policies

**Нельзя:**

- хардкодить проверки в сервисах;
- дублировать проверки между модулями.

**Правильно:**

```python
# В сервисе:
self.policy.can_edit(user, data_point, assignment)
# Policy бросает AppError если нельзя
```

### 7.5. Все события должны быть формализованы

Любое значимое изменение:

- **должно** генерировать event;
- **должно** быть логировано (audit log);
- handler подписывается через `EventBus.subscribe()`.

---

## 8. Technology Stack (backend)

| Компонент | Технология | Версия | Обоснование |
|-----------|-----------|--------|------------|
| **Framework** | FastAPI | 0.110+ | Async, типизация, auto-docs, DI |
| **ORM** | SQLAlchemy 2.0 (async) | 2.0+ | Async support, mature, CTE, window functions |
| **Migrations** | Alembic | 1.13+ | Стандарт для SQLAlchemy |
| **Validation** | Pydantic v2 | 2.6+ | Нативная интеграция с FastAPI |
| **Auth** | python-jose + passlib | — | JWT + bcrypt |
| **DB** | PostgreSQL | 16+ | JSONB, CTE, partial indexes |
| **DB Driver** | asyncpg | 0.29+ | Async PostgreSQL driver |
| **File Storage** | boto3 (aioboto3) | — | S3/MinIO |
| **Background Tasks** | arq (MVP) → Celery (Phase 3) | — | Redis-based task queue |
| **Logging** | structlog | 24.1+ | Structured JSON logs |
| **Testing** | pytest + pytest-asyncio + httpx | — | Async test support |
| **Linting** | ruff | 0.3+ | Fast Python linter + formatter |
| **Type Checking** | mypy | 1.8+ | Static type checking |

---

## 9. Применение к текущим модулям

### 9.1. Evidence

| Слой | Файл | Содержание |
|------|------|-----------|
| Domain | `domain/evidence.py` | `Evidence`, `EvidenceType`, invariants |
| Service | `services/evidence_service.py` | `create`, `delete`, `link_to_dp`, `link_to_ri` |
| Repository | `repositories/evidence_repo.py` | CRUD, `is_used_in_approved_scope`, filtered list |
| Policy | `policies/evidence_policy.py` | `can_create`, `can_delete`, `not_in_approved_scope` |
| Events | `events/types.py` | `EvidenceCreated`, `EvidenceLinkedToDP`, ... |

### 9.2. Org Structure & Boundary

| Слой | Файл | Содержание |
|------|------|-----------|
| Domain | `domain/company_entity.py`, `domain/boundary.py`, `domain/ownership.py` | Entities, ownership chain, boundary rules |
| Service | `services/entity_service.py`, `services/boundary_service.py` | CRUD entities, apply boundary, calculate effective ownership |
| Repository | `repositories/entity_repo.py`, `repositories/boundary_repo.py` | Tree queries (CTE), memberships |
| Policy | `policies/boundary_policy.py` | `snapshot_immutable`, `project_locked`, `boundary_inclusion_check` |
| Workflow | `workflows/boundary_workflow.py` | `ApplyBoundaryWorkflow` (multi-step) |
| Events | `events/types.py` | `BoundaryAppliedToProject`, `BoundarySnapshotCreated`, ... |

### 9.3. Data Points

| Слой | Файл | Содержание |
|------|------|-----------|
| Domain | `domain/data_point.py`, `domain/workflow_state.py`, `domain/identity_rule.py` | State machine, Identity Rule |
| Service | `services/data_point_service.py` | `create`, `update`, `submit`, `find_reuse` |
| Repository | `repositories/data_point_repo.py` | CRUD, reuse search, dimension queries |
| Policy | `policies/data_point_policy.py` | `can_edit`, `can_submit`, `is_locked` |
| Workflow | `workflows/data_point_workflow.py` | `SubmitDataPointWorkflow` |
| Events | `events/types.py` | `DataPointCreated`, `DataPointSubmitted`, ... |

### 9.4. Review

| Слой | Файл | Содержание |
|------|------|-----------|
| Service | `services/review_service.py` | `approve`, `reject`, `request_revision`, `batch_approve` |
| Policy | `policies/review_policy.py` | `can_approve`, `requires_comment`, `check_evidence` |
| Workflow | `workflows/review_workflow.py` | `BatchApproveWorkflow` |

### 9.5. Completeness

| Слой | Файл | Содержание |
|------|------|-----------|
| Service | `services/completeness_service.py` | `calculate_item_status`, `aggregate_disclosure`, `recalculate_project` |
| Workflow | `workflows/completeness_workflow.py` | Full recalculation pipeline |
| Events handler | `events/handlers/completeness_handler.py` | React to DataPoint/Boundary events |

### 9.6. Merge Engine

| Слой | Файл | Содержание |
|------|------|-----------|
| Service | `services/merge_service.py` | `get_merged_view`, `calculate_coverage`, `impact_preview` |
| Workflow | `workflows/merge_workflow.py` | Collect → group → classify → find orphans → build view |

---

## 10. Критерии приёмки архитектуры

Система считается соответствующей требованиям, если:

- [ ] Нет бизнес-логики в API routers (все routers < 30 строк на endpoint)
- [ ] Все операции проходят через service слой
- [ ] Нет прямых вызовов БД из API (нет `session` в router аргументах)
- [ ] Policies вынесены отдельно (нет inline role/permission checks в services)
- [ ] Workflows реализованы отдельно (сложные операции не inline в services)
- [ ] События централизованы (все через EventBus, типы в `events/types.py`)
- [ ] Структура проекта единообразна по всем модулям
- [ ] Domain layer не имеет импортов FastAPI или SQLAlchemy
- [ ] Все ошибки через `AppError` с единым форматом `ErrorResponse`
- [ ] DI настроен через FastAPI `Depends()` chain
- [ ] Каждый модуль покрыт: route → schema → service → repo → policy → event

---

## 11. Контроль соблюдения

| Механизм | Описание |
|----------|----------|
| **Code review** | Обязательная проверка архитектурных слоёв при каждом PR |
| **CI lint** | ruff + mypy + custom rules для проверки imports (domain не импортирует fastapi) |
| **Architecture tests** | pytest тесты, проверяющие, что domain/ не имеет запрещённых импортов |
| **Blocking policy** | Архитектурные нарушения считаются **blocking issues** — PR не мёржится |

**Пример architecture test:**

```python
# tests/test_architecture.py

import ast
import os


FORBIDDEN_IMPORTS_IN_DOMAIN = {"fastapi", "sqlalchemy", "starlette"}


def test_domain_has_no_framework_imports():
    """Domain layer must not depend on FastAPI or SQLAlchemy."""
    domain_dir = "app/domain"
    for filename in os.listdir(domain_dir):
        if not filename.endswith(".py"):
            continue
        filepath = os.path.join(domain_dir, filename)
        with open(filepath) as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = node.module if isinstance(node, ast.ImportFrom) else None
                if module:
                    top_level = module.split(".")[0]
                    assert top_level not in FORBIDDEN_IMPORTS_IN_DOMAIN, (
                        f"{filepath} imports '{module}' — domain must not depend on {top_level}"
                    )
```
