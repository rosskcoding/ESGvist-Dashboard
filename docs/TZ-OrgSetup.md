# ТЗ: Экран "Key Organization Setup"

**Модуль:** Onboarding / Organization Setup Wizard
**Версия:** 1.0
**Дата:** 2026-03-22
**Статус:** Согласован

---

## 1. Цель

Обеспечить создание и первичную настройку ключевой организации (root entity), которая является:

- владельцем всех данных в системе;
- верхним уровнем структуры группы;
- базой для boundary;
- основой для всех reporting projects.

---

## 2. Когда используется

| Сценарий | Условие |
|----------|---------|
| **Первый вход (onboarding)** | У пользователя нет организаций |
| **Через Admin** | Создание новой организации вручную |
| **Multi-tenant** | Пользователь управляет несколькими организациями |

---

## 3. Основная логика

**Архитектурное решение:**

> **Organization (tenant) ≠ Company Entity**

| Уровень | Назначение |
|---------|-----------|
| **Organization** | Tenancy / доступ / данные / subscription |
| **Company Entity** | Реальная структура группы (юрлица, филиалы, JV) |

В системе **всегда** есть root entity (ключевая организация):

```
Organization (tenant)
    ↓
Key Organization (root company_entity, entity_type = 'parent_company')
    ↓
Group structure (subsidiaries, JV, facilities, ...)
```

---

## 4. Основные поля

### 4.1. Базовая информация

| Поле | Тип | Обязательно | Описание |
|------|-----|:-----------:|----------|
| Organization name | text | ✅ | Название организации (отображается в UI) |
| Legal name | text | ❌ | Полное юридическое название |
| Registration number | text | ❌ | Регистрационный номер (ИИН/БИН/ОГРН) |
| Country | select | ✅ | Страна регистрации |
| Jurisdiction | text | ❌ | Юрисдикция |
| Industry / sector | select | ✅ | Отрасль (Oil & Gas, Mining, Finance, ...) |
| Currency (default) | select | ✅ | Валюта по умолчанию (auto: по стране) |

### 4.2. Reporting defaults

| Поле | Тип | Обязательно | Описание |
|------|-----|:-----------:|----------|
| Reporting standard | multi-select | ❌ | GRI / IFRS / ESRS (можно выбрать позже) |
| Default boundary | select | ✅ (auto) | `financial_reporting_default` по умолчанию |
| Reporting year | select | ✅ (auto) | Текущий год по умолчанию |

### 4.3. ESG параметры (опционально)

| Поле | Тип | Обязательно | Описание |
|------|-----|:-----------:|----------|
| Consolidation approach | select | ❌ | `financial_control` / `operational_control` / `equity_share` |
| Scope approach (GHG) | select | ❌ | `location-based` / `market-based` |

### 4.4. User setup

| Поле | Тип | Обязательно | Описание |
|------|-----|:-----------:|----------|
| Owner | auto | ✅ | Создатель = admin |
| Initial ESG manager | user select | ❌ | Можно назначить позже |
| Additional admins | user multi-select | ❌ | Приглашение по email |

---

## 5. UX сценарий (Wizard)

### 5.1. Шаг 1 — Organization Basics

```
┌─────────────────────────────────────────────┐
│  Step 1 of 5: Your Organization             │
│                                             │
│  Organization name *  [________________]    │
│  Country *            [▼ Kazakhstan    ]    │
│  Industry *           [▼ Oil & Gas     ]    │
│                                             │
│  ── Optional ──                             │
│  Legal name           [________________]    │
│  Registration number  [________________]    │
│                                             │
│              [Back]  [Next →]               │
│                                             │
│  💡 AI: "Выбор отрасли влияет на то,       │
│      какие ESG-метрики будут предложены"    │
└─────────────────────────────────────────────┘
```

**Smart defaults:**

- Currency = auto по стране (KZT для Kazakhstan, RUB для Russia, USD для US, ...)
- Reporting year = текущий год

### 5.2. Шаг 2 — Reporting Setup

```
┌─────────────────────────────────────────────┐
│  Step 2 of 5: Reporting Setup               │
│                                             │
│  Which standards will you report against?   │
│                                             │
│  ☑ GRI 2021                                │
│  ☐ IFRS S2 2023                            │
│  ☐ ESRS E1                                 │
│  ☐ SASB (sector-specific)                  │
│                                             │
│  Default boundary                           │
│  ● Financial Reporting (recommended)        │
│  ○ Operational Control                      │
│  ○ Equity Share                             │
│                                             │
│  Reporting year    [▼ 2025    ]             │
│                                             │
│              [← Back]  [Next →]             │
│                                             │
│  💡 AI: "Большинство компаний начинают     │
│      с GRI. IFRS S2 можно добавить позже"  │
└─────────────────────────────────────────────┘
```

**Правила:**

- Стандарты можно не выбирать сейчас (добавить позже в Project Setup);
- Boundary = `financial_reporting_default` предвыбран;
- «Skip this step» допускается.

### 5.3. Шаг 3 — Company Structure (минимальный старт)

```
┌─────────────────────────────────────────────┐
│  Step 3 of 5: Company Structure             │
│                                             │
│  Your organization:                         │
│                                             │
│  🏢 KazEnergy Group (parent company)       │
│                                             │
│  Add subsidiaries? (optional)               │
│                                             │
│  [+ Add subsidiary]  [+ Add JV]             │
│                                             │
│  Added:                                     │
│  ├── KazEnergy Production (100%)           │
│  └── KazEnergy Trading (100%)              │
│                                             │
│  ☐ I'll set up the structure later          │
│                                             │
│              [← Back]  [Next →]             │
│                                             │
│  💡 AI: "Добавить дочерние компании можно  │
│      позже в Company Structure & Boundary"  │
└─────────────────────────────────────────────┘
```

**Правила:**

- Root entity создаётся **автоматически** из данных шага 1;
- Добавление subsidiaries **опционально**;
- «I'll set up later» — пропуск шага;
- Каждая добавленная subsidiary = `company_entity` с `parent_entity_id` = root.

### 5.4. Шаг 4 — Users

```
┌─────────────────────────────────────────────┐
│  Step 4 of 5: Team Setup                    │
│                                             │
│  You (ross@company.kz) will be Admin.       │
│                                             │
│  Invite ESG Manager (optional):             │
│  [  email@company.kz                    ]   │
│  [+ Invite another user]                    │
│                                             │
│  ☐ I'll invite users later                  │
│                                             │
│              [← Back]  [Next →]             │
│                                             │
│  💡 AI: "ESG Manager управляет проектами   │
│      и назначает сборщиков данных"          │
└─────────────────────────────────────────────┘
```

### 5.5. Шаг 5 — Review & Confirm

```
┌─────────────────────────────────────────────┐
│  Step 5 of 5: Review & Create               │
│                                             │
│  Organization:  KazEnergy Group             │
│  Country:       Kazakhstan                  │
│  Industry:      Oil & Gas                   │
│  Currency:      KZT                         │
│                                             │
│  Standards:     GRI 2021                    │
│  Boundary:      Financial Reporting Default │
│  Year:          2025                        │
│                                             │
│  Structure:                                 │
│  🏢 KazEnergy Group                        │
│  ├── KazEnergy Production (100%)           │
│  └── KazEnergy Trading (100%)              │
│                                             │
│  Users:                                     │
│  👤 ross@company.kz (Admin)                │
│  👤 esg@company.kz (ESG Manager, invited)  │
│                                             │
│         [← Back]  [Create Organization]     │
└─────────────────────────────────────────────┘
```

---

## 6. Результат создания

При нажатии «Create Organization» система **автоматически** выполняет:

### 6.1. Создание сущностей

| Сущность | Таблица | Описание |
|----------|---------|----------|
| Organization (tenant) | `organizations` | Корневая запись тенанта |
| Root company entity | `company_entities` | `entity_type = 'parent_company'`, `status = 'active'` |
| Child entities (если добавлены) | `company_entities` | `parent_entity_id` → root entity |
| Ownership links (если есть children) | `ownership_links` | 100% ownership по умолчанию |
| Default boundary | `boundary_definitions` | `financial_reporting_default`, `is_default = true` |
| Boundary memberships | `boundary_memberships` | Root + children включены, `inclusion_source = 'automatic'` |

### 6.2. Создание настроек

| Настройка | Значение |
|-----------|----------|
| Default currency | По стране (auto) |
| Default reporting year | Текущий / выбранный |
| Default consolidation | `financial_control` |
| Default standards | Выбранные на шаге 2 (или пустой набор) |

### 6.3. Создание ролей

| Пользователь | Роль |
|-------------|------|
| Создатель | `admin` |
| Приглашённый ESG manager | `esg_manager` (invite pending) |
| Дополнительные admins | `admin` (invite pending) |

### 6.4. Инициализация системы

- Пустая структура group → готова к редактированию в Company Structure;
- Default boundary создан → готов к использованию;
- Если выбраны стандарты → seed data загружается (GRI sections, disclosures, requirement items);
- Dashboard показывает onboarding state: «Create your first ESG report».

---

## 7. Backend: API и workflow

### 7.1. API Endpoint

```
POST /api/organizations/setup
```

**Request:**

```json
{
  "name": "KazEnergy Group",
  "legal_name": "TOO KazEnergy Group",
  "registration_number": "123456789",
  "country": "KZ",
  "jurisdiction": "Kazakhstan",
  "industry": "oil_gas",
  "currency": "KZT",
  "reporting_year": 2025,
  "standards": ["GRI_2021"],
  "boundary_type": "financial_reporting_default",
  "consolidation_approach": "financial_control",
  "ghg_scope_approach": "location_based",
  "subsidiaries": [
    {
      "name": "KazEnergy Production",
      "entity_type": "legal_entity",
      "country": "KZ",
      "ownership_percent": 100
    },
    {
      "name": "KazEnergy Trading",
      "entity_type": "legal_entity",
      "country": "KZ",
      "ownership_percent": 100
    }
  ],
  "invite_users": [
    {
      "email": "esg@company.kz",
      "role": "esg_manager"
    }
  ]
}
```

**Response:**

```json
{
  "organization_id": 1,
  "root_entity_id": 1,
  "boundary_id": 1,
  "created_entities": 3,
  "invited_users": 1,
  "next_step": "/dashboard"
}
```

### 7.2. Setup Workflow

```python
# app/workflows/org_setup_workflow.py

class OrganizationSetupWorkflow:
    """
    Multi-step workflow: create organization from scratch.

    Steps:
    1. Create organization (tenant)
    2. Create root company entity
    3. Create child entities (if any)
    4. Create ownership links
    5. Create default boundary
    6. Calculate boundary memberships
    7. Create user roles
    8. Send invitations
    9. Load seed data (if standards selected)
    10. Emit events
    """

    async def execute(self, payload: OrgSetupPayload, creator_user) -> OrgSetupResult:
        # Step 1: Create organization
        org = await self.org_repo.create(
            name=payload.name,
            legal_name=payload.legal_name,
            registration_number=payload.registration_number,
            country=payload.country,
            jurisdiction=payload.jurisdiction,
            industry=payload.industry,
            default_currency=payload.currency,
        )

        # Step 2: Create root entity
        root_entity = await self.entity_repo.create(
            organization_id=org.id,
            name=payload.name,
            entity_type="parent_company",
            country=payload.country,
            jurisdiction=payload.jurisdiction,
            status="active",
        )

        # Step 3: Create child entities
        child_entities = []
        for sub in payload.subsidiaries:
            child = await self.entity_repo.create(
                organization_id=org.id,
                parent_entity_id=root_entity.id,
                name=sub.name,
                entity_type=sub.entity_type,
                country=sub.country,
                status="active",
            )
            child_entities.append(child)

            # Step 4: Ownership links
            await self.ownership_repo.create(
                parent_entity_id=root_entity.id,
                child_entity_id=child.id,
                ownership_percent=sub.ownership_percent,
                ownership_type="direct",
            )

        # Step 5: Default boundary
        boundary = await self.boundary_repo.create(
            organization_id=org.id,
            name="Financial Reporting Default",
            boundary_type="financial_reporting_default",
            is_default=True,
            inclusion_rules={
                "rules": [
                    {"type": "include_if_financially_controlled", "consolidation": "full"}
                ],
                "defaultExclude": True,
            },
        )

        # Step 6: Boundary memberships (root + all children)
        all_entities = [root_entity] + child_entities
        for entity in all_entities:
            await self.boundary_repo.create_membership(
                boundary_definition_id=boundary.id,
                entity_id=entity.id,
                included=True,
                inclusion_source="automatic",
                consolidation_method="full",
            )

        # Step 7: User roles
        await self.user_repo.assign_role(creator_user.id, org.id, "admin")

        # Step 8: Invitations
        for invite in payload.invite_users:
            await self.invitation_service.send(
                email=invite.email,
                role=invite.role,
                organization_id=org.id,
                invited_by=creator_user.id,
            )

        # Step 9: Seed data
        if payload.standards:
            for standard_code in payload.standards:
                await self.seed_service.load_standard(standard_code, org.id)

        # Step 10: Events
        await self.event_bus.publish(OrganizationCreated(
            organization_id=org.id,
            root_entity_id=root_entity.id,
        ))

        return OrgSetupResult(
            organization_id=org.id,
            root_entity_id=root_entity.id,
            boundary_id=boundary.id,
            created_entities=len(all_entities),
            invited_users=len(payload.invite_users),
        )
```

### 7.3. Permissions

| Endpoint | Кто может |
|----------|----------|
| `POST /api/organizations/setup` | Любой аутентифицированный пользователь без организации (onboarding) |
| `POST /api/organizations/setup` (admin) | Admin текущей организации (создание дополнительной) |

---

## 8. Модель данных

### 8.1. Расширение organizations

```sql
ALTER TABLE organizations
    ADD COLUMN legal_name           text,
    ADD COLUMN registration_number  text,
    ADD COLUMN country              text,
    ADD COLUMN jurisdiction         text,
    ADD COLUMN industry             text,
    ADD COLUMN default_currency     text NOT NULL DEFAULT 'USD',
    ADD COLUMN default_reporting_year integer,
    ADD COLUMN consolidation_approach text CHECK (consolidation_approach IN (
        'financial_control', 'operational_control', 'equity_share'
    )),
    ADD COLUMN ghg_scope_approach   text CHECK (ghg_scope_approach IN (
        'location_based', 'market_based'
    )),
    ADD COLUMN setup_completed      boolean NOT NULL DEFAULT false;
```

### 8.2. User invitations

```sql
create table user_invitations (
    id                  bigserial primary key,
    organization_id     bigint not null references organizations(id) on delete cascade,
    email               text not null,
    role                text not null,
    invited_by          bigint not null references users(id) on delete cascade,
    status              text not null default 'pending' check (status in ('pending', 'accepted', 'expired')),
    token               text not null unique,
    expires_at          timestamptz not null,
    created_at          timestamptz not null default now()
);

create index idx_invitations_org on user_invitations(organization_id);
create index idx_invitations_token on user_invitations(token);
create index idx_invitations_email on user_invitations(email);
```

---

## 9. Интеграция с другими модулями

### 9.1. Company Structure (TZ-CompanyStructure.md)

- Root entity становится вершиной дерева;
- Root entity **нельзя удалить** (`CANNOT_DELETE_ROOT_ENTITY`, 422);
- Root entity можно редактировать;
- Subsidiaries, добавленные при setup, видны в Company Structure сразу.

### 9.2. Boundary (TZ-CompanyStructure.md, TZ-BoundaryIntegration.md)

- `financial_reporting_default` создаётся автоматически;
- Root entity **всегда** включена в boundary;
- Все child entities включены с `consolidation_method = 'full'`.

### 9.3. Projects

- После setup Dashboard показывает CTA: **«Create your first ESG report»**;
- Первый project предзаполняет: org, boundary, standards из setup.

### 9.4. AI Assistant (TZ-AIAssistance.md)

AI помогает **внутри wizard**:

| Шаг | AI подсказка |
|-----|-------------|
| Step 1 | «Выбор отрасли влияет на рекомендуемые ESG-метрики» |
| Step 2 | «Большинство компаний начинают с GRI. IFRS S2 можно добавить позже» |
| Step 2 | «Financial boundary — стандартный выбор. Operational control нужен, если вы управляете JV» |
| Step 3 | «Добавить дочерние компании можно позже в Company Structure» |
| Step 3 | «Нужно ли добавлять JV сейчас?» → context-aware ответ |
| Step 4 | «ESG Manager управляет проектами и назначает сборщиков данных» |

---

## 10. Events

```python
@dataclass
class OrganizationCreated(DomainEvent):
    organization_id: int = 0
    root_entity_id: int = 0

@dataclass
class UserInvited(DomainEvent):
    invitation_id: int = 0
    email: str = ""
    role: str = ""
    organization_id: int = 0

@dataclass
class SetupCompleted(DomainEvent):
    organization_id: int = 0
    standards_loaded: list[str] = field(default_factory=list)
    entities_created: int = 0
```

---

## 11. Error Codes

| Code | HTTP | Описание |
|------|------|----------|
| `ORG_ALREADY_EXISTS` | 409 | Организация с таким именем уже существует |
| `CANNOT_DELETE_ROOT_ENTITY` | 422 | Нельзя удалить root entity |
| `SETUP_ALREADY_COMPLETED` | 409 | Setup уже завершён для этой организации |
| `INVALID_INVITATION_TOKEN` | 400 | Токен приглашения невалиден или истёк |
| `INVITATION_EXPIRED` | 410 | Приглашение истекло |

---

## 12. UX принципы

### 12.1. Не перегружать

Это onboarding, не SAP.

- Обязательные поля — **минимум** (name, country, industry);
- Остальное — optional или «set up later»;
- Каждый шаг — 3-5 полей максимум.

### 12.2. Smart defaults

| Поле | Smart default |
|------|--------------|
| Currency | По стране (KZ → KZT, RU → RUB, US → USD) |
| Boundary | `financial_reporting_default` |
| Reporting year | Текущий год |
| Consolidation | `financial_control` |
| GHG approach | `location_based` |
| Ownership % | 100% для новых subsidiaries |

### 12.3. Возможность «пропустить»

- «Skip» на шагах 2, 3, 4;
- «I'll set up later» checkbox;
- Минимальный путь: Step 1 → Step 5 (только name + country + industry).

### 12.4. Post-setup guidance

После создания Dashboard показывает:

```
Welcome to ESGvist!

Your organization "KazEnergy Group" is ready.

Next steps:
  1. 📋 Create your first ESG report    [Create project →]
  2. 🏢 Set up company structure         [Open structure →]
  3. 👥 Invite team members              [Invite users →]
```

---

## 13. Ограничения

- Нельзя создать проект без организации;
- Нельзя удалить root entity;
- Должен существовать хотя бы один boundary (`DEFAULT_BOUNDARY_REQUIRED`);
- Должен быть хотя бы один admin;
- Setup workflow — **транзакционный** (если любой шаг fails → rollback всего);
- Invitation token expires через 7 дней.

---

## 14. Критерии приёмки

- [ ] Пользователь может создать организацию с нуля через wizard (5 шагов)
- [ ] Создаётся root company entity (`entity_type = 'parent_company'`)
- [ ] Создаётся default boundary (`financial_reporting_default`)
- [ ] Root entity автоматически включена в boundary
- [ ] Child entities (если добавлены) автоматически включены в boundary с 100% ownership
- [ ] Роли назначаются корректно (creator = admin)
- [ ] Приглашения отправляются по email
- [ ] Smart defaults работают (currency по стране, year текущий)
- [ ] Можно пропустить шаги 2, 3, 4 (минимальный путь)
- [ ] После setup Dashboard показывает post-setup guidance
- [ ] Нельзя удалить root entity
- [ ] AI подсказки работают внутри wizard
- [ ] Setup workflow транзакционный (rollback при ошибке)
- [ ] Если стандарты выбраны → seed data загружается автоматически
