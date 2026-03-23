# ТЗ: AI Assistance & Explainability Layer

**Модуль:** AI Assistant / Contextual Copilot
**Версия:** 1.0
**Дата:** 2026-03-22
**Статус:** Согласован

---

## 1. Цель

Обеспечить встроенный интеллектуальный слой помощи пользователю (AI Assistance Layer), направленный на:

- объяснение терминов, показателей и требований ESG-стандартов;
- интерпретацию системных решений (boundary, completeness, validation);
- снижение когнитивной нагрузки при работе с системой;
- ускорение прохождения сценариев (data entry, review, reporting);
- повышение качества вводимых данных.

AI слой должен выступать как **explainability и guidance инструмент**, а не как источник бизнес-логики.

---

## 2. Область применения

Модуль применяется во всех ключевых пользовательских контурах:

| Экран | Применение AI |
|-------|--------------|
| **Data Collection / Wizard** | Объяснение полей, guidance по заполнению, примеры |
| **Merge View** | Объяснение пересечений, delta-требований |
| **Review / Validation** | Summary data point, anomaly detection, draft комментариев |
| **Company Structure & Boundary** | Объяснение boundary decisions, inclusion/exclusion |
| **Completeness / Dashboard** | Объяснение статусов, блокеров, next steps |
| **Evidence Management** | Guidance по типу evidence, требованиям к качеству |
| **Project Setup** | Объяснение настроек, стандартов, boundary выбора |

---

## 3. Основные принципы

### 3.1. AI не является источником истины

Все решения (boundary, completeness, validation) принимаются **системой**.

**AI НЕ может:**

- изменять данные;
- принимать решения;
- выполнять workflow.

**AI МОЖЕТ:**

- объяснять;
- интерпретировать;
- подсказывать следующий шаг;
- генерировать draft текстов (комментарии, narrative).

### 3.2. Context-aware ответы

AI всегда работает в контексте:

- текущего экрана;
- текущего проекта;
- выбранного boundary;
- роли пользователя;
- конкретного объекта (data point, requirement, entity).

**Без контекста AI не отвечает.** Если контекст недостаточен — AI запрашивает уточнение у пользователя.

### 3.3. Role-based ограничение

AI **не раскрывает** данные, недоступные роли пользователя:

| Роль | Ограничение AI |
|------|---------------|
| Collector | Видит только свои assignments и data points |
| Reviewer | Видит только assigned review scope |
| ESG Manager | Видит все данные проекта |
| Auditor | Read-only, AI не предлагает actions |
| Admin | Полный контекст |

### 3.4. Structured grounding

AI **не должен «догадываться»** — он должен использовать:

- данные из backend (через tools/function calls);
- заранее определённые функции;
- структурированный контекст.

**Запрещено:** генерация цифр, статусов, boundary decisions без обращения к реальным данным.

### 3.5. Inline-first UX

Основной способ взаимодействия — **inline explainers**, а не чат.

Чат (Copilot panel) — вторичный, для сложных вопросов.

---

## 4. Основные функции

### 4.1. Field Explanation

Пользователь может запросить для любого поля:

| Вопрос | Источник данных |
|--------|----------------|
| Что означает это поле? | `requirement_items.description` + стандарт |
| Почему оно требуется? | `requirement_items.is_required` + `mandatory_level` |
| Как его заполнить? | `requirement_items.item_type` + `value_type` + `unit_code` |
| Пример значения | Предзагруженные примеры + контекст отрасли |
| Откуда взять данные? | `requirement_items.description` + guidance text |

**UX:** кнопка `?` рядом с полем → inline tooltip или expand panel.

**Пример ответа:**

```
Scope 1 GHG Emissions (GRI 305-1)

Что: Прямые выбросы парниковых газов из источников,
     принадлежащих или контролируемых организацией.

Единица: тонны CO2-эквивалента (tCO2e)

Включает: стационарное сжигание, мобильные источники,
          технологические выбросы, утечки хладагентов.

Breakdown: обязателен по типам газов (CO2, CH4, N2O, HFCs, PFCs, SF6).

Источник данных: данные от производственных подразделений,
               расчёт по GHG Protocol methodology.
```

### 4.2. Requirement Explanation

Для requirement / disclosure:

| Вопрос | Ответ AI |
|--------|---------|
| Что требует стандарт? | Описание disclosure + контекст стандарта |
| Какие данные нужны? | Список requirement_items с типами |
| Какие breakdown обязательны? | `granularity_rule` → человекочитаемый текст |
| Связь с другими требованиями? | `requirement_item_dependencies` → граф |
| Какие стандарты требуют то же? | `requirement_item_shared_elements` → reuse info |

**Tool call:** `get_requirement_details(requirement_item_id)`

### 4.3. Boundary Explanation

Для entity / boundary:

| Вопрос | Ответ AI |
|--------|---------|
| Входит ли entity в boundary? | `boundary_memberships.included` |
| Почему включена / исключена? | `inclusion_reason` + `inclusion_source` |
| По какому правилу? | `boundary_definitions.inclusion_rules` → текст |
| Метод консолидации? | `consolidation_method` + объяснение |
| Что изменится при другом boundary? | `boundary/preview` → diff |

**Tool call:** `get_boundary_decision(entity_id, boundary_id)`

**Пример ответа:**

```
Entity: JV Alpha

Статус: Включена в boundary "Operational Control"

Причина: Operational control = true (установлено вручную).
         Хотя ownership = 50%, JV Alpha управляется операционно.

Метод консолидации: Full (100% данных включаются в отчёт).

Примечание: в boundary "Financial Reporting Default" эта entity
           включается proportionally (50%).
```

### 4.4. Completeness Explanation

Для disclosure / проекта:

| Вопрос | Ответ AI |
|--------|---------|
| Что не заполнено? | Список missing requirement_items |
| Почему incomplete? | Конкретные причины (no data / not approved / no evidence) |
| Какие блокеры? | boundary exclusion, missing evidence, pending review |
| Какие шаги нужны? | Ordered action list с responsible |

**Tool call:** `get_completeness_details(project_id, disclosure_id)`

**Пример ответа:**

```
Disclosure GRI 305-1: Partial (67%)

Что заполнено:
  ✅ Scope 1 total — approved
  ✅ Methodology description — approved
  ✅ Base year — approved

Что не заполнено:
  ❌ Breakdown by gas type — данные не введены
     → Ответственный: Иванов А.Б., дедлайн: 2026-04-15
  ❌ Biogenic CO2 emissions — данные в статусе draft
     → Необходимо: submit на review

Блокеры:
  ⚠ Evidence required для "Audit certificate" — не загружен

Следующие шаги:
  1. Иванов: заполнить breakdown by gas type
  2. Петрова: submit biogenic CO2 draft
  3. Загрузить audit certificate (evidence)
```

### 4.5. Review Assistant

Для reviewer:

| Функция | Описание |
|---------|----------|
| **Summary** | Краткое описание data point (значение, изменение YoY, entity, evidence) |
| **Anomaly detection** | Отклонение от прошлого периода, cross-reference inconsistencies |
| **Missing evidence alert** | Если requires_evidence = true и evidence нет |
| **Draft comment** | Предложение текста комментария для reject / needs_revision |
| **Reuse impact** | В скольких стандартах/disclosures используется этот DataPoint |

**Tool calls:**
- `get_data_point_details(data_point_id)`
- `get_review_context(data_point_id)` — prev year, evidence, reuse count
- `get_anomaly_flags(data_point_id)` — outlier checks

**Пример draft комментария:**

```
Draft: "Значение Scope 1 (1240 tCO2e) снизилось на 10.1%
по сравнению с прошлым периодом (1380 tCO2e).
Пожалуйста, подтвердите корректность и приложите
обоснование снижения."

[Использовать]  [Редактировать]  [Отклонить]
```

### 4.6. Evidence Guidance

Для collector:

| Вопрос | Ответ AI |
|--------|---------|
| Какой тип evidence ожидается? | На основе `requirement_items.item_type` + `requires_evidence` |
| Примеры документов | Предзагруженный каталог типовых evidence |
| Требования к качеству | Формат, актуальность, подпись, язык |
| Достаточно ли загруженного? | Проверка количества и типа привязанных evidence |

**Пример ответа:**

```
Для GRI 305-1 требуется evidence:

Обязательно:
  📄 Отчёт об инвентаризации выбросов (PDF/Excel)
     — содержит расчёт Scope 1 по источникам

Рекомендовано:
  📊 Расчётная таблица (Excel)
     — breakdown по газам и источникам
  🔗 Ссылка на методологию
     — если используется нестандартный подход

Требования к файлам:
  — Формат: PDF, XLSX, DOCX (макс. 10 MB)
  — Актуальность: за отчётный период
  — Язык: RU или EN
```

### 4.7. Contextual Q&A

Пользователь может задать произвольный вопрос:

- в рамках текущего экрана;
- с учётом текущего контекста.

**Примеры вопросов:**

| Вопрос | Контекст | Ответ |
|--------|----------|-------|
| «Почему Plant G не в отчёте?» | Boundary View | Boundary decision для entity |
| «Что ещё нужно для GRI 305?» | Data Collection | Completeness details |
| «Чем отличается Scope 1 от Scope 2?» | Wizard | Определения из стандарта |
| «Кто отвечает за water data?» | Dashboard | Assignment lookup |
| «Можно ли использовать данные прошлого года?» | Data Entry | Reuse / methodology guidance |

---

## 5. UX компоненты

### 5.1. Inline Explain Button (`?`)

Рядом с:

- полями ввода;
- статусами (missing / partial / complete);
- warning badges;
- boundary badges;
- validation ошибками.

**Поведение:** клик → inline tooltip с объяснением (1-3 предложения). Ссылка «Подробнее» → Copilot panel.

### 5.2. "Why?" Links

Кликабельные ссылки для:

- boundary decisions: `Why included?` / `Why excluded?`
- completeness статусов: `Why partial?`
- validation ошибок: `Why required?`
- reuse индикаторов: `Why reused?`

**Поведение:** клик → structured explanation (reasons + next actions).

### 5.3. AI Side Panel (Copilot)

Контекстный помощник:

- открывается справа (slide-over panel);
- получает контекст текущего экрана автоматически;
- позволяет задавать вопросы;
- показывает streaming ответы;
- сохраняет историю в рамках сессии.

**Layout:**

```
┌─────────────────────────────────┬──────────────────┐
│                                 │  AI Copilot      │
│       Main Content              │                  │
│                                 │  Context: GRI    │
│                                 │  305-1, Plant A  │
│                                 │                  │
│                                 │  Q: Why partial? │
│                                 │                  │
│                                 │  A: Missing      │
│                                 │  breakdown by    │
│                                 │  gas type...     │
│                                 │                  │
│                                 │  [Ask question]  │
└─────────────────────────────────┴──────────────────┘
```

### 5.4. Suggested Actions

AI может предлагать действия (но **не выполнять** их):

| Suggestion | Действие пользователя |
|------------|----------------------|
| «Добавить evidence» | Кнопка → открывает upload dialog |
| «Заполнить breakdown» | Кнопка → переход к полю |
| «Проверить entity scope» | Кнопка → переход в Boundary Manager |
| «Submit на review» | Кнопка → открывает confirm dialog |
| «Назначить ответственного» | Кнопка → переход в Assignment Matrix |

**Правило:** suggestion — это навигация или открытие UI, **не автоматическое действие**.

---

## 6. Архитектура

### 6.1. Общая схема

```
┌──────────────────┐
│    Frontend       │
│  (Copilot Panel,  │
│   Inline Buttons) │
└────────┬─────────┘
         │ POST /api/ai/ask
         │ POST /api/ai/explain
┌────────▼─────────┐
│  AI Assistant     │
│  Service          │
│  (app/services/   │
│   ai_service.py)  │
└────────┬─────────┘
         │
    ┌────┼──────────────────┐
    │    │                  │
┌───▼──┐ ▼              ┌──▼───────────┐
│Tools │ Domain          │ LLM API      │
│(func │ Services        │ (Claude /    │
│calls)│ (read-only)     │  OpenAI)     │
└──────┘                 └──────────────┘
```

### 6.2. AI Assistant Service

```python
# app/services/ai_service.py

class AIAssistantService:
    """
    Orchestrates AI assistance:
    1. Collects context from domain services
    2. Builds structured prompt
    3. Calls LLM with tools
    4. Processes response
    5. Logs interaction
    """

    def __init__(
        self,
        llm_client: LLMClient,
        requirement_repo: RequirementItemRepository,
        completeness_service: CompletenessService,
        boundary_service: BoundaryService,
        data_point_repo: DataPointRepository,
        evidence_repo: EvidenceRepository,
        assignment_repo: AssignmentRepository,
        audit_service: AuditService,
    ):
        self.llm_client = llm_client
        self.requirement_repo = requirement_repo
        self.completeness_service = completeness_service
        self.boundary_service = boundary_service
        self.data_point_repo = data_point_repo
        self.evidence_repo = evidence_repo
        self.assignment_repo = assignment_repo
        self.audit_service = audit_service

    async def explain_field(
        self, requirement_item_id: int, user, project_id: int
    ) -> AIResponse:
        """Explain a field to the user."""
        # 1. Collect context
        item = await self.requirement_repo.get_with_standard(requirement_item_id)
        shared_element = await self.requirement_repo.get_shared_element(requirement_item_id)

        context = FieldContext(
            item=item,
            shared_element=shared_element,
            standard_name=item.disclosure.standard.name,
            user_role=user.role,
        )

        # 2. Call LLM with structured context
        response = await self.llm_client.explain(
            prompt_type="field_explanation",
            context=context.to_dict(),
        )

        # 3. Log interaction
        await self._log_interaction(user, "explain_field", context, response)

        return response

    async def explain_completeness(
        self, project_id: int, disclosure_id: int, user
    ) -> AIResponse:
        """Explain why a disclosure is incomplete."""
        # 1. Get completeness details from domain service
        details = await self.completeness_service.get_detailed_status(
            project_id, disclosure_id
        )
        assignments = await self.assignment_repo.get_by_disclosure(
            project_id, disclosure_id
        )

        context = CompletenessContext(
            disclosure=details.disclosure,
            items=details.items,
            missing_items=details.missing_items,
            blockers=details.blockers,
            assignments=assignments,
            user_role=user.role,
        )

        # 2. Call LLM
        response = await self.llm_client.explain(
            prompt_type="completeness_explanation",
            context=context.to_dict(),
        )

        # 3. Log
        await self._log_interaction(user, "explain_completeness", context, response)

        return response

    async def ask(
        self, question: str, screen_context: ScreenContext, user
    ) -> AIResponse:
        """Handle free-form question with context."""
        # 1. Build context from screen
        context = await self._build_context(screen_context, user)

        # 2. Call LLM with tools
        response = await self.llm_client.ask(
            question=question,
            context=context,
            tools=self._get_tools_for_role(user.role),
        )

        # 3. Log
        await self._log_interaction(user, "ask", {"question": question}, response)

        return response

    async def review_assist(
        self, data_point_id: int, user
    ) -> ReviewAssistResponse:
        """Generate review assistance for a data point."""
        # 1. Collect full review context
        dp = await self.data_point_repo.get_with_details(data_point_id)
        prev_year = await self.data_point_repo.get_previous_period(data_point_id)
        evidence = await self.evidence_repo.list_for_data_point(data_point_id)
        reuse_count = await self.data_point_repo.get_reuse_count(data_point_id)
        anomalies = await self._detect_anomalies(dp, prev_year)

        context = ReviewContext(
            data_point=dp,
            previous_value=prev_year,
            evidence=evidence,
            reuse_count=reuse_count,
            anomalies=anomalies,
            user_role=user.role,
        )

        # 2. Call LLM
        response = await self.llm_client.review_assist(context=context.to_dict())

        # 3. Log
        await self._log_interaction(user, "review_assist", context, response)

        return response

    def _get_tools_for_role(self, role: str) -> list[Tool]:
        """Return available tools based on user role."""
        base_tools = [
            Tool("get_requirement_details", get_requirement_details),
            Tool("get_standard_info", get_standard_info),
        ]

        if role in ("esg_manager", "admin"):
            base_tools.extend([
                Tool("get_boundary_decision", get_boundary_decision),
                Tool("get_project_completeness", get_project_completeness),
                Tool("get_assignment_info", get_assignment_info),
            ])

        if role in ("reviewer", "esg_manager", "admin"):
            base_tools.extend([
                Tool("get_data_point_details", get_data_point_details),
                Tool("get_anomaly_flags", get_anomaly_flags),
                Tool("get_evidence_status", get_evidence_status),
            ])

        return base_tools

    async def _log_interaction(self, user, action, context, response):
        """Log AI interaction for audit."""
        await self.audit_service.log(
            entity_type="AIInteraction",
            action=action,
            user_id=user.id,
            details={
                "role": user.role,
                "context_summary": str(context)[:500],
                "response_summary": str(response)[:500],
            },
        )
```

### 6.3. Tools / Function Calls

AI использует строго определённые функции для получения данных:

```python
# app/services/ai_tools.py

TOOL_DEFINITIONS = [
    {
        "name": "get_requirement_details",
        "description": "Get details about a requirement item including standard, type, rules",
        "parameters": {
            "requirement_item_id": {"type": "integer"},
        },
    },
    {
        "name": "get_boundary_decision",
        "description": "Get boundary inclusion decision for an entity",
        "parameters": {
            "entity_id": {"type": "integer"},
            "boundary_id": {"type": "integer"},
        },
    },
    {
        "name": "get_project_completeness",
        "description": "Get completeness status for a project or disclosure",
        "parameters": {
            "project_id": {"type": "integer"},
            "disclosure_id": {"type": "integer", "optional": True},
        },
    },
    {
        "name": "get_data_point_details",
        "description": "Get data point value, history, evidence, reuse info",
        "parameters": {
            "data_point_id": {"type": "integer"},
        },
    },
    {
        "name": "get_evidence_requirements",
        "description": "Get evidence requirements for a requirement item",
        "parameters": {
            "requirement_item_id": {"type": "integer"},
        },
    },
    {
        "name": "get_anomaly_flags",
        "description": "Get anomaly flags for a data point (YoY deviation, cross-checks)",
        "parameters": {
            "data_point_id": {"type": "integer"},
        },
    },
    {
        "name": "get_assignment_info",
        "description": "Get assignment details (collector, reviewer, deadline, status)",
        "parameters": {
            "project_id": {"type": "integer"},
            "shared_element_id": {"type": "integer", "optional": True},
        },
    },
    {
        "name": "get_standard_info",
        "description": "Get standard description, sections, requirements overview",
        "parameters": {
            "standard_id": {"type": "integer"},
        },
    },
]
```

**Правило:** AI вызывает tools → получает структурированный ответ → формирует объяснение. AI **никогда** не выдумывает данные.

### 6.4. Structured Output

Ответ AI возвращается в структурированном виде:

```python
# app/schemas/ai.py

class AIResponse(BaseModel):
    """Structured AI response."""
    text: str                              # Основной текст объяснения
    reasons: list[str] | None = None       # Список причин (для "Why?" ответов)
    next_actions: list[SuggestedAction] | None = None  # Предлагаемые действия
    references: list[Reference] | None = None  # Ссылки на стандарты / документы
    confidence: str | None = None          # 'high' | 'medium' | 'low'


class SuggestedAction(BaseModel):
    label: str                             # "Добавить evidence"
    action_type: str                       # 'navigate' | 'open_dialog' | 'highlight'
    target: str                            # URL path или element ID
    description: str | None = None


class Reference(BaseModel):
    title: str                             # "GRI 305-1, paragraph a"
    source: str                            # "GRI Standards 2021"
    url: str | None = None


class ReviewAssistResponse(BaseModel):
    summary: str                           # Краткое описание data point
    anomalies: list[str]                   # Обнаруженные аномалии
    missing_evidence: list[str]            # Недостающие evidence
    draft_comment: str | None = None       # Предложение комментария
    reuse_impact: str | None = None        # Влияние на другие стандарты
```

### 6.5. LLM Client

```python
# app/infrastructure/llm_client.py

class LLMClient:
    """Abstraction over LLM API (Claude / OpenAI)."""

    def __init__(self, config: AIConfig):
        self.config = config
        self.client = anthropic.AsyncAnthropic(api_key=config.api_key)

    async def explain(
        self, prompt_type: str, context: dict
    ) -> AIResponse:
        """Generate explanation using structured prompt."""
        system_prompt = self._get_system_prompt(prompt_type)

        response = await self.client.messages.create(
            model=self.config.model,
            max_tokens=1024,
            system=system_prompt,
            messages=[
                {"role": "user", "content": self._format_context(context)}
            ],
        )

        return self._parse_response(response)

    async def ask(
        self, question: str, context: dict, tools: list[Tool]
    ) -> AIResponse:
        """Handle free-form question with tools."""
        response = await self.client.messages.create(
            model=self.config.model,
            max_tokens=2048,
            system=self._get_system_prompt("contextual_qa"),
            messages=[
                {"role": "user", "content": f"Context: {context}\n\nQuestion: {question}"}
            ],
            tools=[t.to_anthropic_format() for t in tools],
        )

        # Handle tool calls
        if response.stop_reason == "tool_use":
            response = await self._handle_tool_calls(response, tools)

        return self._parse_response(response)

    async def ask_stream(
        self, question: str, context: dict, tools: list[Tool]
    ):
        """Streaming version for Copilot panel."""
        async with self.client.messages.stream(
            model=self.config.model,
            max_tokens=2048,
            system=self._get_system_prompt("contextual_qa"),
            messages=[
                {"role": "user", "content": f"Context: {context}\n\nQuestion: {question}"}
            ],
        ) as stream:
            async for text in stream.text_stream:
                yield text
```

---

## 7. API Endpoints

### 7.1. Explain

```
POST /api/ai/explain/field
```

**Request:**

```json
{
  "requirement_item_id": 42,
  "project_id": 1
}
```

**Response:** `AIResponse`

### 7.2. Explain Completeness

```
POST /api/ai/explain/completeness
```

**Request:**

```json
{
  "project_id": 1,
  "disclosure_id": 15
}
```

### 7.3. Explain Boundary

```
POST /api/ai/explain/boundary
```

**Request:**

```json
{
  "entity_id": 10,
  "boundary_id": 1,
  "project_id": 1
}
```

### 7.4. Review Assist

```
POST /api/ai/review-assist
```

**Request:**

```json
{
  "data_point_id": 123
}
```

**Response:** `ReviewAssistResponse`

### 7.5. Contextual Q&A

```
POST /api/ai/ask
```

**Request:**

```json
{
  "question": "Почему Plant G не в отчёте?",
  "screen": "boundary_view",
  "context": {
    "project_id": 1,
    "boundary_id": 1,
    "entity_id": 15
  }
}
```

### 7.6. Streaming Q&A

```
POST /api/ai/ask/stream
```

**Response:** Server-Sent Events (SSE) stream.

### 7.7. Evidence Guidance

```
POST /api/ai/explain/evidence
```

**Request:**

```json
{
  "requirement_item_id": 42
}
```

---

## 8. Ролевое поведение

| Роль | Возможности AI | Ограничения |
|------|---------------|-------------|
| **Collector** | Explain fields, guidance по заполнению, evidence guidance | Только свои assignments, нет analytical insights |
| **Reviewer** | Explain + review assistant (summary, anomalies, draft comments) | Только assigned review scope |
| **ESG Manager** | Explain + analytical insights + completeness analysis + boundary explanation | Все данные проекта |
| **Auditor** | Explain read-only (объяснения без suggested actions) | Read-only, нет draft комментариев |
| **Admin** | Explain system logic + все функции | Полный доступ |

---

## 9. Prompt Templates

### 9.1. System Prompts

```python
# app/services/ai_prompts.py

SYSTEM_PROMPTS = {
    "field_explanation": """
You are an ESG reporting assistant. Your role is to explain ESG metrics,
requirements, and fields to users.

Rules:
- Use the provided context (requirement item, standard, shared element)
- Be concise and practical
- Give concrete examples relevant to the user's industry
- Explain in the user's language (RU or EN based on context)
- Never invent data or numbers
- Reference the specific standard (e.g., "GRI 305-1 requires...")
""",

    "completeness_explanation": """
You are an ESG completeness assistant. Your role is to explain why
a disclosure or project is incomplete and what steps are needed.

Rules:
- Use the provided completeness data (items, statuses, assignments)
- List specific missing items with responsible persons
- Identify blockers (boundary, evidence, review)
- Suggest concrete next steps in priority order
- Never suggest actions the user's role cannot perform
""",

    "review_assist": """
You are an ESG review assistant helping reviewers check data quality.

Rules:
- Summarize the data point (value, unit, entity, period)
- Flag anomalies (YoY deviation, cross-check failures)
- Note missing evidence if required
- Draft a review comment if anomalies found
- Note reuse impact (how many standards affected)
- Be objective — flag issues but don't make approval decisions
""",

    "contextual_qa": """
You are an ESG reporting assistant embedded in the ESGvist platform.
Answer questions using the provided context and tools.

Rules:
- Use tools to fetch real data before answering
- Never guess numbers, statuses, or decisions
- If you don't have enough context, say so
- Respect the user's role — don't reveal data they can't access
- Be concise — this is an inline assistant, not a report generator
""",
}
```

---

## 10. AI Control & Safety Layer (Gate)

AI Gate — это **не один check**, а набор контролей, через которые проходит каждый AI-запрос:

```
User → AI API
  → 1. Rate / Abuse Gate
  → 2. Context Gate (filtering)
  → 3. Permission Gate (role + object)
  → 4. Tool Access Gate
  → 5. Prompt Gate (construction + sanitization)
  → LLM API
  → 6. Output Gate (validation + filtering)
  → 7. Action Gate (suggestion validation)
  → 8. Audit Gate (logging)
  → User
```

**Без Gate Layer AI превращается в дырку в системе.** С ним — в безопасный explainability engine.

---

### 10.1. Context Gate (самый важный)

**Перед** вызовом AI система **обязана** отфильтровать данные.

AI получает **только:**

- данные текущего проекта (`project_id`);
- данные текущей организации (`organization_id`);
- объекты, доступные роли пользователя;
- текущий экран и выбранный объект.

AI **никогда не видит:**

- чужие проекты;
- чужие организации;
- скрытые / internal-only поля;
- данные за пределами assignment scope (для collector/reviewer);
- raw SQL / internal IDs (только бизнес-идентификаторы).

```python
# app/policies/ai_gate.py

class ContextGate:
    """Filters context before it reaches AI."""

    async def filter(self, raw_context: dict, user) -> dict:
        """Remove everything the user's role cannot access."""
        ctx = dict(raw_context)

        # Tenant isolation (always)
        assert ctx.get("organization_id") == user.organization_id

        # Role-based filtering
        if user.role == "collector":
            ctx.pop("all_assignments", None)
            ctx.pop("boundary_rules", None)
            ctx.pop("other_users_data", None)
            # Keep only own assignments
            if "assignments" in ctx:
                ctx["assignments"] = [
                    a for a in ctx["assignments"]
                    if a["collector_id"] == user.id
                ]

        if user.role == "reviewer":
            # Keep only assigned review scope
            if "data_points" in ctx:
                ctx["data_points"] = [
                    dp for dp in ctx["data_points"]
                    if dp["reviewer_id"] == user.id
                ]

        if user.role == "auditor":
            ctx.pop("suggested_actions", None)
            ctx.pop("draft_comments", None)

        # Always remove sensitive fields
        for key in ("password_hash", "api_keys", "internal_notes", "raw_sql"):
            ctx.pop(key, None)

        # Limit context size (prevent token overflow)
        return self._truncate(ctx, max_tokens=4000)

    def _truncate(self, ctx: dict, max_tokens: int) -> dict:
        """Truncate context to fit within token budget."""
        import json
        serialized = json.dumps(ctx, default=str)
        if len(serialized) > max_tokens * 4:  # rough char-to-token ratio
            # Keep most important fields, drop details
            ctx.pop("full_history", None)
            ctx.pop("all_comments", None)
        return ctx
```

---

### 10.2. Permission Gate

Проверяет, **имеет ли пользователь право** вызвать конкретный AI endpoint.

```python
class PermissionGate:
    """Checks if user can use this AI function."""

    ENDPOINT_PERMISSIONS: dict[str, list[str]] = {
        "explain_field":       ["collector", "reviewer", "esg_manager", "auditor", "admin"],
        "explain_completeness": ["collector", "reviewer", "esg_manager", "auditor", "admin"],
        "explain_boundary":    ["esg_manager", "auditor", "admin"],
        "review_assist":       ["reviewer", "esg_manager", "admin"],
        "ask":                 ["collector", "reviewer", "esg_manager", "auditor", "admin"],
        "evidence_guidance":   ["collector", "esg_manager", "admin"],
    }

    def check(self, action: str, user) -> None:
        allowed_roles = self.ENDPOINT_PERMISSIONS.get(action, [])
        if user.role not in allowed_roles:
            raise AppError("FORBIDDEN", 403, f"AI {action} not available for role {user.role}")
```

---

### 10.3. Tool Access Gate

AI использует tools (function calls) для получения данных. **Не все tools доступны всем ролям.**

| Tool | collector | reviewer | esg_manager | auditor | admin |
|------|:---------:|:--------:|:-----------:|:-------:|:-----:|
| `get_requirement_details` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `get_standard_info` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `get_evidence_requirements` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `get_data_point_details` | ⚠️ own | ⚠️ assigned | ✅ | ✅ RO | ✅ |
| `get_anomaly_flags` | ❌ | ✅ | ✅ | ❌ | ✅ |
| `get_boundary_decision` | ❌ | ✅ RO | ✅ | ✅ RO | ✅ |
| `get_project_completeness` | ⚠️ own scope | ✅ | ✅ | ✅ | ✅ |
| `get_assignment_info` | ⚠️ own | ❌ | ✅ | ✅ RO | ✅ |

```python
class ToolAccessGate:
    """Controls which tools AI can use based on user role."""

    BLOCKED_TOOLS: dict[str, set[str]] = {
        "collector": {"get_boundary_decision", "get_assignment_info", "get_anomaly_flags"},
        "auditor":   {"get_anomaly_flags"},
        "reviewer":  {"get_assignment_info"},
    }

    OBJECT_LEVEL_TOOLS: set[str] = {
        "get_data_point_details",
        "get_project_completeness",
        "get_assignment_info",
    }

    def filter_tools(self, tools: list[Tool], user) -> list[Tool]:
        """Remove tools the user's role cannot access."""
        blocked = self.BLOCKED_TOOLS.get(user.role, set())
        return [t for t in tools if t.name not in blocked]

    async def validate_tool_call(self, tool_name: str, params: dict, user) -> None:
        """Validate a specific tool call before execution."""
        blocked = self.BLOCKED_TOOLS.get(user.role, set())
        if tool_name in blocked:
            raise AppError("FORBIDDEN", 403, f"Tool '{tool_name}' not available for role {user.role}")

        # Object-level checks for sensitive tools
        if tool_name in self.OBJECT_LEVEL_TOOLS:
            await self._check_object_access(tool_name, params, user)

    async def _check_object_access(self, tool_name: str, params: dict, user) -> None:
        """Check if user has access to the specific object."""
        if tool_name == "get_data_point_details" and user.role == "collector":
            dp = await self.dp_repo.get_by_id(params["data_point_id"])
            assignment = await self.assignment_repo.get_for_data_point(dp.id)
            if assignment.collector_id != user.id:
                raise AppError("FORBIDDEN", 403, "Access denied to this data point")
```

---

### 10.4. Prompt Gate

Backend **формирует prompt** — frontend **никогда** не отправляет raw prompt.

**Правила:**

| Правило | Описание |
|---------|----------|
| No raw user prompt to LLM | Frontend отправляет `question` + `screen_context`, backend строит prompt |
| System prompt immutable | System prompt задаётся backend, user input не может его переопределить |
| Context normalization | Данные нормализуются: убираются internal IDs, raw SQL, timestamps приводятся к human-readable |
| Input sanitization | User question проходит sanitization: strip HTML, limit length (500 chars), escape special chars |
| Token budget | Контекст ограничен бюджетом (~4000 tokens), чтобы не превышать window и не раскрывать лишнее |

```python
class PromptGate:
    """Controls prompt construction — prevents injection and data leaks."""

    MAX_QUESTION_LENGTH = 500
    MAX_CONTEXT_TOKENS = 4000

    def sanitize_question(self, question: str) -> str:
        """Clean user input before including in prompt."""
        import re
        # Strip HTML tags
        question = re.sub(r"<[^>]+>", "", question)
        # Limit length
        question = question[:self.MAX_QUESTION_LENGTH]
        # Remove attempts to override system prompt
        injection_patterns = [
            r"ignore previous instructions",
            r"you are now",
            r"system:",
            r"<\|im_start\|>",
            r"```system",
        ]
        for pattern in injection_patterns:
            question = re.sub(pattern, "[filtered]", question, flags=re.IGNORECASE)
        return question.strip()

    def build_prompt(
        self, prompt_type: str, context: dict, question: str | None = None
    ) -> list[dict]:
        """Build structured prompt — only backend controls this."""
        system = SYSTEM_PROMPTS[prompt_type]
        user_content = f"Context:\n{self._format_context(context)}"
        if question:
            user_content += f"\n\nUser question: {question}"

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ]

    def _format_context(self, context: dict) -> str:
        """Format context for prompt — remove sensitive fields, normalize."""
        safe_context = {k: v for k, v in context.items() if k not in SENSITIVE_FIELDS}
        return json.dumps(safe_context, indent=2, default=str, ensure_ascii=False)


SENSITIVE_FIELDS = {
    "password_hash", "api_key", "refresh_token", "internal_id",
    "raw_sql", "connection_string", "secret",
}
```

---

### 10.5. Output Gate (критичный)

**После** ответа AI — перед отправкой пользователю — обязательная проверка.

| Проверка | Описание | Действие при нарушении |
|----------|----------|----------------------|
| Структура ответа | Response соответствует `AIResponse` schema | Fallback → generic explanation |
| Hallucination markers | AI упоминает несуществующие стандарты, entity, статусы | Fallback → «unable to verify» |
| Data leak detection | Ответ содержит email, token, password, internal ID | Strip sensitive data |
| Forbidden actions | AI предлагает выполнить запрещённое действие (approve, delete, etc.) | Remove action from response |
| Role boundary | Ответ содержит данные за пределами роли пользователя | Filter out |
| Confidence check | AI не уверен (low confidence) | Добавить disclaimer |

```python
class OutputGate:
    """Validates and filters AI response before sending to user."""

    SENSITIVE_PATTERNS = [
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # email
        r"\b(password|secret|token|api_key)\s*[:=]\s*\S+",           # credentials
        r"\b(SELECT|INSERT|UPDATE|DELETE)\s+.+FROM\b",               # SQL
    ]

    FORBIDDEN_ACTION_KEYWORDS = [
        "approve this data point",
        "reject this submission",
        "delete this entity",
        "change the boundary",
        "modify the assignment",
        "publish the report",
    ]

    async def validate(self, response: AIResponse, user, context: dict) -> AIResponse:
        """Validate and clean AI response."""
        # 1. Check structure
        if not response or not response.text:
            return self._fallback_response("AI response was empty.")

        # 2. Filter sensitive data from text
        response.text = self._strip_sensitive(response.text)

        # 3. Remove forbidden action suggestions
        if response.next_actions:
            response.next_actions = [
                a for a in response.next_actions
                if not self._is_forbidden_action(a, user)
            ]

        # 4. Validate references exist
        if response.references:
            response.references = await self._validate_references(response.references)

        # 5. Add disclaimer if low confidence
        if response.confidence == "low":
            response.text += "\n\n⚠️ Этот ответ может быть неточным. Проверьте данные в системе."

        return response

    def _strip_sensitive(self, text: str) -> str:
        import re
        for pattern in self.SENSITIVE_PATTERNS:
            text = re.sub(pattern, "[redacted]", text)
        return text

    def _is_forbidden_action(self, action: SuggestedAction, user) -> bool:
        """Check if suggested action is forbidden for this role."""
        label_lower = action.label.lower()
        # Auditors get no actions at all
        if user.role == "auditor":
            return True
        # Check forbidden keywords
        return any(kw in label_lower for kw in self.FORBIDDEN_ACTION_KEYWORDS)

    def _fallback_response(self, reason: str) -> AIResponse:
        return AIResponse(
            text="Не удалось сформировать объяснение. Попробуйте уточнить вопрос или обратитесь к документации.",
            confidence="low",
        )
```

---

### 10.6. Action Gate

AI может **предложить** действия, но **не выполнять** их.

**Правила:**

| Правило | Описание |
|---------|----------|
| AI → suggestion only | AI возвращает `SuggestedAction` с `action_type: navigate \| open_dialog \| highlight` |
| Frontend validates | Frontend проверяет, что пользователь **имеет право** на это действие через policy |
| No auto-execute | Кнопка suggestion **открывает UI**, не выполняет действие напрямую |
| No side effects | AI endpoint **не делает** POST/PUT/DELETE к domain services |
| Confirm required | Любое действие, предложенное AI, требует **явного подтверждения** пользователя |

```python
class ActionGate:
    """Validates suggested actions before sending to frontend."""

    # Actions that AI can suggest per role
    ALLOWED_SUGGESTIONS: dict[str, set[str]] = {
        "collector":   {"navigate_to_field", "open_upload_dialog", "highlight_missing"},
        "reviewer":    {"navigate_to_field", "use_draft_comment", "highlight_anomaly"},
        "esg_manager": {"navigate_to_field", "open_assignment", "open_boundary_preview", "navigate_to_entity"},
        "auditor":     set(),  # no actions for auditor
        "admin":       {"navigate_to_field", "open_assignment", "open_boundary_preview", "navigate_to_entity", "open_settings"},
    }

    def filter_actions(self, actions: list[SuggestedAction], user) -> list[SuggestedAction]:
        allowed = self.ALLOWED_SUGGESTIONS.get(user.role, set())
        return [a for a in actions if a.action_type in allowed]
```

---

### 10.7. Rate / Abuse Gate

| Роль | Лимит запросов AI | Burst limit |
|------|-------------------|-------------|
| Collector | 30 req/hour | 5 req/min |
| Reviewer | 50 req/hour | 8 req/min |
| ESG Manager | 100 req/hour | 15 req/min |
| Admin | 200 req/hour | 20 req/min |
| Auditor | 30 req/hour | 5 req/min |

**Abuse detection:**

| Pattern | Действие |
|---------|----------|
| > 10 identical questions in 1h | Block + alert admin |
| Systematic entity enumeration | Block + alert admin |
| Prompt injection attempts (detected by Prompt Gate) | Log + block user for 1h |
| Token budget exceeded per org | Throttle to 10 req/hour |

```python
class RateGate:
    """Rate limiting and abuse detection for AI endpoints."""

    LIMITS: dict[str, dict] = {
        "collector":   {"per_hour": 30,  "per_minute": 5},
        "reviewer":    {"per_hour": 50,  "per_minute": 8},
        "esg_manager": {"per_hour": 100, "per_minute": 15},
        "admin":       {"per_hour": 200, "per_minute": 20},
        "auditor":     {"per_hour": 30,  "per_minute": 5},
    }

    async def check(self, user) -> None:
        limits = self.LIMITS.get(user.role, {"per_hour": 10, "per_minute": 2})

        # Check per-minute burst
        recent_count = await self.redis.get(f"ai:rate:{user.id}:minute")
        if recent_count and int(recent_count) >= limits["per_minute"]:
            raise AppError("RATE_LIMITED", 429, "AI request limit exceeded. Try again in a minute.")

        # Check per-hour
        hourly_count = await self.redis.get(f"ai:rate:{user.id}:hour")
        if hourly_count and int(hourly_count) >= limits["per_hour"]:
            raise AppError("RATE_LIMITED", 429, "AI hourly limit exceeded.")

        # Increment counters
        pipe = self.redis.pipeline()
        pipe.incr(f"ai:rate:{user.id}:minute")
        pipe.expire(f"ai:rate:{user.id}:minute", 60)
        pipe.incr(f"ai:rate:{user.id}:hour")
        pipe.expire(f"ai:rate:{user.id}:hour", 3600)
        await pipe.execute()
```

---

### 10.8. Audit Gate

Каждый AI вызов **обязательно** логируется — без исключений.

См. раздел 11 (Логирование и аудит) — таблица `ai_interactions`.

Дополнительные audit поля для Gate:

| Поле | Описание |
|------|----------|
| `gate_blocked` | `true` если Gate заблокировал запрос |
| `gate_reason` | Причина блокировки (role, rate, injection, etc.) |
| `tools_blocked` | Список tools, заблокированных Tool Access Gate |
| `output_filtered` | `true` если Output Gate модифицировал ответ |
| `output_filter_reason` | Что было отфильтровано |

```sql
ALTER TABLE ai_interactions
    ADD COLUMN gate_blocked         boolean NOT NULL DEFAULT false,
    ADD COLUMN gate_reason          text,
    ADD COLUMN tools_blocked        text[],
    ADD COLUMN output_filtered      boolean NOT NULL DEFAULT false,
    ADD COLUMN output_filter_reason text;
```

---

### 10.9. Полная цепочка Gate в коде

```python
# app/services/ai_service.py — orchestration через gate chain

class AIAssistantService:

    async def ask(self, question: str, screen_context: ScreenContext, user) -> AIResponse:
        """Full gate chain for every AI request."""

        # Gate 1: Rate / Abuse
        await self.rate_gate.check(user)

        # Gate 2: Permission
        self.permission_gate.check("ask", user)

        # Gate 3: Context filtering
        raw_context = await self._build_raw_context(screen_context, user)
        safe_context = await self.context_gate.filter(raw_context, user)

        # Gate 4: Tool access filtering
        all_tools = self._get_all_tools()
        allowed_tools = self.tool_gate.filter_tools(all_tools, user)

        # Gate 5: Prompt construction + sanitization
        clean_question = self.prompt_gate.sanitize_question(question)
        messages = self.prompt_gate.build_prompt("contextual_qa", safe_context, clean_question)

        # LLM call
        raw_response = await self.llm_client.call(messages, tools=allowed_tools)

        # Gate 6: Output validation
        response = self.output_gate.validate(raw_response, user, safe_context)

        # Gate 7: Action filtering
        if response.next_actions:
            response.next_actions = self.action_gate.filter_actions(response.next_actions, user)

        # Gate 8: Audit logging
        await self.audit_gate.log(user, "ask", safe_context, clean_question, response)

        return response
```

---

### 10.10. Критерии приёмки Gate Layer

- [ ] AI не видит чужие проекты / организации (Context Gate)
- [ ] Collector не получает boundary/assignment data через AI (Tool Access Gate)
- [ ] Auditor не получает suggested actions (Action Gate)
- [ ] Frontend не отправляет raw prompt — только question + context (Prompt Gate)
- [ ] Prompt injection попытки обнаруживаются и блокируются (Prompt Gate)
- [ ] Ответ AI не содержит email, tokens, SQL, passwords (Output Gate)
- [ ] AI не предлагает approve/reject/delete/publish (Output Gate + Action Gate)
- [ ] Rate limiting работает по ролям (Rate Gate)
- [ ] Abuse detection блокирует enumeration и flooding (Rate Gate)
- [ ] Все AI вызовы логируются, включая blocked (Audit Gate)
- [ ] Gate blocked events видны admin в audit log

---

## 11. Логирование и аудит

### 11.1. Таблица ai_interactions

```sql
create table ai_interactions (
    id                  bigserial primary key,
    user_id             bigint not null references users(id) on delete cascade,
    organization_id     bigint not null references organizations(id) on delete cascade,
    role                text not null,
    screen              text not null,
    action              text not null,         -- 'explain_field', 'ask', 'review_assist'
    context_summary     text,                  -- краткое описание контекста (до 500 символов)
    question            text,                  -- вопрос пользователя (для Q&A)
    response_summary    text,                  -- краткое описание ответа (до 500 символов)
    tools_used          text[],                -- список вызванных tools
    model               text,                  -- 'claude-sonnet-4-6', etc.
    tokens_input        integer,
    tokens_output       integer,
    latency_ms          integer,
    created_at          timestamptz not null default now()
);

create index idx_ai_interactions_user on ai_interactions(user_id);
create index idx_ai_interactions_org on ai_interactions(organization_id);
create index idx_ai_interactions_created on ai_interactions(created_at);
```

### 11.2. Что логируется

| Поле | Описание |
|------|----------|
| user_id | Кто запросил |
| role | Роль пользователя |
| screen | Экран (data_collection, merge_view, review, ...) |
| action | Тип действия (explain_field, ask, review_assist) |
| context_summary | Краткий контекст (не полный prompt — для экономии) |
| question | Вопрос пользователя (для Q&A) |
| response_summary | Краткий ответ (не полный — для экономии) |
| tools_used | Какие tools были вызваны |
| model / tokens / latency | Технические метрики |

---

## 12. Производительность

| Требование | Значение |
|-----------|----------|
| Inline explain (поле) | < 2 секунды |
| Completeness explanation | < 4 секунды |
| Review assist | < 5 секунд |
| Contextual Q&A | < 6 секунд |
| Streaming первый chunk | < 500ms |
| Timeout | 15 секунд (hard limit) |
| Fallback при недоступности AI | Показать «AI temporarily unavailable» + static help text |

### 12.1. Caching

- Field explanations кэшируются по `requirement_item_id` (TTL 24h) — не меняются часто;
- Completeness explanations **не кэшируются** — зависят от текущего состояния;
- Standard info кэшируется (TTL 7d).

### 12.2. Streaming

```python
# app/api/routes/ai.py

@router.post("/api/ai/ask/stream")
async def ask_stream(
    payload: AIAskRequest,
    user=Depends(get_current_user),
    service: AIAssistantService = Depends(get_ai_service),
):
    async def event_generator():
        async for chunk in service.ask_stream(
            question=payload.question,
            screen_context=payload.context,
            user=user,
        ):
            yield f"data: {json.dumps({'text': chunk})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )
```

---

## 13. Frontend интеграция

### 13.1. React hooks

```typescript
// frontend/lib/hooks/useAIExplain.ts

export function useAIExplain() {
  const mutation = useMutation({
    mutationFn: (params: { type: string; id: number; projectId?: number }) =>
      api.post(`/api/ai/explain/${params.type}`, params),
  })

  return {
    explain: mutation.mutate,
    data: mutation.data as AIResponse | undefined,
    isLoading: mutation.isPending,
    error: mutation.error,
  }
}

// frontend/lib/hooks/useAICopilot.ts

export function useAICopilot(screenContext: ScreenContext) {
  const [messages, setMessages] = useState<Message[]>([])

  const ask = async (question: string) => {
    // SSE streaming
    const eventSource = new EventSource(
      `/api/ai/ask/stream?question=${encodeURIComponent(question)}&context=${JSON.stringify(screenContext)}`
    )
    // ... handle stream
  }

  return { messages, ask, isStreaming }
}
```

### 13.2. Компоненты

| Компонент | Описание |
|-----------|----------|
| `<ExplainButton />` | Кнопка `?` с tooltip |
| `<WhyLink />` | Кликабельная ссылка «Why?» |
| `<CopilotPanel />` | Side panel с чатом |
| `<SuggestedActions />` | Список предлагаемых действий |
| `<AIBadge />` | Индикатор AI-generated контента |

---

## 14. Ограничения

AI **не может:**

- изменять данные;
- выполнять submit / approve / reject;
- менять boundary;
- изменять assignments;
- генерировать официальные отчёты без подтверждения пользователя;
- создавать или удалять entities;
- отправлять уведомления;
- раскрывать данные за пределами роли пользователя.

AI **не заменяет:**

- бизнес-логику системы;
- policies;
- workflow;
- validation rules.

---

## 15. Phasing

| Фаза | Функциональность |
|------|-----------------|
| **Phase 1 (MVP)** | Inline field explanation (static + LLM), «Why?» links для completeness |
| **Phase 2** | Copilot panel, contextual Q&A, review assistant |
| **Phase 3** | Evidence guidance, boundary explanation, suggested actions, streaming |

---

## 16. Критерии приёмки

Система считается принятой, если:

- [ ] Пользователь может получить объяснение для любого поля (inline explain)
- [ ] Boundary decisions объяснимы через AI («Why included / excluded?»)
- [ ] Completeness объясняется в человекочитаемом виде (конкретные missing items + next steps)
- [ ] Reviewer получает summary + anomaly flags + draft comment
- [ ] AI не нарушает роль и доступ (collector не видит чужие assignments через AI)
- [ ] AI не выполняет действия вместо пользователя (только suggestions)
- [ ] Ответы основаны на реальном контексте системы (через tools, не hallucination)
- [ ] Streaming работает в Copilot panel (первый chunk < 500ms)
- [ ] Все AI interactions логируются в `ai_interactions`
- [ ] Fallback работает при недоступности AI (static help text)
- [ ] Rate limiting по ролям соблюдается
