# ТЗ: Platform Administration и расширение ролевой модели

**Модуль:** Platform Administration / Role Model v2
**Версия:** 1.0
**Дата:** 2026-03-22
**Статус:** Согласован

---

## 1. Цель изменения

Зафиксировать разделение полномочий между:

- **platform-level** администрацией (создание и provisioning tenants);
- **tenant-level** администрацией (управление внутри конкретной организации).

Исключить смешение обязанностей между созданием организаций в системе и управлением структурой/отчётностью внутри конкретной организации.

---

## 2. Новая роль: platform_admin

### 2.1. Определение

| Свойство | Значение |
|----------|----------|
| Название | `platform_admin` |
| Scope | **Platform** (вся инсталляция) |
| Уровень | Выше любой tenant-scoped роли |
| Количество | 1-3 пользователя на инсталляцию |

### 2.2. Назначение

`platform_admin` отвечает за:

- создание новой организации (tenant) в системе;
- создание key organization / root entity;
- первичную инициализацию структуры tenant;
- назначение первого tenant admin;
- управление platform-level настройками;
- просмотр списка всех tenants;
- активацию / деактивацию / архивацию tenants;
- выполнение platform-level support / override операций;
- управление глобальными справочниками (стандарты, единицы измерения).

---

## 3. Обновлённая ролевая модель

### 3.1. Два уровня ролей

| Уровень | Роли | Scope |
|---------|------|-------|
| **Platform** | `platform_admin` | Вся платформа |
| **Tenant** | `admin`, `esg_manager`, `reviewer`, `collector`, `auditor` | Конкретная организация |

### 3.2. Ключевое различие

| | platform_admin | admin |
|-|:-:|:-:|
| **Работает над** | системой | организацией |
| **Создаёт tenants** | ✅ | ❌ |
| **Видит все организации** | ✅ | ❌ |
| **Scope** | platform | organization |
| **Назначает первого admin** | ✅ | ❌ |
| **Управляет company structure** | ⚠️ support/override | ✅ |
| **Создаёт projects** | ⚠️ обычно не нужно | ✅ |

### 3.3. Ограничение admin

Роль `admin` **tenant-scoped** и ограничена рамками одной организации:

- **не может** создавать новые tenants;
- **не может** видеть другие tenants;
- **не может** управлять platform-level сущностями;
- **не может** выполнять platform provisioning.

---

## 4. Scope-aware Role Binding (изменение модели данных)

### 4.1. Проблема текущей модели

**Было (плоская модель):**

```
users.role = 'admin' | 'esg_manager' | ...
```

Это не поддерживает:
- пользователя с разными ролями в разных организациях;
- platform-scoped роль;
- multi-tenant сценарий.

### 4.2. Новая модель: role_bindings

```sql
-- Пользователь — глобальный, без роли
create table users (
    id                  bigserial primary key,
    email               text not null unique,
    password_hash       text not null,
    full_name           text not null,
    is_active           boolean not null default true,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now()
);

-- Назначение роли с scope
create table role_bindings (
    id                  bigserial primary key,
    user_id             bigint not null references users(id) on delete cascade,
    role                text not null check (role in (
                            'platform_admin',
                            'admin', 'esg_manager', 'reviewer', 'collector', 'auditor'
                        )),
    scope_type          text not null check (scope_type in ('platform', 'organization')),
    scope_id            bigint,  -- NULL для platform scope, organization_id для tenant scope
    created_at          timestamptz not null default now(),
    created_by          bigint references users(id) on delete set null,

    -- Constraints
    constraint chk_scope_id_required
        check (
            (scope_type = 'platform' and scope_id is null) or
            (scope_type = 'organization' and scope_id is not null)
        ),
    constraint chk_platform_role
        check (
            (scope_type = 'platform' and role = 'platform_admin') or
            (scope_type = 'organization' and role != 'platform_admin')
        ),
    unique (user_id, role, scope_type, scope_id)
);

-- Foreign key для organization scope
alter table role_bindings
    add constraint fk_role_bindings_org
    foreign key (scope_id) references organizations(id) on delete cascade;

-- Indexes
create index idx_role_bindings_user on role_bindings(user_id);
create index idx_role_bindings_scope on role_bindings(scope_type, scope_id);
create index idx_role_bindings_role on role_bindings(role);
```

### 4.3. Примеры

Пользователь `ross@company.kz` может иметь:

| role_binding | role | scope_type | scope_id |
|-------------|------|------------|----------|
| 1 | `platform_admin` | `platform` | NULL |
| 2 | `admin` | `organization` | 101 |
| 3 | `auditor` | `organization` | 202 |

**Один пользователь — разные роли в разных организациях.**

### 4.4. Удаление поля users.role

```sql
-- После миграции на role_bindings
ALTER TABLE users DROP COLUMN role;

-- Убрать organization_id из users (теперь через role_bindings)
ALTER TABLE users DROP COLUMN organization_id;
```

### 4.5. Миграция JWT Claims

**Было:**

```python
class JWTPayload(BaseModel):
    sub: int
    email: str
    role: str                 # одна роль
    organization_id: int      # одна организация
```

**Стало:**

```python
class JWTPayload(BaseModel):
    sub: int                  # user.id
    email: str
    # role и organization_id больше НЕ в JWT
    # определяются на backend по role_bindings + X-Organization-Id header

class RequestContext(BaseModel):
    """Resolved per-request context."""
    user_id: int
    email: str
    organization_id: int | None     # из header X-Organization-Id
    role: str                       # resolved из role_bindings
    is_platform_admin: bool
```

**Resolving роли на каждый запрос:**

```python
# app/core/dependencies.py

async def get_current_context(
    token: str = Depends(oauth2_scheme),
    org_header: int | None = Header(None, alias="X-Organization-Id"),
    session: AsyncSession = Depends(get_session),
) -> RequestContext:
    """Resolve user context: role + organization from role_bindings."""
    payload = decode_jwt(token)
    user_id = payload.sub

    # Check platform_admin
    platform_binding = await session.execute(
        select(RoleBinding).where(
            RoleBinding.user_id == user_id,
            RoleBinding.scope_type == "platform",
            RoleBinding.role == "platform_admin",
        )
    )
    is_platform_admin = platform_binding.scalar_one_or_none() is not None

    # If platform admin accessing platform endpoints — no org needed
    if is_platform_admin and org_header is None:
        return RequestContext(
            user_id=user_id,
            email=payload.email,
            organization_id=None,
            role="platform_admin",
            is_platform_admin=True,
        )

    # For tenant endpoints — org header required
    if org_header is None:
        raise AppError("BAD_REQUEST", 400, "X-Organization-Id header required")

    # Resolve tenant role
    tenant_binding = await session.execute(
        select(RoleBinding).where(
            RoleBinding.user_id == user_id,
            RoleBinding.scope_type == "organization",
            RoleBinding.scope_id == org_header,
        )
    )
    binding = tenant_binding.scalar_one_or_none()

    if binding is None and not is_platform_admin:
        raise AppError("FORBIDDEN", 403, "No access to this organization")

    return RequestContext(
        user_id=user_id,
        email=payload.email,
        organization_id=org_header,
        role=binding.role if binding else "platform_admin",
        is_platform_admin=is_platform_admin,
    )
```

---

## 5. Обновлённый Onboarding Flow

### 5.1. Platform Provisioning Flow (platform_admin)

```
platform_admin → "Create Organization / Tenant"
    │
    ├── Step 1: Tenant info (name, country, industry)
    ├── Step 2: Key organization (root entity)
    ├── Step 3: Default boundary
    ├── Step 4: First admin (invite)
    └── Step 5: Confirm → tenant created
         │
         └── Tenant admin получает invite email
```

### 5.2. Tenant Setup Flow (admin)

```
admin → "Complete Company Setup"
    │
    ├── Достроить структуру группы
    ├── Создать ownership / control links
    ├── Настроить boundaries
    ├── Выбрать стандарты
    ├── Создать reporting project
    └── Добавить пользователей
```

### 5.3. Self-service Onboarding (если разрешено)

Для SaaS-сценария platform_admin может разрешить self-service registration:

```
Новый пользователь → Register
    │
    └── Система автоматически:
        ├── Создаёт tenant
        ├── Создаёт root entity
        ├── Назначает creator = admin
        └── Показывает Tenant Setup Wizard
```

**Конфигурация:**

```python
# app/core/config.py

class Settings(BaseSettings):
    allow_self_registration: bool = False    # Управляется platform_admin
    require_platform_provisioning: bool = True  # Default: только через platform_admin
```

---

## 6. Platform Admin экраны

### 6.1. Tenant List (`/platform/tenants`)

Доступен **только** `platform_admin`.

```
┌─────────────────────────────────────────────────────┐
│  Platform Admin: Organizations                       │
│                                                      │
│  [+ Create Organization]  [Search...]               │
│                                                      │
│  ┌────────────┬──────────┬────────┬────────┬──────┐ │
│  │ Name       │ Country  │ Users  │ Status │      │ │
│  ├────────────┼──────────┼────────┼────────┼──────┤ │
│  │ KazEnergy  │ KZ       │ 12     │ Active │ [⋯]  │ │
│  │ RusGas     │ RU       │ 8      │ Active │ [⋯]  │ │
│  │ TestOrg    │ US       │ 2      │ Susp.  │ [⋯]  │ │
│  └────────────┴──────────┴────────┴────────┴──────┘ │
│                                                      │
│  Total: 3 organizations                             │
└─────────────────────────────────────────────────────┘
```

### 6.2. Create Organization (`/platform/tenants/new`)

Wizard для platform_admin (расширенная версия TZ-OrgSetup):

| Шаг | Содержание |
|-----|-----------|
| 1 | Tenant info: name, country, industry, subscription tier |
| 2 | Key organization: root entity |
| 3 | Default boundary + reporting defaults |
| 4 | First admin: email + invite |
| 5 | Review & create |

### 6.3. Tenant Details (`/platform/tenants/:id`)

| Секция | Содержание |
|--------|-----------|
| Overview | Name, country, status, created date, subscription |
| Users | List of users + roles within tenant |
| Structure | Read-only view of company structure |
| Activity | Audit log filtered by tenant |
| Actions | Suspend / Reactivate / Archive |

---

## 7. API Endpoints (Platform Level)

```
# Platform tenant management (platform_admin only)
GET    /api/platform/tenants                    — список всех tenants
POST   /api/platform/tenants                    — создать tenant (provisioning)
GET    /api/platform/tenants/:id                — детали tenant
PATCH  /api/platform/tenants/:id                — обновить tenant (name, status)
POST   /api/platform/tenants/:id/suspend        — приостановить tenant
POST   /api/platform/tenants/:id/reactivate     — реактивировать tenant
POST   /api/platform/tenants/:id/archive        — архивировать tenant

# Platform user management
GET    /api/platform/users                      — все пользователи платформы
POST   /api/platform/tenants/:id/admins         — назначить admin для tenant

# Platform settings
GET    /api/platform/settings                   — глобальные настройки
PATCH  /api/platform/settings                   — обновить настройки

# Role bindings
GET    /api/users/:id/roles                     — все роли пользователя (по scope)
POST   /api/users/:id/roles                     — назначить роль
DELETE /api/users/:id/roles/:bindingId          — удалить роль
```

**Permission matrix:**

| Endpoint | platform_admin | admin | esg_manager | ... |
|----------|:-:|:-:|:-:|:-:|
| `GET /platform/tenants` | ✅ | ❌ | ❌ | ❌ |
| `POST /platform/tenants` | ✅ | ❌ | ❌ | ❌ |
| `PATCH /platform/tenants/:id` | ✅ | ❌ | ❌ | ❌ |
| `POST /platform/tenants/:id/suspend` | ✅ | ❌ | ❌ | ❌ |
| `GET /platform/users` | ✅ | ❌ | ❌ | ❌ |
| `GET /users/:id/roles` | ✅ | ⚠️ own org | ❌ | ❌ |
| `POST /users/:id/roles` | ✅ | ⚠️ tenant roles only | ❌ | ❌ |

---

## 8. Policies

### 8.1. Platform Policy

```python
# app/policies/platform_policy.py

class PlatformPolicy:
    """Access control for platform-level operations."""

    def require_platform_admin(self, ctx: RequestContext) -> None:
        if not ctx.is_platform_admin:
            raise AppError("FORBIDDEN", 403, "Platform admin access required")

    def can_manage_tenant(self, ctx: RequestContext, tenant_id: int) -> None:
        self.require_platform_admin(ctx)

    def can_assign_role(self, ctx: RequestContext, role: str, scope_type: str) -> None:
        """Check if current user can assign a specific role."""
        if scope_type == "platform":
            # Only platform_admin can assign platform roles
            self.require_platform_admin(ctx)
        elif scope_type == "organization":
            # platform_admin or tenant admin
            if not ctx.is_platform_admin and ctx.role != "admin":
                raise AppError("FORBIDDEN", 403, "Only admin can assign tenant roles")
            # admin cannot create platform_admin
            if role == "platform_admin":
                raise AppError("FORBIDDEN", 403, "Cannot assign platform_admin via tenant")
```

### 8.2. Tenant Isolation Policy (обновление)

```python
# app/policies/auth_policy.py (обновление)

def check_tenant_isolation(ctx: RequestContext, resource) -> bool:
    """Ensure user can only access resources in their organization."""
    # platform_admin can access any tenant (support mode)
    if ctx.is_platform_admin:
        return True
    # Regular users — strict isolation
    return ctx.organization_id == resource.organization_id
```

---

## 9. Изменения в существующих документах

### 9.1. ERROR-MODEL.md — обновление Permission Policy

Добавить в раздел 2.2:

```
platform_admin (level: ∞)
  Полный доступ на уровне платформы.
  Может:
  - создавать / управлять tenants
  - назначать tenant admins
  - выполнять support override
  - видеть все организации
```

Обновить JWT Claims (раздел 2.6) на новую модель с `X-Organization-Id` header.

### 9.2. ARCHITECTURE.md — обновление Security Architecture

Добавить в раздел 7.2:

```
RBAC model:
  Layer 1: Platform scope (platform_admin)
  Layer 2: Tenant scope (admin, esg_manager, reviewer, collector, auditor)
  Layer 3: Object-level checks (assignments, projects)
```

### 9.3. TZ-OrgSetup.md — разделение сценариев

- Сценарий A (platform provisioning): platform_admin создаёт tenant
- Сценарий B (tenant setup): admin достраивает структуру
- Self-service: если `allow_self_registration = true`

### 9.4. TZ-AIAssistance.md — AI Gate обновление

Tool Access Gate должен учитывать `platform_admin`:

- platform_admin получает доступ ко всем tools (support mode)
- Но AI ответы всё равно фильтруются по текущему tenant context

### 9.5. TZ-BackendArchitecture.md — dependencies обновление

`get_current_user` → `get_current_context` (возвращает `RequestContext` с resolved role + org).

---

## 10. Events

```python
@dataclass
class TenantCreated(DomainEvent):
    tenant_id: int = 0
    created_by: int = 0

@dataclass
class TenantSuspended(DomainEvent):
    tenant_id: int = 0
    suspended_by: int = 0
    reason: str = ""

@dataclass
class TenantReactivated(DomainEvent):
    tenant_id: int = 0
    reactivated_by: int = 0

@dataclass
class TenantArchived(DomainEvent):
    tenant_id: int = 0
    archived_by: int = 0

@dataclass
class RoleBindingCreated(DomainEvent):
    user_id: int = 0
    role: str = ""
    scope_type: str = ""
    scope_id: int | None = None
    assigned_by: int = 0

@dataclass
class RoleBindingRemoved(DomainEvent):
    user_id: int = 0
    role: str = ""
    scope_type: str = ""
    scope_id: int | None = None
    removed_by: int = 0
```

---

## 11. Error Codes

| Code | HTTP | Описание |
|------|------|----------|
| `PLATFORM_ADMIN_REQUIRED` | 403 | Требуется роль platform_admin |
| `TENANT_NOT_FOUND` | 404 | Tenant не найден |
| `TENANT_SUSPENDED` | 403 | Tenant приостановлен — доступ заблокирован |
| `TENANT_ARCHIVED` | 410 | Tenant архивирован — данные read-only |
| `CANNOT_ASSIGN_PLATFORM_ROLE` | 403 | Tenant admin не может назначить platform_admin |
| `ROLE_BINDING_EXISTS` | 409 | Такая role binding уже существует |
| `LAST_ADMIN_CANNOT_LEAVE` | 422 | Нельзя удалить единственного admin из tenant |
| `ORG_HEADER_REQUIRED` | 400 | Заголовок X-Organization-Id обязателен для tenant endpoints |

---

## 12. Audit & Security

### 12.1. Логирование platform_admin

**Все** действия platform_admin логируются:

| Действие | entity_type | Описание |
|----------|------------|----------|
| Create tenant | Tenant | Создание организации |
| Suspend tenant | Tenant | Приостановка с причиной |
| Reactivate tenant | Tenant | Реактивация |
| Archive tenant | Tenant | Архивация |
| Assign first admin | RoleBinding | Назначение admin |
| Support access | SupportSession | Вход в tenant для поддержки |

### 12.2. Support / Override Mode

Если platform_admin заходит в tenant для поддержки:

- Все действия помечаются `performed_by_platform_admin = true`;
- Tenant admin видит в audit log: «Action performed by platform support»;
- Override действия требуют обоснование (reason field).

---

## 13. Ограничения

- `admin` **не может** выполнять platform-level provisioning;
- `platform_admin` **не должен** использоваться как рабочая tenant-роль;
- Действия `platform_admin` логируются как platform-level события;
- Platform-level и tenant-level операции **разделены** в UI и API (`/api/platform/*` vs `/api/*`);
- Suspend tenant = блокировка логина для всех users tenant (кроме platform_admin);
- Archive tenant = данные переходят в read-only, вход заблокирован.

---

## 14. Критерии приёмки

- [ ] Новая организация может быть создана **только** platform_admin
- [ ] admin **не видит** другие tenants
- [ ] Ролевая модель поддерживает scope-aware назначение (role_bindings)
- [ ] Один пользователь может иметь разные роли в разных организациях
- [ ] JWT не содержит роль/организацию — resolve через role_bindings + header
- [ ] Platform admin экран (`/platform/tenants`) показывает все tenants
- [ ] Можно создать tenant, назначить admin, передать в управление
- [ ] Suspend/reactivate/archive tenant работает
- [ ] platform_admin действия логируются отдельно в audit log
- [ ] Self-service registration управляется настройкой `allow_self_registration`
- [ ] X-Organization-Id header обязателен для tenant endpoints
- [ ] Tenant isolation работает (role_bindings scope check)

---

## 15. Формулировка для основного ТЗ

> **Platform Administration**
>
> В системе должна существовать отдельная роль `platform_admin`, отвечающая за создание и инициализацию организаций (tenants) на уровне платформы. Роль `admin` ограничивается scope конкретной организации и не может выполнять platform-level provisioning. Ролевая модель должна поддерживать scope-aware назначения ролей через `role_bindings` (user + role + scope_type + scope_id).
