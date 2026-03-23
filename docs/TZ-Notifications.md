# ТЗ: Notifications & Events

**Модуль:** Notification Service / Event System
**Версия:** 1.0
**Дата:** 2026-03-22
**Статус:** Согласован
**Зависимости:** ARCHITECTURE.md, TZ-BackendArchitecture.md

---

## 1. Цель

Обеспечить:

- уведомления пользователям о ключевых событиях;
- поддержку workflow (submit → notify reviewer, reject → notify collector);
- реакцию на события системы (completeness change, boundary change);
- внешние интеграции через webhooks (Phase 2).

---

## 2. Типы уведомлений

| Тип | Канал | Обязательность |
|-----|-------|---------------|
| **In-app** | UI (notification center) | Обязательно (MVP) |
| **Email** | SMTP | Для критичных событий (MVP) |
| **Webhook** | HTTP POST | Phase 2 |
| **Digest** | Email (сводка) | Phase 3 |

---

## 3. Основные события

### 3.1. Assignments

| Событие | Описание | Получатели | Канал |
|---------|----------|-----------|-------|
| `assignment_created` | Метрика назначена | Collector | in-app + email |
| `assignment_updated` | Назначение изменено (collector/reviewer/deadline) | Affected user | in-app |
| `assignment_overdue` | Дедлайн просрочен | Collector + ESG Manager | in-app + email |
| `assignment_escalated` | SLA breach → backup collector | Backup collector + ESG Manager | in-app + email |

### 3.2. Data Points

| Событие | Описание | Получатели | Канал |
|---------|----------|-----------|-------|
| `data_point_submitted` | Данные отправлены на review | Reviewer | in-app + email |
| `data_point_approved` | Данные утверждены | Collector | in-app |
| `data_point_rejected` | Данные отклонены | Collector | in-app + email |
| `data_point_needs_revision` | Требуется доработка | Collector | in-app + email |
| `data_point_rolled_back` | Откат approved → draft | Collector + Reviewer | in-app + email |

### 3.3. Review

| Событие | Описание | Получатели | Канал |
|---------|----------|-----------|-------|
| `review_requested` | Данные ожидают review | Reviewer | in-app + email |
| `batch_review_completed` | Массовый approve/reject завершён | ESG Manager | in-app |

### 3.4. Project

| Событие | Описание | Получатели | Канал |
|---------|----------|-----------|-------|
| `project_started` | Проект запущен (draft → active) | All assigned users | in-app + email |
| `project_in_review` | Проект перешёл в review | ESG Manager + Reviewers | in-app |
| `project_published` | Проект опубликован | Admin + ESG Manager | in-app + email |
| `project_deadline_approaching` | До дедлайна 3/7 дней | All assigned users | in-app + email |

### 3.5. Boundary

| Событие | Описание | Получатели | Канал |
|---------|----------|-----------|-------|
| `boundary_changed` | Boundary изменён для проекта | ESG Manager + affected collectors | in-app + email |
| `boundary_snapshot_created` | Snapshot сохранён | ESG Manager | in-app |
| `assignments_affected_by_boundary` | Boundary change повлиял на assignments | Affected collectors | in-app + email |

### 3.6. Completeness

| Событие | Описание | Получатели | Канал |
|---------|----------|-----------|-------|
| `completeness_100_percent` | Все disclosures complete | ESG Manager | in-app + email |
| `completeness_recalculated` | Completeness пересчитан (boundary/data change) | ESG Manager | in-app |

### 3.7. System / Users

| Событие | Описание | Получатели | Канал |
|---------|----------|-----------|-------|
| `user_invited` | Приглашение в организацию | Invited user | email |
| `role_changed` | Роль пользователя изменена | Affected user | in-app + email |
| `sla_breach_level_1` | Просрочка 3+ дня | Backup collector + ESG Manager | in-app + email |
| `sla_breach_level_2` | Просрочка 7+ дня | Admin | in-app + email |

---

## 4. Матрица получателей

| Событие | collector | reviewer | esg_manager | admin | auditor |
|---------|:-:|:-:|:-:|:-:|:-:|
| assignment_created | ✅ own | ✅ own | — | — | — |
| assignment_overdue | ✅ own | — | ✅ | — | — |
| data_point_submitted | — | ✅ assigned | — | — | — |
| data_point_approved | ✅ own | — | — | — | — |
| data_point_rejected | ✅ own | — | — | — | — |
| project_started | ✅ assigned | ✅ assigned | ✅ | ✅ | — |
| project_published | — | — | ✅ | ✅ | — |
| boundary_changed | ✅ affected | — | ✅ | — | — |
| completeness_100 | — | — | ✅ | — | — |
| sla_breach_level_2 | — | — | — | ✅ | — |

---

## 5. Критичность и каналы

| Критичность | Канал | Примеры |
|-------------|-------|---------|
| **Critical** | in-app + email | reject, SLA breach, deadline |
| **Important** | in-app + email | submit, approve, project start |
| **Info** | in-app only | completeness update, boundary change |
| **Low** | in-app only | batch review completed |

---

## 6. Поведение

### 6.1. Immediate (синхронно с событием)

- `data_point_submitted`
- `data_point_rejected`
- `data_point_approved`
- `assignment_created`

### 6.2. Scheduled (cron job)

| Событие | Расписание |
|---------|-----------|
| `assignment_overdue` | Daily check (утро) |
| `project_deadline_approaching` | Daily check (за 7, 3, 1 день) |
| `sla_breach_level_1` | Daily check (+3 дня после deadline) |
| `sla_breach_level_2` | Daily check (+7 дней после deadline) |

### 6.3. Digest (Phase 3)

- Daily summary: «5 data points submitted, 2 overdue, 1 rejected»
- Weekly summary для ESG Manager

---

## 7. Модель данных

### 7.1. notifications

```sql
create table notifications (
    id                  bigserial primary key,
    organization_id     bigint not null references organizations(id) on delete cascade,
    user_id             bigint not null references users(id) on delete cascade,
    type                text not null,
    title               text not null,
    message             text not null,
    entity_type         text,              -- 'data_point', 'project', 'assignment', ...
    entity_id           bigint,
    severity            text not null default 'info' check (severity in ('critical', 'important', 'info', 'low')),
    channel             text not null default 'in_app' check (channel in ('in_app', 'email', 'both')),
    is_read             boolean not null default false,
    read_at             timestamptz,
    email_sent          boolean not null default false,
    email_sent_at       timestamptz,
    created_at          timestamptz not null default now()
);

create index idx_notifications_user on notifications(user_id, is_read);
create index idx_notifications_org on notifications(organization_id);
create index idx_notifications_created on notifications(created_at);
create index idx_notifications_type on notifications(type);
```

### 7.2. webhook_endpoints (Phase 2)

```sql
create table webhook_endpoints (
    id                  bigserial primary key,
    organization_id     bigint not null references organizations(id) on delete cascade,
    url                 text not null,
    secret              text not null,       -- HMAC signing secret
    events              text[] not null,      -- ['data_point.submitted', 'project.published']
    is_active           boolean not null default true,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now()
);
```

### 7.3. webhook_deliveries (Phase 2)

```sql
create table webhook_deliveries (
    id                  bigserial primary key,
    webhook_endpoint_id bigint not null references webhook_endpoints(id) on delete cascade,
    event_type          text not null,
    payload             jsonb not null,
    status              text not null default 'pending' check (status in ('pending', 'success', 'failed', 'dead_letter')),
    http_status         integer,
    response_body       text,
    attempt             integer not null default 0,
    max_attempts        integer not null default 5,
    next_retry_at       timestamptz,
    created_at          timestamptz not null default now(),
    delivered_at        timestamptz
);

create index idx_webhook_deliveries_status on webhook_deliveries(status) where status = 'pending';
create index idx_webhook_deliveries_endpoint on webhook_deliveries(webhook_endpoint_id);
```

---

## 8. Структура уведомления

### 8.1. In-app notification

```json
{
  "id": 1,
  "type": "data_point_rejected",
  "title": "Data point rejected",
  "message": "Your Scope 1 emission data was rejected by Петрова А.Б.",
  "entityType": "data_point",
  "entityId": 9001,
  "severity": "critical",
  "isRead": false,
  "createdAt": "2026-03-22T10:00:00Z"
}
```

### 8.2. Webhook payload (Phase 2)

```json
{
  "event": "data_point.submitted",
  "timestamp": "2026-03-22T10:00:00Z",
  "data": {
    "dataPointId": 9001,
    "projectId": 101,
    "sharedElementCode": "GHG_SCOPE_1_TOTAL",
    "submittedBy": "ivanov@company.kz",
    "entityName": "Plant A"
  }
}
```

**Webhook security:**

- HMAC-SHA256 signature в header `X-Webhook-Signature`;
- Timestamp в header `X-Webhook-Timestamp` (replay protection ± 5 min).

---

## 9. API

### 9.1. Notifications

```
GET    /api/notifications                    — список (filter: type, is_read, severity)
PATCH  /api/notifications/:id/read          — отметить прочитанным
POST   /api/notifications/read-all          — отметить все прочитанными
GET    /api/notifications/unread-count       — количество непрочитанных
```

### 9.2. Webhooks (Phase 2)

```
GET    /api/webhooks                         — список endpoints
POST   /api/webhooks                         — создать endpoint
PATCH  /api/webhooks/:id                     — обновить
DELETE /api/webhooks/:id                     — удалить
GET    /api/webhooks/:id/deliveries          — история доставок
POST   /api/webhooks/:id/test               — отправить тестовый webhook
```

### 9.3. Permissions

| Endpoint | admin | esg_manager | collector | reviewer | auditor |
|----------|:-:|:-:|:-:|:-:|:-:|
| `GET /notifications` | ✅ own | ✅ own | ✅ own | ✅ own | ❌ |
| `PATCH /notifications/:id/read` | ✅ own | ✅ own | ✅ own | ✅ own | ❌ |
| `POST /notifications/read-all` | ✅ | ✅ | ✅ | ✅ | ❌ |
| `GET /webhooks` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `POST /webhooks` | ✅ | ❌ | ❌ | ❌ | ❌ |

---

## 10. Notification Service реализация

```python
# app/services/notification_service.py

class NotificationService:

    async def notify(
        self,
        user_id: int,
        org_id: int,
        type: str,
        title: str,
        message: str,
        entity_type: str | None = None,
        entity_id: int | None = None,
        severity: str = "info",
    ) -> None:
        """Create in-app notification and optionally send email."""
        # 1. Create in-app notification
        notification = await self.notification_repo.create(
            organization_id=org_id,
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            entity_type=entity_type,
            entity_id=entity_id,
            severity=severity,
        )

        # 2. Send email for critical/important
        if severity in ("critical", "important"):
            await self._send_email(user_id, title, message)

    async def notify_many(
        self,
        user_ids: list[int],
        org_id: int,
        **kwargs,
    ) -> None:
        """Notify multiple users."""
        for user_id in user_ids:
            await self.notify(user_id=user_id, org_id=org_id, **kwargs)
```

### 10.1. Event → Notification mapping

```python
# app/events/handlers/notification_handler.py

class NotificationEventHandler:

    async def on_data_point_submitted(self, event: DataPointSubmitted):
        assignment = await self.assignment_repo.get_for_data_point(event.data_point_id)
        if assignment.reviewer_id:
            await self.notification_service.notify(
                user_id=assignment.reviewer_id,
                org_id=assignment.organization_id,
                type="data_point_submitted",
                title="New data point for review",
                message=f"Data point submitted by collector, waiting for your review.",
                entity_type="data_point",
                entity_id=event.data_point_id,
                severity="important",
            )

    async def on_data_point_rejected(self, event: DataPointRejected):
        dp = await self.dp_repo.get_by_id(event.data_point_id)
        assignment = await self.assignment_repo.get_for_data_point(dp.id)
        await self.notification_service.notify(
            user_id=assignment.collector_id,
            org_id=dp.organization_id,
            type="data_point_rejected",
            title="Data point rejected",
            message=f"Your submission was rejected: {event.comment}",
            entity_type="data_point",
            entity_id=dp.id,
            severity="critical",
        )

    async def on_boundary_applied(self, event: BoundaryAppliedToProject):
        project = await self.project_repo.get_by_id(event.project_id)
        managers = await self.user_repo.get_by_role(
            project.organization_id, "esg_manager"
        )
        await self.notification_service.notify_many(
            user_ids=[m.id for m in managers],
            org_id=project.organization_id,
            type="boundary_changed",
            title="Project boundary changed",
            message=f"Boundary updated for project.",
            entity_type="project",
            entity_id=event.project_id,
            severity="info",
        )
```

---

## 11. Правила

| Правило | Описание |
|---------|----------|
| **Дедупликация** | Не создавать дублирующие уведомления для одного события |
| **No self-notify** | Не отправлять уведомления автору действия |
| **Batch collapse** | Batch approve → одно уведомление «5 data points approved» |
| **User preferences** | Phase 3: пользователь может отключить email для info-level |
| **Timezone** | Email отправляется с учётом timezone пользователя (Phase 3) |

---

## 12. Webhook Events (Phase 2)

### 12.1. Доступные события

| Event | Описание |
|-------|----------|
| `data_point.submitted` | Data point отправлен на review |
| `data_point.approved` | Data point утверждён |
| `data_point.rejected` | Data point отклонён |
| `project.started` | Проект запущен |
| `project.published` | Проект опубликован |
| `evidence.created` | Evidence создан |
| `boundary.changed` | Boundary изменён |
| `completeness.updated` | Completeness пересчитан |

### 12.2. Retry

| Параметр | Значение |
|----------|----------|
| Max attempts | 5 |
| Strategy | Exponential backoff (1s, 2s, 4s, 8s, 16s) |
| Timeout per attempt | 10 сек |
| Dead letter | После 5 failed → `status = 'dead_letter'`, alert admin |
| Idempotency | Receiver может получить дубликат — должен обработать idempotently |

---

## 13. Критерии приёмки

- [ ] Пользователь получает in-app уведомления по ключевым событиям
- [ ] Email отправляется для critical / important событий
- [ ] Нет дублирования уведомлений
- [ ] Уведомления не отправляются автору действия
- [ ] Уведомления связаны с объектами (entity_type + entity_id → кликабельная ссылка)
- [ ] `GET /notifications/unread-count` работает (для badge в UI)
- [ ] Mark as read / read-all работает
- [ ] Scheduled notifications (overdue, deadline approaching) работают через cron
- [ ] Webhook endpoint CRUD работает (Phase 2)
- [ ] Webhook delivery с retry и dead letter (Phase 2)
- [ ] Webhook payload подписан HMAC-SHA256 (Phase 2)
