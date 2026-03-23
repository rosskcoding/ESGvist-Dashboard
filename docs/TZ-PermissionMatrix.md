# Master Role & Permission Matrix

**Модуль:** RBAC / Authorization
**Версия:** 1.0
**Дата:** 2026-03-22
**Статус:** Согласован
**Зависимости:** TZ-PlatformAdmin.md, ERROR-MODEL.md, TZ-BackendArchitecture.md

---

## 1. Общие принципы

### 1.1. Scope-aware доступ

Все права проверяются с учётом scope:

```
platform → organization → project → entity / data_point
```

### 1.2. Типы проверок

Каждое действие проверяется по 4 уровням:

| Уровень | Описание | Пример |
|---------|----------|--------|
| **Role** | Кто выполняет | `collector`, `reviewer`, `admin` |
| **Scope** | Где выполняет | `platform`, `organization_id=101` |
| **Object ownership** | К какому объекту | `assignment.collector_id == user.id` |
| **Workflow state** | Можно ли сейчас | `data_point.status == 'draft'` |

### 1.3. Уровни ролей

| Уровень | Роли |
|---------|------|
| **Platform** | `platform_admin` |
| **Tenant** | `admin`, `esg_manager`, `collector`, `reviewer`, `auditor` |

---

## 2. Легенда

| Обозначение | Значение |
|:-----------:|----------|
| ✅ | Разрешено |
| ⚠️ | Разрешено с условиями (object-level check) |
| ❌ | Запрещено |

---

## 3. Platform-level операции

| Действие | platform_admin | admin | esg_manager | collector | reviewer | auditor |
|----------|:-:|:-:|:-:|:-:|:-:|:-:|
| Создать organization (tenant) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Просмотреть список организаций | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Деактивировать tenant | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Архивировать tenant | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Назначить первого admin | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Impersonation (support mode) | ⚠️ логируется | ❌ | ❌ | ❌ | ❌ | ❌ |
| Platform settings | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

**Условия ⚠️:**

- Impersonation: каждый вход логируется в audit log с `performed_by_platform_admin = true`, требуется reason.

---

## 4. Organization / Company Structure

| Действие | platform_admin | admin | esg_manager | collector | reviewer | auditor |
|----------|:-:|:-:|:-:|:-:|:-:|:-:|
| Создать entity | ⚠️ support | ✅ | ✅ | ❌ | ❌ | ❌ |
| Редактировать entity | ⚠️ support | ✅ | ✅ | ❌ | ❌ | ❌ |
| Удалить / деактивировать entity | ⚠️ support | ⚠️ not in use | ❌ | ❌ | ❌ | ❌ |
| Создать ownership link | ⚠️ support | ✅ | ✅ | ❌ | ❌ | ❌ |
| Редактировать ownership link | ⚠️ support | ✅ | ✅ | ❌ | ❌ | ❌ |
| Удалить ownership link | ⚠️ support | ✅ | ❌ | ❌ | ❌ | ❌ |
| Создать control link | ⚠️ support | ✅ | ✅ | ❌ | ❌ | ❌ |
| Редактировать control link | ⚠️ support | ✅ | ✅ | ❌ | ❌ | ❌ |
| Удалить control link | ⚠️ support | ✅ | ❌ | ❌ | ❌ | ❌ |
| Просматривать дерево структуры | ✅ | ✅ | ✅ | ⚠️ assigned entities | ✅ RO | ✅ RO |
| Просматривать effective ownership | ✅ | ✅ | ✅ | ❌ | ✅ RO | ✅ RO |

**Условия ⚠️:**

- `platform_admin` support: все действия логируются как platform-level override
- `admin` delete entity: только если entity не используется в data_points (`ENTITY_IN_USE`, 409)
- `collector` просмотр: только entity, к которым привязаны assignments

---

## 5. Boundary

| Действие | platform_admin | admin | esg_manager | collector | reviewer | auditor |
|----------|:-:|:-:|:-:|:-:|:-:|:-:|
| Создать boundary definition | ⚠️ support | ✅ | ❌ | ❌ | ❌ | ❌ |
| Редактировать boundary definition | ⚠️ support | ✅ | ❌ | ❌ | ❌ | ❌ |
| Управлять membership (include/exclude) | ⚠️ support | ✅ | ✅ | ❌ | ❌ | ❌ |
| Пересчитать automatic memberships | ⚠️ support | ✅ | ✅ | ❌ | ❌ | ❌ |
| Применить boundary к проекту | ❌ | ⚠️ | ✅ | ❌ | ❌ | ❌ |
| Сохранить boundary snapshot | ❌ | ⚠️ | ✅ | ❌ | ❌ | ❌ |
| Просматривать boundary | ✅ | ✅ | ✅ | ⚠️ текст | ✅ RO | ✅ RO |
| Просматривать snapshot | ✅ | ✅ | ✅ | ❌ | ✅ RO | ✅ RO |
| Boundary preview (diff) | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |

**Условия ⚠️:**

- `admin` apply/snapshot: только для проектов в статусе `draft` / `in_progress`
- `collector` просмотр: только текстовый badge «Boundary: Operational Control», без доступа к деталям

---

## 6. Standards / Catalog

| Действие | platform_admin | admin | esg_manager | collector | reviewer | auditor |
|----------|:-:|:-:|:-:|:-:|:-:|:-:|
| Создать standard | ⚠️ support | ✅ | ❌ | ❌ | ❌ | ❌ |
| Редактировать standard | ⚠️ support | ✅ | ❌ | ❌ | ❌ | ❌ |
| Деактивировать standard | ⚠️ support | ⚠️ not in use | ❌ | ❌ | ❌ | ❌ |
| Создать disclosure requirement | ⚠️ support | ✅ | ❌ | ❌ | ❌ | ❌ |
| Создать requirement item | ⚠️ support | ✅ | ❌ | ❌ | ❌ | ❌ |
| Создать shared element | ⚠️ support | ✅ | ❌ | ❌ | ❌ | ❌ |
| Создать mapping | ⚠️ support | ✅ | ❌ | ❌ | ❌ | ❌ |
| Просматривать standards | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Просматривать shared elements | ✅ | ✅ | ✅ | ⚠️ assigned | ✅ | ✅ |
| Просматривать mappings | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ |

---

## 7. Projects

| Действие | platform_admin | admin | esg_manager | collector | reviewer | auditor |
|----------|:-:|:-:|:-:|:-:|:-:|:-:|
| Создать project | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Редактировать project settings | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Добавить standard к project | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Запустить project (draft → in_progress) | ❌ | ⚠️ | ✅ | ❌ | ❌ | ❌ |
| Перевести в review | ❌ | ⚠️ | ✅ | ❌ | ❌ | ❌ |
| Опубликовать project | ❌ | ⚠️ | ✅ | ❌ | ❌ | ❌ |
| Откатить published → in_progress | ❌ | ⚠️ с обоснованием | ⚠️ с обоснованием | ❌ | ❌ | ❌ |
| Архивировать project | ❌ | ⚠️ | ✅ | ❌ | ❌ | ❌ |
| Просматривать project | ⚠️ support | ✅ | ✅ | ⚠️ assigned | ⚠️ assigned | ✅ |

**Условия ⚠️:**

- `admin` project transitions: разрешено, но ESG Manager — primary owner workflow
- Откат published: обязателен комментарий, записывается в audit_log
- `collector` / `reviewer`: видят только проекты, в которых у них есть assignments

---

## 8. Assignments

| Действие | platform_admin | admin | esg_manager | collector | reviewer | auditor |
|----------|:-:|:-:|:-:|:-:|:-:|:-:|
| Создать assignment | ⚠️ support | ✅ | ✅ | ❌ | ❌ | ❌ |
| Назначить collector | ⚠️ support | ✅ | ✅ | ❌ | ❌ | ❌ |
| Назначить reviewer | ⚠️ support | ✅ | ✅ | ❌ | ❌ | ❌ |
| Назначить backup collector | ⚠️ support | ✅ | ✅ | ❌ | ❌ | ❌ |
| Удалить assignment | ⚠️ support | ✅ | ✅ | ❌ | ❌ | ❌ |
| Просматривать все assignments | ⚠️ support | ✅ | ✅ | ❌ | ❌ | ✅ |
| Просматривать свои assignments | — | — | — | ✅ | ✅ | — |
| Массовое назначение | ⚠️ support | ✅ | ✅ | ❌ | ❌ | ❌ |

**Бизнес-правила:**

- `collector_id != reviewer_id` для одного assignment (`ASSIGNMENT_ROLE_CONFLICT`, 409)
- `backup_collector_id != collector_id` и `backup_collector_id != reviewer_id`

---

## 9. Data Points

| Действие | platform_admin | admin | esg_manager | collector | reviewer | auditor |
|----------|:-:|:-:|:-:|:-:|:-:|:-:|
| Создать data point | ⚠️ support | ⚠️ | ⚠️ | ✅ assigned | ❌ | ❌ |
| Редактировать data point | ⚠️ support | ⚠️ | ⚠️ | ⚠️ own + editable status | ❌ | ❌ |
| Submit (draft → submitted) | ❌ | ⚠️ | ⚠️ | ✅ own draft | ❌ | ❌ |
| Resubmit (rejected → submitted) | ❌ | ❌ | ❌ | ✅ own rejected | ❌ | ❌ |
| Approve (in_review → approved) | ❌ | ⚠️ override | ⚠️ | ❌ | ✅ assigned | ❌ |
| Reject (in_review → rejected) | ❌ | ⚠️ override | ⚠️ | ❌ | ✅ assigned + comment | ❌ |
| Request revision | ❌ | ⚠️ override | ⚠️ | ❌ | ✅ assigned + comment | ❌ |
| Rollback (approved → draft) | ❌ | ❌ | ✅ + comment | ❌ | ❌ | ❌ |
| Просматривать data point | ⚠️ support | ✅ | ✅ | ⚠️ own | ⚠️ assigned | ✅ |
| Find reuse | ❌ | ✅ | ✅ | ⚠️ own draft | ❌ | ❌ |

**Условия ⚠️:**

- Collector edit: только свои data points + статус `draft` / `rejected` / `needs_revision`
- Admin/ESG Manager override: логируется как admin action
- Reject/Request revision: **комментарий обязателен** (`REVIEW_COMMENT_REQUIRED`, 422)
- Rollback: **комментарий обязателен**, записывается в audit_log

**Locking rules (по статусу):**

| Status | Collector может edit | Reviewer может act | ESG Manager может rollback |
|--------|:-:|:-:|:-:|
| `draft` | ✅ | ❌ | ❌ |
| `submitted` | ❌ | ❌ (auto → in_review) | ❌ |
| `in_review` | ❌ | ✅ | ❌ |
| `approved` | ❌ | ❌ | ✅ |
| `rejected` | ✅ | ❌ | ❌ |
| `needs_revision` | ✅ | ❌ | ❌ |

---

## 10. Evidence

| Действие | platform_admin | admin | esg_manager | collector | reviewer | auditor |
|----------|:-:|:-:|:-:|:-:|:-:|:-:|
| Создать evidence (file/link) | ⚠️ support | ✅ | ✅ | ✅ assigned | ❌ | ❌ |
| Редактировать evidence metadata | ⚠️ support | ✅ | ✅ | ⚠️ own + before submit | ❌ | ❌ |
| Upload file | ⚠️ support | ✅ | ✅ | ✅ assigned | ❌ | ❌ |
| Link evidence → data point | ⚠️ support | ✅ | ✅ | ✅ own dp | ❌ | ❌ |
| Unlink evidence from data point | ⚠️ support | ✅ | ⚠️ not approved | ⚠️ own + before approve | ❌ | ❌ |
| Link evidence → requirement item | ⚠️ support | ✅ | ✅ | ❌ | ❌ | ❌ |
| Delete evidence | ⚠️ support | ⚠️ not in approved scope | ⚠️ not in approved scope | ⚠️ own + draft | ❌ | ❌ |
| Просматривать evidence | ⚠️ support | ✅ | ✅ | ⚠️ own | ✅ assigned | ✅ |
| Скачивать файл | ⚠️ support | ✅ | ✅ | ⚠️ own | ✅ assigned | ✅ |

**Условия ⚠️:**

- Delete evidence: `EVIDENCE_IN_USE` (409) если привязан к approved data point
- Collector edit: только до submit (`data_point.status == 'draft'`)

---

## 11. Review

| Действие | platform_admin | admin | esg_manager | collector | reviewer | auditor |
|----------|:-:|:-:|:-:|:-:|:-:|:-:|
| Просматривать review queue | ⚠️ support | ✅ | ✅ | ❌ | ✅ assigned | ❌ |
| Approve single | ❌ | ⚠️ override | ⚠️ | ❌ | ✅ assigned | ❌ |
| Reject single | ❌ | ⚠️ override | ⚠️ | ❌ | ✅ assigned + comment | ❌ |
| Request revision | ❌ | ⚠️ override | ⚠️ | ❌ | ✅ assigned + comment | ❌ |
| Batch approve | ❌ | ⚠️ override | ⚠️ | ❌ | ✅ assigned | ❌ |
| Batch reject | ❌ | ⚠️ override | ⚠️ | ❌ | ✅ assigned + comment | ❌ |
| Комментировать | ⚠️ support | ✅ | ✅ | ⚠️ own scope | ✅ assigned | ❌ |
| Resolve comment | ⚠️ support | ✅ | ✅ | ❌ | ✅ own comment | ❌ |

**Batch rules:**

- Batch reject: комментарий **обязателен** (единый для всех)
- Batch approve: комментарий **опционален** (рекомендован)
- Summary preview перед batch action **обязателен**

---

## 12. Merge View

| Действие | platform_admin | admin | esg_manager | collector | reviewer | auditor |
|----------|:-:|:-:|:-:|:-:|:-:|:-:|
| Просматривать merge view | ⚠️ support | ✅ | ✅ | ❌ | ✅ RO | ✅ RO |
| Impact preview (add standard) | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Merge coverage report | ⚠️ support | ✅ | ✅ | ❌ | ✅ RO | ✅ RO |
| Drill-down из merge view | ⚠️ support | ✅ | ✅ | ❌ | ⚠️ assigned | ✅ RO |

---

## 13. Completeness / Dashboard

| Действие | platform_admin | admin | esg_manager | collector | reviewer | auditor |
|----------|:-:|:-:|:-:|:-:|:-:|:-:|
| Просматривать overall completion | ⚠️ support | ✅ | ✅ | ⚠️ own scope | ⚠️ assigned scope | ✅ |
| Drill-down по disclosure | ⚠️ support | ✅ | ✅ | ⚠️ own scope | ⚠️ assigned scope | ✅ |
| Drill-down по entity | ⚠️ support | ✅ | ✅ | ❌ | ⚠️ | ✅ |
| Drill-down по user | ⚠️ support | ✅ | ✅ | ❌ | ❌ | ✅ |
| Trigger manual recalculate | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |

**Условия ⚠️:**

- `collector` own scope: видит completeness только по своим assignments
- `reviewer` assigned scope: видит completeness по назначенному review scope

---

## 14. Export / Reporting

| Действие | platform_admin | admin | esg_manager | collector | reviewer | auditor |
|----------|:-:|:-:|:-:|:-:|:-:|:-:|
| Readiness check | ❌ | ✅ | ✅ | ❌ | ✅ RO | ✅ RO |
| Запустить export (GRI Index, PDF, Excel) | ❌ | ⚠️ | ✅ | ❌ | ❌ | ❌ |
| Скачать export | ⚠️ support | ✅ | ✅ | ❌ | ⚠️ RO | ✅ |
| Publish project | ❌ | ⚠️ с обоснованием | ✅ | ❌ | ❌ | ❌ |
| Просматривать export metadata | ⚠️ support | ✅ | ✅ | ❌ | ⚠️ RO | ✅ |

---

## 15. Notifications

| Действие | platform_admin | admin | esg_manager | collector | reviewer | auditor |
|----------|:-:|:-:|:-:|:-:|:-:|:-:|
| Получать уведомления | ✅ platform | ✅ | ✅ | ✅ own | ✅ own | ❌ |
| Просматривать уведомления | ✅ | ✅ | ✅ | ✅ own | ✅ own | ❌ |
| Отметить прочитанным | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Настройки уведомлений | ✅ platform | ✅ | ✅ | ✅ own | ✅ own | ❌ |

---

## 16. Audit Log

| Действие | platform_admin | admin | esg_manager | collector | reviewer | auditor |
|----------|:-:|:-:|:-:|:-:|:-:|:-:|
| Просматривать platform audit | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Просматривать tenant audit | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ |
| Фильтровать по user/entity/date | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ |
| Export audit log | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |

---

## 17. User Management

| Действие | platform_admin | admin | esg_manager | collector | reviewer | auditor |
|----------|:-:|:-:|:-:|:-:|:-:|:-:|
| Создать пользователя (tenant) | ⚠️ support | ✅ | ❌ | ❌ | ❌ | ❌ |
| Изменить роль пользователя | ⚠️ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Деактивировать пользователя | ⚠️ support | ✅ | ❌ | ❌ | ❌ | ❌ |
| Пригласить пользователя | ⚠️ support | ✅ | ⚠️ | ❌ | ❌ | ❌ |
| Просматривать список пользователей | ✅ all | ✅ own org | ⚠️ limited | ❌ | ❌ | ❌ |

**Условия ⚠️:**

- `platform_admin` change role: может назначить platform_admin; admin не может
- `esg_manager` invite: может пригласить collector/reviewer (не admin)

---

## 18. AI Assistant

| Действие | platform_admin | admin | esg_manager | collector | reviewer | auditor |
|----------|:-:|:-:|:-:|:-:|:-:|:-:|
| Field explain | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Requirement explain | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Contextual Q&A | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Boundary explain | ✅ | ✅ | ✅ | ⚠️ simplified | ✅ | ✅ |
| Completeness explain | ✅ | ✅ | ✅ | ⚠️ own scope | ⚠️ assigned | ✅ |
| Review assist | ⚠️ support | ⚠️ | ⚠️ | ❌ | ✅ | ❌ |
| Evidence guidance | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Suggested actions | ✅ | ✅ | ✅ | ⚠️ limited | ⚠️ limited | ❌ |

**AI Gate restrictions** (см. TZ-AIAssistance.md раздел 10):

- Все AI ответы фильтруются по роли через Context Gate + Output Gate
- `collector`: AI не раскрывает boundary rules, чужие assignments, analytical insights
- `auditor`: AI не предлагает actions (read-only mode)

---

## 19. Object-level правила (сводка)

Дополнительно к role check, каждый запрос проверяется:

| Правило | Описание | Где применяется |
|---------|----------|----------------|
| Tenant isolation | `user.organization_id == object.organization_id` | Все tenant endpoints |
| Collector ownership | `assignment.collector_id == user.id` | Data points, evidence |
| Reviewer scope | `assignment.reviewer_id == user.id` | Review queue |
| Entity boundary | Entity входит в project boundary | Data collection, assignments |
| Data point scope | Data point принадлежит текущему project | Data entry, review |
| Workflow state | Действие допустимо в текущем статусе | Submit, approve, reject, rollback |
| Project lock | Project status разрешает операцию | Edit, publish, archive |
| Snapshot immutable | Published snapshot нельзя изменить | Boundary snapshot |
| Evidence in use | Нельзя удалить evidence в approved scope | Evidence delete |

---

## 20. Ограничения по ролям (сводка)

### 20.1. Collector

- Только свои assignments;
- Не видит всю структуру группы (только assigned entities);
- Не управляет boundary;
- Не видит Merge View;
- Не видит чужие data points;
- Может edit только в editable statuses (draft, rejected, needs_revision).

### 20.2. Reviewer

- Не изменяет данные напрямую;
- Только approve / reject / request revision;
- Комментарий обязателен при reject и needs_revision;
- Видит только assigned review scope;
- Не управляет структурой, boundary, assignments.

### 20.3. Auditor

- **Read-only** — никаких write операций;
- Доступ к audit log, snapshots, exports;
- Не может approve / reject / comment;
- Не получает suggested actions от AI.

### 20.4. ESG Manager

- Primary owner workflow проекта;
- Может rollback approved → draft (с обоснованием);
- Не может менять структуру стандартов (это admin);
- Не может вводить данные напрямую (если нет role collector).

### 20.5. Admin

- Полный доступ **внутри своей организации**;
- Не может создавать tenants;
- Не видит другие организации;
- Override actions логируются отдельно.

### 20.6. Platform Admin

- **Не должен** использоваться как рабочая tenant-роль;
- Только provisioning / support;
- Все действия логируются как platform-level events;
- Support mode = impersonation с обоснованием.

---

## 21. Policy layer реализация

Все проверки **централизованы** в policy layer (не разбросаны по routers/services):

```python
# app/policies/ — один файл на домен
#
# auth_policy.py      → tenant isolation, role check
# platform_policy.py  → platform_admin checks
# data_point_policy.py → can_edit, can_submit, is_locked
# review_policy.py    → can_approve, requires_comment
# evidence_policy.py  → can_delete, not_in_approved_scope
# boundary_policy.py  → snapshot_immutable, boundary_inclusion
# assignment_policy.py → collector_reviewer_conflict
# project_policy.py   → project_locked, can_publish
# ai_policy.py        → tool_access, context_filter, rate_limit
```

> **Архитектурное требование:** нет inline permission checks в routers или services. Все проверки — через `self.policy.check_*()`. Нарушение = blocking PR issue. См. TZ-BackendArchitecture.md раздел 7.4.

---

## 22. Критерии приёмки

- [ ] Ни один endpoint не доступен без проверки роли
- [ ] Scope учитывается всегда (tenant isolation на каждом запросе)
- [ ] Collector не видит чужие data points / assignments
- [ ] Reviewer не может редактировать данные (только approve/reject)
- [ ] Auditor = strict read-only (нет write endpoints)
- [ ] platform_admin не используется как обычный tenant пользователь
- [ ] Object-level checks работают (ownership, workflow state, boundary scope)
- [ ] Все проверки централизованы в policy layer
- [ ] Reject / needs_revision / rollback требуют комментарий
- [ ] Admin override действия логируются отдельно
- [ ] platform_admin impersonation логируется с reason
- [ ] AI Gate фильтрует tools и контекст по роли
