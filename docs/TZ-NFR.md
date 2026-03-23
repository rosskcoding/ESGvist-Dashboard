# ТЗ: Non-Functional Requirements (NFR)

**Версия:** 1.0
**Дата:** 2026-03-22
**Статус:** Согласован

---

## 1. Цель

Определить требования к производительности, надёжности, безопасности, масштабируемости и наблюдаемости для обеспечения стабильной работы системы.

---

## 2. Производительность

### 2.1. API Latency (SLA)

| Тип запроса | SLA (p95) | Пример |
|-------------|-----------|--------|
| Простые GET (list, read) | ≤ 300 ms | `GET /standards`, `GET /data-points/:id` |
| Сложные GET (merge, completeness) | ≤ 700 ms | `GET /projects/:id/merge`, `GET /completeness` |
| POST / PUT (сохранение данных) | ≤ 500 ms | `POST /data-points`, `PATCH /entities/:id` |
| Gate check | ≤ 200 ms | `POST /gate-check` |
| Auth (login, token refresh) | ≤ 300 ms | `POST /auth/login` |
| Pagination | обязательна | max `page_size = 100`, default `20` |

### 2.2. AI Latency

| Тип запроса | SLA | Streaming |
|-------------|-----|-----------|
| Inline explain (поле) | ≤ 2 сек | Нет |
| Contextual ask | ≤ 4 сек | Да (first chunk < 500ms) |
| Review assist | ≤ 3 сек | Нет |
| Completeness explain | ≤ 4 сек | Опционально |
| Timeout (hard limit) | 15 сек | — |

### 2.3. Export

| Тип | SLA | Метод |
|-----|-----|-------|
| Small export (< 50 disclosures) | ≤ 5 сек | Синхронный |
| Large export | Async (background job) | Polling / notification |
| GRI Content Index (PDF) | ≤ 10 сек | Синхронный |
| Full data dump (Excel) | Async | Background job |

### 2.4. Completeness Engine

| Операция | SLA |
|----------|-----|
| Single requirement_item recalculate | ≤ 100 ms |
| Full project recalculation | ≤ 5 сек |
| Async execution | Не блокирует UI |

### 2.5. Database

| Метрика | Требование |
|---------|-----------|
| Query timeout | 30 сек (hard limit) |
| Connection pool | 20-50 connections per service |
| Slow query threshold | > 1 сек → log warning |
| Indexes | Все FK + часто фильтруемые поля |

---

## 3. Надёжность

### 3.1. Доступность

| Метрика | Значение |
|---------|----------|
| Target uptime | 99.5%+ |
| Planned maintenance window | 30 мин/месяц |
| Recovery time (RTO) | ≤ 1 час |
| Recovery point (RPO) | ≤ 1 час (DB backups) |

### 3.2. Graceful Degradation

| Компонент | Поведение при отказе |
|-----------|---------------------|
| AI сервис | Fallback → static help text, UI badge «AI temporarily unavailable» |
| Export service | Retry → уведомление пользователю |
| File storage (S3/MinIO) | Upload disabled, existing files cached |
| Redis (queue/cache) | In-process fallback для критичных операций |
| Email service | Queue → retry, in-app notification сохраняется |

### 3.3. Retry политика

**Webhooks:**

| Параметр | Значение |
|----------|----------|
| Max retries | 5 |
| Strategy | Exponential backoff (1s, 2s, 4s, 8s, 16s) |
| Dead letter | После 5 failed → dead letter queue + alert admin |

**Background jobs:**

| Параметр | Значение |
|----------|----------|
| Max retries | 3 (configurable per job type) |
| Strategy | Exponential backoff |
| Dead letter | Phase 2 (Redis-based) |

### 3.4. Идемпотентность

- POST endpoints поддерживают idempotency через `X-Idempotency-Key` header;
- Webhook delivery — idempotent (receiver может получить дубликат);
- Background jobs — idempotent (safe to re-run).

### 3.5. Data Integrity

- Все multi-step operations — **транзакционные** (rollback при ошибке);
- Foreign key constraints enforced на DB level;
- Soft delete для критичных сущностей (evidence, entities);
- Audit log — append-only (immutable).

---

## 4. Безопасность

### 4.1. Аутентификация

| Параметр | Значение |
|----------|----------|
| Механизм | JWT (access + refresh) |
| Access token TTL | 15 минут |
| Refresh token TTL | 7 дней |
| Password hashing | bcrypt (passlib) |
| Phase 3 | SSO (SAML 2.0 / OAuth 2.0), 2FA (TOTP) |

### 4.2. Авторизация

- RBAC + scope-aware (см. TZ-PermissionMatrix.md);
- Object-level проверки обязательны;
- Policy layer централизован (см. TZ-BackendArchitecture.md раздел 5.6).

### 4.3. Tenant Isolation

- Данные **строго изолированы** по `organization_id`;
- Запрещены cross-tenant запросы;
- `X-Organization-Id` header обязателен для tenant endpoints;
- DB queries **всегда** фильтруются по `organization_id`.

### 4.4. AI безопасность

- Context filtering по роли (Context Gate);
- Prompt sanitization (Prompt Gate);
- Tool access control по роли (Tool Access Gate);
- Output validation (Output Gate);
- Rate limiting по роли;
- Подробнее: TZ-AIAssistance.md раздел 10.

### 4.5. File Security (Evidence)

| Параметр | Значение |
|----------|----------|
| Mime type validation | Whitelist: PDF, XLSX, XLS, DOC, DOCX, JPG, PNG, CSV |
| Max file size | 10 MB (configurable, max 50 MB) |
| Virus scan | Phase 3 (ClamAV) |
| Storage | Private bucket, pre-signed URLs для download |
| Upload | Multipart upload через backend (не direct S3) |

### 4.6. Transport Security

| Параметр | Значение |
|----------|----------|
| Protocol | HTTPS only (TLS 1.3) |
| CORS | Whitelist origins |
| HSTS | Enabled |
| Rate limiting | 100 req/min per user (API), role-based для AI |

### 4.7. Input Validation

- **Все** inputs валидируются через Pydantic v2 schemas;
- SQL injection: SQLAlchemy parameterized queries (no raw SQL from user input);
- XSS: output encoding, CSP headers;
- Path traversal: file names sanitized.

---

## 5. Хранение данных

### 5.1. Evidence Files

| Параметр | Значение |
|----------|----------|
| Storage | S3-compatible (MinIO dev / S3 prod) |
| Max size | Configurable (default 10 MB, max 50 MB) |
| Metadata | PostgreSQL (`evidence_files` table) |
| Retention | Пока organization active |
| Backup | S3 versioning (prod) |

### 5.2. Audit Logs

| Параметр | Значение |
|----------|----------|
| Retention | Минимум 3 года |
| Mutability | **Immutable** (append-only) |
| Storage | PostgreSQL (`audit_log` table) |
| Archival | Phase 3: move old records to cold storage |

### 5.3. AI Interaction Logs

| Параметр | Значение |
|----------|----------|
| Retention | 1 год |
| Content | Request context summary + response summary (не полный prompt) |
| Access | Только `admin` / `platform_admin` |
| PII | Не хранить user questions содержащие PII |

### 5.4. Database Backups

| Параметр | Значение |
|----------|----------|
| Frequency | Daily (full) + hourly (WAL) |
| Retention | 30 дней |
| Testing | Monthly restore test |

---

## 6. Масштабируемость

### 6.1. Backend

- **Stateless API** — нет сессий на сервере (JWT + Redis для refresh tokens);
- Горизонтальное масштабирование — добавление инстансов за load balancer;
- Connection pooling — PgBouncer (transaction mode).

### 6.2. Background Jobs

- Async processing через **arq** (MVP) → **Celery** (Phase 2+);
- Redis как message broker;
- Separate worker process(es).

### 6.3. Database

- Индексирование всех FK + часто фильтруемых полей;
- Pagination **обязательна** на всех list endpoints;
- Partial indexes для hot queries (`WHERE is_active = true`);
- Read replicas (Phase 3) для тяжёлых read queries.

### 6.4. Capacity Targets (MVP)

| Метрика | Значение |
|---------|----------|
| Concurrent users | 50 |
| Organizations (tenants) | 10 |
| Data points per project | 10,000 |
| Standards per project | 5 |
| Entities per organization | 100 |
| Evidence files per org | 1,000 |

---

## 7. Observability

### 7.1. Logging

**Формат:** Structured JSON (structlog).

**Что логировать:**

| Категория | Примеры |
|-----------|---------|
| API requests | method, path, status, latency, user_id, request_id |
| Errors | stack trace, context, request_id |
| Workflow transitions | entity_type, from_status, to_status, user_id |
| Gate failures | action, failed_codes, user_id |
| AI calls | action, model, tokens, latency, tools_used |
| Webhook delivery | url, status, retry_count |
| Slow queries | query, duration, params |

**Log levels:**

| Level | Когда |
|-------|-------|
| ERROR | Unhandled exceptions, DB errors, external service failures |
| WARN | Slow queries, retry attempts, gate warnings |
| INFO | API requests, workflow transitions, login/logout |
| DEBUG | Detailed query logs, AI prompts (dev only) |

### 7.2. Tracing

- `request_id` (UUID) на каждый HTTP запрос;
- Передаётся через всю цепочку: API → Service → Repository → DB;
- Включается в response header `X-Request-ID`;
- Связывание: API request → background job → webhook → AI call.

### 7.3. Metrics (Phase 2+)

| Метрика | Тип |
|---------|-----|
| API latency (p50, p95, p99) | Histogram |
| Error rate (по endpoint) | Counter |
| Active users | Gauge |
| Completeness Engine execution time | Histogram |
| AI usage (tokens, calls, latency) | Counter + Histogram |
| Job success/failure rate | Counter |
| Queue depth | Gauge |
| DB connection pool utilization | Gauge |

### 7.4. Health Checks

```
GET /api/health         — basic (API alive)
GET /api/health/db      — database connectivity
GET /api/health/storage — file storage connectivity
GET /api/health/redis   — Redis connectivity
```

**Response:**

```json
{
  "status": "healthy",
  "checks": {
    "database": "ok",
    "storage": "ok",
    "redis": "ok"
  },
  "version": "1.0.0",
  "uptime": 86400
}
```

---

## 8. Fallback поведение

| Компонент | Fallback | Пользователь видит |
|-----------|----------|-------------------|
| AI недоступен | Static help text | Badge «AI temporarily unavailable» |
| Export fail | Retry (3 attempts) | «Export failed, retrying...» → notification |
| Webhook fail | Retry + dead letter | Admin alert в dashboard |
| Gate error | Block + structured message | Inline error / modal с причинами |
| File upload fail | Retry | «Upload failed, please try again» |
| Email fail | Queue + retry | In-app notification сохраняется |
| Redis fail | In-process fallback | Degraded performance, no cache |

---

## 9. Браузеры

| Браузер | Поддержка |
|---------|-----------|
| Chrome (latest 2 versions) | Primary |
| Edge (latest 2 versions) | Full |
| Safari (latest 2 versions) | Full |
| Firefox (latest 2 versions) | Best effort |
| Mobile browsers | Phase 3 (responsive, не native app) |

---

## 10. Критерии приёмки NFR

- [ ] API latency укладывается в SLA (p95)
- [ ] AI fallback работает при недоступности LLM
- [ ] Ошибки обрабатываются корректно (structured ErrorResponse)
- [ ] Нет утечек данных между tenants (tenant isolation)
- [ ] AI не нарушает безопасность (Gate Layer)
- [ ] Все действия логируются (structured JSON logs)
- [ ] request_id присутствует в каждом запросе
- [ ] Health checks работают
- [ ] File upload валидирует mime type и размер
- [ ] Pagination работает на всех list endpoints
- [ ] Retry policy работает для webhooks и jobs
- [ ] Graceful degradation при отказе внешних сервисов
