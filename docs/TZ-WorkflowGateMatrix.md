# Master Workflow & Gate Matrix

**Модуль:** Workflow Engine / Gate Engine
**Версия:** 1.0
**Дата:** 2026-03-22
**Статус:** Согласован
**Зависимости:** TZ-BackendArchitecture.md, TZ-PermissionMatrix.md, ERROR-MODEL.md

---

## 1. Общие принципы

### 1.1. Workflow-driven система

Все ключевые сущности управляются через статусы и переходы. Ни одна сущность не меняет статус «просто так» — только через формализованный transition.

### 1.2. Gate-controlled transitions

Любой переход статуса проходит через **Gate Engine**:

```
Action → Gate Engine → (allowed | blocked) → transition → events
```

### 1.3. Типы Gate

| Gate | Описание |
|------|----------|
| **Data Gate** | Валидация обязательных полей и форматов |
| **Evidence Gate** | Проверка наличия required evidence |
| **Boundary Gate** | Проверка, что entity входит в boundary проекта |
| **Completeness Gate** | Проверка полноты данных (requirement level, project level) |
| **Review Gate** | Проверка статуса review (наличие, завершённость) |
| **Workflow Gate** | Проверка допустимости перехода (lock state, project status) |

### 1.4. Gate Engine архитектура

```python
# app/workflows/gate_engine.py

@dataclass
class GateResult:
    allowed: bool
    failed_gates: list[FailedGate]
    warnings: list[FailedGate]


@dataclass
class FailedGate:
    code: str
    gate_type: str       # 'data' | 'evidence' | 'boundary' | 'completeness' | 'review' | 'workflow'
    message: str
    severity: str        # 'blocker' | 'warning'
    details: dict | None = None


class GateEngine:
    """Central gate engine — all transitions go through here."""

    def __init__(self, gates: list[Gate]):
        self.gates = gates

    async def check(self, action: str, context: dict) -> GateResult:
        """Run all applicable gates for an action."""
        failed = []
        warnings = []

        for gate in self.gates:
            if not gate.applies_to(action):
                continue

            result = await gate.evaluate(context)
            if result is None:
                continue  # passed

            if result.severity == "blocker":
                failed.append(result)
            else:
                warnings.append(result)

        return GateResult(
            allowed=len(failed) == 0,
            failed_gates=failed,
            warnings=warnings,
        )
```

```python
# app/workflows/gates/base.py

from abc import ABC, abstractmethod


class Gate(ABC):
    """Base gate interface."""

    @abstractmethod
    def applies_to(self, action: str) -> bool:
        """Check if this gate applies to the given action."""
        ...

    @abstractmethod
    async def evaluate(self, context: dict) -> FailedGate | None:
        """Evaluate gate. Return None if passed, FailedGate if failed."""
        ...
```

---

## 2. Сущность: Data Point

### 2.1. State Machine

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

### 2.2. Transition: `draft → submitted`

| Gate | Code | Условие | Severity |
|------|------|---------|----------|
| Data Gate | `INVALID_DATA` | Отсутствуют обязательные поля (value, unit_code, dimensions) | blocker |
| Data Gate | `INVALID_VALUE_TYPE` | Значение не соответствует `value_type` (number вместо text и т.д.) | blocker |
| Boundary Gate | `OUT_OF_BOUNDARY` | `data_point.entity_id` не входит в boundary проекта | ⚠️ warning (configurable → blocker) |
| Evidence Gate | `EVIDENCE_REQUIRED` | `requires_evidence = true` и нет привязанного evidence | blocker |
| Workflow Gate | `DATA_POINT_LOCKED` | Текущий статус не позволяет submit (не draft/rejected/needs_revision) | blocker |

```python
# app/workflows/gates/data_gate.py

class DataValidationGate(Gate):
    def applies_to(self, action: str) -> bool:
        return action in ("submit_data_point",)

    async def evaluate(self, context: dict) -> FailedGate | None:
        dp = context["data_point"]
        item = context["requirement_item"]

        missing_fields = []
        if item.value_type == "number" and dp.numeric_value is None:
            missing_fields.append("numeric_value")
        if item.unit_code and not dp.unit_code:
            missing_fields.append("unit_code")

        # Check required dimensions
        if item.granularity_rule:
            required_dims = self._get_required_dimensions(item.granularity_rule)
            existing_dims = {d.dimension_type for d in dp.dimensions}
            for rd in required_dims:
                if rd not in existing_dims:
                    missing_fields.append(f"dimension:{rd}")

        if missing_fields:
            return FailedGate(
                code="INVALID_DATA",
                gate_type="data",
                message=f"Missing required fields: {', '.join(missing_fields)}",
                severity="blocker",
                details={"missing_fields": missing_fields},
            )
        return None
```

```python
# app/workflows/gates/evidence_gate.py

class EvidenceRequiredGate(Gate):
    def __init__(self, evidence_repo):
        self.evidence_repo = evidence_repo

    def applies_to(self, action: str) -> bool:
        return action in ("submit_data_point", "approve_data_point")

    async def evaluate(self, context: dict) -> FailedGate | None:
        item = context["requirement_item"]
        if not item.requires_evidence:
            return None

        dp_id = context["data_point"].id
        item_id = item.id

        count = await self.evidence_repo.count_for_data_point(dp_id)
        count += await self.evidence_repo.count_for_requirement_item(item_id)

        if count == 0:
            return FailedGate(
                code="EVIDENCE_REQUIRED",
                gate_type="evidence",
                message="This data point requires supporting evidence.",
                severity="blocker",
            )
        return None
```

```python
# app/workflows/gates/boundary_gate.py

class BoundaryInclusionGate(Gate):
    def __init__(self, boundary_repo):
        self.boundary_repo = boundary_repo

    def applies_to(self, action: str) -> bool:
        return action in ("submit_data_point",)

    async def evaluate(self, context: dict) -> FailedGate | None:
        dp = context["data_point"]
        project = context["project"]

        if not dp.entity_id or not project.boundary_definition_id:
            return None

        membership = await self.boundary_repo.get_membership(
            project.boundary_definition_id, dp.entity_id
        )

        if not membership or not membership.included:
            return FailedGate(
                code="OUT_OF_BOUNDARY",
                gate_type="boundary",
                message=f"Entity is not included in project boundary.",
                severity="warning",  # configurable per project
                details={"entity_id": dp.entity_id, "boundary_id": project.boundary_definition_id},
            )
        return None
```

### 2.3. Transition: `submitted → in_review`

**Автоматический transition** при наличии назначенного reviewer.

| Gate | Code | Условие | Severity |
|------|------|---------|----------|
| Workflow Gate | `NO_REVIEWER_ASSIGNED` | Нет reviewer в assignment | blocker (остаётся в submitted) |

### 2.4. Transition: `in_review → approved`

| Gate | Code | Условие | Severity |
|------|------|---------|----------|
| Review Gate | `REVIEW_NOT_COMPLETED` | Reviewer не выполнил действие | blocker |
| Evidence Gate | `EVIDENCE_REQUIRED` | `requires_evidence = true` и нет evidence | blocker |
| Completeness Gate | `REQUIREMENT_INCOMPLETE` | Связанный requirement item не complete (dimension/evidence gap) | blocker |
| Workflow Gate | `INVALID_WORKFLOW_TRANSITION` | Текущий статус не `in_review` | blocker |

### 2.5. Transition: `in_review → rejected`

| Gate | Code | Условие | Severity |
|------|------|---------|----------|
| Review Gate | `REVIEW_COMMENT_REQUIRED` | Комментарий обязателен при reject | blocker |

**Reject всегда разрешён reviewer** (при наличии комментария).

### 2.6. Transition: `in_review → needs_revision`

| Gate | Code | Условие | Severity |
|------|------|---------|----------|
| Review Gate | `REVIEW_COMMENT_REQUIRED` | Комментарий обязателен | blocker |

### 2.7. Transition: `rejected / needs_revision → submitted`

| Gate | Code | Условие | Severity |
|------|------|---------|----------|
| Data Gate | `INVALID_DATA` | Обязательные поля (повторная проверка) | blocker |
| Evidence Gate | `EVIDENCE_REQUIRED` | Evidence (повторная проверка) | blocker |

### 2.8. Transition: `approved → draft` (rollback)

| Gate | Code | Условие | Severity |
|------|------|---------|----------|
| Workflow Gate | `ROLLBACK_COMMENT_REQUIRED` | Комментарий / обоснование обязательны | blocker |
| Workflow Gate | `PROJECT_LOCKED` | Проект в статусе `published` | blocker |
| Workflow Gate | `ROLE_NOT_ALLOWED` | Только `esg_manager` может rollback | blocker |

---

## 3. Сущность: Evidence

### 3.1. Статусы

```
active → archived
```

### 3.2. Transition: `active → archived`

| Gate | Code | Условие | Severity |
|------|------|---------|----------|
| Workflow Gate | `EVIDENCE_IN_USE` | Evidence привязан к approved data point | blocker |

### 3.3. Действие: unlink evidence from data point

| Gate | Code | Условие | Severity |
|------|------|---------|----------|
| Workflow Gate | `DATA_POINT_LOCKED` | Data point в статусе `approved` / `submitted` / `in_review` | blocker |

### 3.4. Действие: delete evidence

| Gate | Code | Условие | Severity |
|------|------|---------|----------|
| Workflow Gate | `EVIDENCE_IN_USE` | Привязан к любому approved data point | blocker |

---

## 4. Сущность: Assignment

### 4.1. State Machine

```
assigned → in_progress → completed
                ↓
             overdue
```

### 4.2. Transition: `assigned → in_progress`

**Автоматический** — при первом сохранении draft data point.

### 4.3. Transition: `in_progress → completed`

| Gate | Code | Условие | Severity |
|------|------|---------|----------|
| Data Gate | `MISSING_DATA` | Нет data point для assignment | blocker |
| Completeness Gate | `INCOMPLETE` | Связанный requirement item не `complete` | blocker |

### 4.4. Transition: `in_progress → overdue`

**Автоматический** — по cron job при `deadline < now()` и `status != 'completed'`.

---

## 5. Сущность: Project

### 5.1. State Machine

```
draft → active → review → published → archived
                                ↕ (rollback)
                            active
```

### 5.2. Transition: `draft → active`

| Gate | Code | Условие | Severity |
|------|------|---------|----------|
| Workflow Gate | `BOUNDARY_NOT_DEFINED` | Нет boundary у проекта | blocker |
| Workflow Gate | `NO_REQUIREMENTS` | Нет выбранных стандартов | blocker |
| Workflow Gate | `NO_ASSIGNMENTS` | Нет назначений (предупреждение, не блокер) | warning |

### 5.3. Transition: `active → review`

| Gate | Code | Условие | Severity |
|------|------|---------|----------|
| Completeness Gate | `PROJECT_INCOMPLETE` | Completeness < threshold (настраивается, default 100%) | blocker |
| Workflow Gate | `UNSUBMITTED_DATA` | Есть data points в статусе `draft` | warning |

### 5.4. Transition: `review → published`

| Gate | Code | Условие | Severity |
|------|------|---------|----------|
| Review Gate | `UNRESOLVED_REVIEW` | Есть data points в `rejected` / `needs_revision` / `in_review` | blocker |
| Completeness Gate | `PROJECT_INCOMPLETE` | Не все mandatory disclosures = `complete` | blocker |
| Evidence Gate | `EVIDENCE_REQUIRED` | Есть requirement items с `requires_evidence = true` без evidence | blocker |
| Workflow Gate | `BOUNDARY_NOT_LOCKED` | Boundary snapshot не создан / не locked | blocker |

### 5.5. Transition: `published → active` (rollback)

| Gate | Code | Условие | Severity |
|------|------|---------|----------|
| Workflow Gate | `ROLLBACK_COMMENT_REQUIRED` | Обоснование обязательно | blocker |
| Workflow Gate | `ROLE_NOT_ALLOWED` | Только `esg_manager` / `admin` | blocker |

### 5.6. Transition: `published → archived`

Без gate — ручное действие admin / esg_manager.

---

## 6. Сущность: Boundary Snapshot

### 6.1. Статусы

```
draft → locked
```

### 6.2. Transition: `draft → locked`

| Gate | Code | Условие | Severity |
|------|------|---------|----------|
| Workflow Gate | `SNAPSHOT_ALREADY_LOCKED` | Snapshot уже locked для published project | blocker |
| Workflow Gate | `EMPTY_BOUNDARY` | Boundary не содержит ни одной included entity | blocker |

### 6.3. Constraint: locked snapshot

- **Нельзя изменить** locked snapshot (`SNAPSHOT_IMMUTABLE`, 409)
- **Нельзя удалить** snapshot published проекта
- **Можно перезаписать** snapshot draft/active проекта (с audit log)

---

## 7. Сущность: Export Job

### 7.1. State Machine

```
pending → running → completed
              ↓
           failed
```

### 7.2. Transition: `pending → running`

| Gate | Code | Условие | Severity |
|------|------|---------|----------|
| Completeness Gate | `PROJECT_INCOMPLETE` | Проект не готов к export | blocker |
| Workflow Gate | `BOUNDARY_NOT_LOCKED` | Snapshot не locked | blocker |
| Workflow Gate | `EXPORT_IN_PROGRESS` | Уже запущен export для этого проекта | blocker |

---

## 8. Gate Catalog (единый реестр)

### 8.1. Data Gates

| Code | Applies to | Condition | Severity |
|------|-----------|-----------|----------|
| `INVALID_DATA` | `data_point.submit`, `data_point.resubmit` | Отсутствуют обязательные поля | blocker |
| `INVALID_VALUE_TYPE` | `data_point.submit` | Значение не соответствует `value_type` | blocker |
| `MISSING_DATA` | `assignment.complete` | Нет data point для assignment | blocker |

### 8.2. Evidence Gates

| Code | Applies to | Condition | Severity |
|------|-----------|-----------|----------|
| `EVIDENCE_REQUIRED` | `data_point.submit`, `data_point.approve`, `project.publish` | `requires_evidence = true` и нет evidence | blocker |

### 8.3. Boundary Gates

| Code | Applies to | Condition | Severity |
|------|-----------|-----------|----------|
| `OUT_OF_BOUNDARY` | `data_point.submit` | Entity вне boundary проекта | warning (configurable) |
| `BOUNDARY_NOT_DEFINED` | `project.start` | Нет boundary у проекта | blocker |
| `BOUNDARY_NOT_LOCKED` | `project.publish`, `export.start` | Snapshot не locked | blocker |
| `EMPTY_BOUNDARY` | `snapshot.lock` | Boundary без included entities | blocker |

### 8.4. Completeness Gates

| Code | Applies to | Condition | Severity |
|------|-----------|-----------|----------|
| `REQUIREMENT_INCOMPLETE` | `data_point.approve` | Связанный requirement item не complete | blocker |
| `PROJECT_INCOMPLETE` | `project.review`, `project.publish`, `export.start` | Completeness < threshold | blocker |
| `INCOMPLETE` | `assignment.complete` | Requirement item не complete | blocker |

### 8.5. Review Gates

| Code | Applies to | Condition | Severity |
|------|-----------|-----------|----------|
| `REVIEW_NOT_COMPLETED` | `data_point.approve` | Нет review action | blocker |
| `REVIEW_COMMENT_REQUIRED` | `data_point.reject`, `data_point.needs_revision` | Комментарий обязателен | blocker |
| `UNRESOLVED_REVIEW` | `project.publish` | Есть rejected / unreviewed data points | blocker |

### 8.6. Workflow Gates

| Code | Applies to | Condition | Severity |
|------|-----------|-----------|----------|
| `INVALID_WORKFLOW_TRANSITION` | Все transitions | Переход из текущего статуса невозможен | blocker |
| `DATA_POINT_LOCKED` | `data_point.edit`, `evidence.unlink` | Data point в locked status | blocker |
| `PROJECT_LOCKED` | `data_point.rollback`, `data_point.edit` | Project в `published` | blocker |
| `ROLE_NOT_ALLOWED` | `data_point.rollback`, `project.rollback` | Роль не может выполнить transition | blocker |
| `ROLLBACK_COMMENT_REQUIRED` | `data_point.rollback`, `project.rollback` | Обоснование обязательно | blocker |
| `EVIDENCE_IN_USE` | `evidence.delete`, `evidence.archive` | Привязан к approved data point | blocker |
| `SNAPSHOT_IMMUTABLE` | `snapshot.edit`, `snapshot.delete` | Snapshot locked для published project | blocker |
| `SNAPSHOT_ALREADY_LOCKED` | `snapshot.lock` | Уже locked | blocker |
| `NO_REQUIREMENTS` | `project.start` | Нет выбранных стандартов | blocker |
| `NO_REVIEWER_ASSIGNED` | `data_point.auto_review` | Нет reviewer в assignment | blocker |
| `EXPORT_IN_PROGRESS` | `export.start` | Export уже запущен | blocker |
| `NO_ASSIGNMENTS` | `project.start` | Нет назначений | warning |
| `UNSUBMITTED_DATA` | `project.review` | Есть draft data points | warning |

---

## 9. Gate Engine реализация

### 9.1. Структура файлов

```
app/workflows/
├── gate_engine.py              # GateEngine orchestrator
├── gates/
│   ├── __init__.py
│   ├── base.py                 # Gate ABC
│   ├── data_gate.py            # INVALID_DATA, INVALID_VALUE_TYPE, MISSING_DATA
│   ├── evidence_gate.py        # EVIDENCE_REQUIRED
│   ├── boundary_gate.py        # OUT_OF_BOUNDARY, BOUNDARY_NOT_DEFINED, EMPTY_BOUNDARY
│   ├── completeness_gate.py    # REQUIREMENT_INCOMPLETE, PROJECT_INCOMPLETE
│   ├── review_gate.py          # REVIEW_NOT_COMPLETED, REVIEW_COMMENT_REQUIRED, UNRESOLVED_REVIEW
│   └── workflow_gate.py        # all WORKFLOW_* gates
└── gate_registry.py            # registers gates per action
```

### 9.2. Gate Registry

```python
# app/workflows/gate_registry.py

from app.workflows.gates import (
    DataValidationGate,
    EvidenceRequiredGate,
    BoundaryInclusionGate,
    CompletenessGate,
    ReviewGate,
    WorkflowTransitionGate,
    RollbackCommentGate,
    ProjectLockedGate,
)


def build_gate_engine(repos, services) -> GateEngine:
    """Build gate engine with all gates wired up."""
    gates = [
        DataValidationGate(),
        EvidenceRequiredGate(repos.evidence),
        BoundaryInclusionGate(repos.boundary),
        CompletenessGate(services.completeness),
        ReviewGate(),
        WorkflowTransitionGate(),
        RollbackCommentGate(),
        ProjectLockedGate(repos.project),
    ]
    return GateEngine(gates)
```

### 9.3. Использование в workflow

```python
# app/workflows/data_point_workflow.py

class SubmitDataPointWorkflow:

    async def execute(self, data_point_id: int, user) -> dict:
        # 1. Load context
        dp = await self.dp_repo.get_with_details(data_point_id)
        item = await self.item_repo.get_by_id(dp.requirement_item_id)
        project = await self.project_repo.get_by_id(dp.project_id)
        assignment = await self.assignment_repo.get_for_data_point(dp.id)

        context = {
            "data_point": dp,
            "requirement_item": item,
            "project": project,
            "assignment": assignment,
            "user": user,
            "action": "submit_data_point",
        }

        # 2. Run Gate Engine
        gate_result = await self.gate_engine.check("submit_data_point", context)

        if not gate_result.allowed:
            raise GateBlockedError(
                code="GATE_BLOCKED",
                status_code=422,
                message="Cannot submit data point.",
                failed_gates=gate_result.failed_gates,
                warnings=gate_result.warnings,
            )

        # 3. Transition
        dp.status = "submitted"
        await self.dp_repo.update(dp)

        # 4. Auto-transition to in_review if reviewer assigned
        if assignment.reviewer_id:
            dp.status = "in_review"
            await self.dp_repo.update(dp)

        # 5. Create version
        await self.version_repo.create_snapshot(dp)

        # 6. Events
        await self.event_bus.publish(DataPointSubmitted(
            data_point_id=dp.id,
            submitted_by=user.id,
        ))

        # 7. Return with warnings
        return {
            "status": dp.status,
            "warnings": [w.to_dict() for w in gate_result.warnings],
        }
```

### 9.4. GateBlockedError

```python
# app/core/exceptions.py (расширение)

@dataclass
class GateBlockedError(AppError):
    """Raised when Gate Engine blocks a transition."""
    failed_gates: list[FailedGate] = field(default_factory=list)
    warnings: list[FailedGate] = field(default_factory=list)

    def to_response(self, request_id: str) -> dict:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": [
                    {
                        "code": g.code,
                        "type": g.gate_type,
                        "message": g.message,
                        "severity": g.severity,
                        "details": g.details,
                    }
                    for g in self.failed_gates
                ],
                "warnings": [
                    {
                        "code": w.code,
                        "type": w.gate_type,
                        "message": w.message,
                    }
                    for w in self.warnings
                ],
                "requestId": request_id,
            }
        }
```

---

## 10. API

### 10.1. Gate Check (pre-flight)

```
POST /api/gate-check
```

**Request:**

```json
{
  "action": "approve_data_point",
  "context": {
    "dataPointId": 9001,
    "projectId": 101
  }
}
```

**Response (blocked):**

```json
{
  "allowed": false,
  "failedGates": [
    {
      "code": "EVIDENCE_REQUIRED",
      "type": "evidence",
      "message": "This data point requires supporting evidence.",
      "severity": "blocker",
      "details": null
    }
  ],
  "warnings": [
    {
      "code": "OUT_OF_BOUNDARY",
      "type": "boundary",
      "message": "Entity is not included in project boundary.",
      "severity": "warning"
    }
  ]
}
```

**Response (allowed):**

```json
{
  "allowed": true,
  "failedGates": [],
  "warnings": []
}
```

### 10.2. Supported actions

| Action | Описание |
|--------|----------|
| `submit_data_point` | draft → submitted |
| `approve_data_point` | in_review → approved |
| `reject_data_point` | in_review → rejected |
| `request_revision` | in_review → needs_revision |
| `rollback_data_point` | approved → draft |
| `complete_assignment` | in_progress → completed |
| `start_project` | draft → active |
| `review_project` | active → review |
| `publish_project` | review → published |
| `rollback_project` | published → active |
| `lock_snapshot` | draft → locked |
| `start_export` | pending → running |
| `delete_evidence` | active → archived |
| `unlink_evidence` | remove binding |

### 10.3. Permission

| Endpoint | Кто может |
|----------|----------|
| `POST /api/gate-check` | Все аутентифицированные (результат зависит от роли + context) |

---

## 11. UI поведение

### 11.1. Pre-flight gate check

Перед каждым transition-действием (кнопка Submit, Approve, Publish, ...) frontend вызывает `POST /api/gate-check` и отображает результат:

### 11.2. Inline (при ошибке)

```
[Submit for Review]  ← кнопка disabled
  ⛔ Missing required field: breakdown by gas type
  ⛔ Evidence required for this metric
```

### 11.3. Modal (при множественных ошибках)

```
┌─────────────────────────────────────────────┐
│  Cannot publish project                      │
│                                              │
│  Blockers (3):                               │
│  ⛔ 2 data points in "rejected" status       │
│  ⛔ Missing evidence for GRI 305-3           │
│  ⛔ Boundary snapshot not locked              │
│                                              │
│  Warnings (1):                               │
│  ⚠️ 3 data points still in "draft" status   │
│                                              │
│  [Close]  [Fix issues →]                     │
└─────────────────────────────────────────────┘
```

### 11.4. AI интеграция

AI Copilot может использовать gate codes для объяснений:

```
User: "Почему я не могу approve?"
AI: (вызывает gate-check) →
    "Этот data point нельзя утвердить потому что:
     1. Требуется evidence (audit certificate) — загрузите документ
     2. Breakdown by gas type не заполнен — требуется GRI 305-1"
```

**AI Tool:**

```python
{
    "name": "check_gate",
    "description": "Check why a transition is blocked",
    "parameters": {
        "action": {"type": "string"},
        "data_point_id": {"type": "integer", "optional": True},
        "project_id": {"type": "integer", "optional": True},
    },
}
```

---

## 12. Связь с другими документами

| Документ | Что затрагивает |
|----------|----------------|
| **TZ-BackendArchitecture.md** | Gate Engine = часть workflows layer |
| **TZ-PermissionMatrix.md** | Gate `ROLE_NOT_ALLOWED` ссылается на permission matrix |
| **ERROR-MODEL.md** | Все gate codes добавляются в error codes catalog |
| **TZ-AIAssistance.md** | AI Tool `check_gate` для объяснения блокировок |
| **TZ-Evidence.md** | `EVIDENCE_REQUIRED`, `EVIDENCE_IN_USE` gates |
| **TZ-BoundaryIntegration.md** | `OUT_OF_BOUNDARY`, `BOUNDARY_NOT_LOCKED` gates |
| **ARCHITECTURE.md** | Completeness Engine triggers через gate events |

---

## 13. Критерии приёмки

- [ ] Любой status transition проходит через Gate Engine (нет прямых status updates)
- [ ] Все gate codes из каталога (раздел 8) реализованы
- [ ] Gate результат возвращается структурированно (`failedGates` + `warnings`)
- [ ] `POST /api/gate-check` работает как pre-flight для всех actions
- [ ] UI показывает blockers inline (рядом с кнопкой) и в modal (при множественных)
- [ ] AI может объяснить каждый gate code через tool `check_gate`
- [ ] Gate логика централизована в `app/workflows/gates/` (нет inline checks в services)
- [ ] Warnings не блокируют transition, но отображаются пользователю
- [ ] Blocker severity = 422 HTTP response с деталями
- [ ] Gate checks логируются в audit log (action, result, failed codes)
- [ ] Configurable severity (`OUT_OF_BOUNDARY` — warning по умолчанию, blocker по настройке)
