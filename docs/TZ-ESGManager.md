# ТЗ: ESG-менеджер

**Модуль:** управление процессом и отчетностью
**Версия:** 1.0
**Статус:** На согласовании

---

## 1. Цель

Обеспечить управление процессом ESG-отчетности:

- выбор стандартов для проекта;
- назначение задач и ответственных;
- контроль прогресса сбора данных;
- анализ покрытия (coverage) по стандартам;
- управление workflow проекта;
- публикация отчета.

---

## 2. Область применения

Используется для:

- управления проектом отчетности от начала до публикации;
- координации сборщиков и ревьюеров;
- мониторинга дедлайнов и проблемных зон;
- финальной сборки и экспорта отчета.

---

## 3. Функциональные требования

### 3.1. Управление проектом отчётности

ESG-менеджер должен иметь возможность:

- создавать проект отчётности;
- выбирать период (`reporting_periods`);
- выбирать стандарты (`reporting_project_standards`);
- определять базовый стандарт (`is_base_standard`);
- задавать дедлайн;
- переводить проект между статусами.

**Workflow проекта:**

```
draft → in_progress → review → published
```

| Из | В | Условия |
|----|---|---------|
| `draft` | `in_progress` | Стандарты выбраны, ответственные назначены |
| `in_progress` | `review` | Completeness > порогового значения (настраивается) |
| `review` | `published` | Все mandatory disclosures = complete |
| `published` | `in_progress` | Откат (с обоснованием, audit_log) |

**Связь с БД:** `reporting_projects`, `reporting_project_standards`, `reporting_periods`

**UI:** `/dashboard` (overview) + `/settings/periods`

### 3.2. Назначение задач

ESG-менеджер должен иметь возможность:

- **назначать requirement items пользователям** через:
  - карточку метрики (индивидуальное назначение);
  - **матрицу назначений** (массовое назначение);
- задавать для каждого назначения:
  - сборщика (`collector_id`);
  - ревьюера (`reviewer_id`);
  - дедлайн;
- оставлять метрики **без назначения** (для назначения позже);
- **распределять по бизнес-юнитам** (если есть дочерние entities);
- контролировать нагрузку:
  - видеть, сколько метрик назначено каждому пользователю;
  - видеть сроки и статусы по пользователям.

**Constraint:** `collector_id != reviewer_id` для одной метрики.

**Связь с БД:** `metric_assignments`

**UI:** `/settings/assignments` — матрица (строки: shared_elements, колонки: collector, reviewer, deadline, status)

### 3.3. Мониторинг прогресса

Система должна показывать ESG-менеджеру:

**Dashboard (overview):**
- Общий прогресс проекта (% completion);
- Прогресс-бар с % inside;
- Breakdown по статусам: missing / partial / complete;
- Количество issues и overdue;

**Completion по разрезам:**

| Разрез | Пример |
|--------|--------|
| По стандарту | GRI: 72%, IFRS: 45% |
| По разделу / теме | Emissions: 80%, Water: 100%, Governance: 50% |
| По пользователю | Иванов: 5/8, Петрова: 3/5 |
| По статусу | 12 approved, 3 in_review, 6 missing |

**Heatmap покрытия:**
- Визуализация coverage в формате матрицы;
- Цветовое кодирование: 🔴 missing → 🟡 partial → 🟢 complete.

**Связь с БД:** `requirement_item_statuses`, `disclosure_requirement_statuses`, `metric_assignments`

**UI:** `/dashboard` — Overview экран

### 3.4. Merge View (расширенный)

ESG-менеджер имеет **полный доступ** к Merge View:

- объединённая модель требований (element × standard);
- reused элементы (одно значение закрывает несколько стандартов);
- delta-требования (дополнительные поля при комбинации стандартов);
- пробелы (gaps) — элементы без данных;
- влияние стандартов друг на друга;
- **drill-down** до data point / assignment;
- **actions из merge view:**
  - назначить ответственного (если gap);
  - перейти к data entry;
  - посмотреть evidence.

**Summary bar:**
```
Coverage: GRI 72% | IFRS 45% | SASB 60%
Common elements: 8 | GRI-only: 4 | IFRS-only: 3 | Deltas: 5
```

**Связь с БД:** `requirement_item_shared_elements`, `requirement_item_statuses`, `requirement_deltas`

**UI:** `/merge`

### 3.5. Управление качеством

ESG-менеджер должен видеть и реагировать на:

- **Проблемные зоны:**
  - disclosures с status = `missing`;
  - data points с outlier-флагами;
  - просроченные дедлайны;
  - data points в статусе `rejected` / `needs_revision` > 3 дней;

- **Анализ incomplete disclosures:**
  - конкретика: какой requirement_item не заполнен;
  - кто ответственный;
  - дедлайн;

- **Drill-down:**
  - от disclosure → до requirement_item → до data_point;
  - от пользователя → до его метрик → до статусов;

**UI:** Issues block на Dashboard (аналог mockup Overview)

### 3.6. Управление workflow

ESG-менеджер контролирует жизненный цикл проекта:

- **Перевод проекта** между статусами (см. 3.1);
- **Блокировка редактирования:**
  - при `status = review` — сборщики не могут вводить данные;
  - при `status = published` — все данные read-only;
- **Контроль дедлайнов:**
  - настройка уведомлений (за 7/3/1 день до дедлайна);
  - автоматическая пометка overdue;
- **Откат данных:**
  - ESG-менеджер может перевести `approved → draft` (с обоснованием);
  - записывается в audit_log.

### 3.7. Экспорт и публикация

ESG-менеджер должен иметь возможность:

**Проверка готовности (readiness check):**
- Перед экспортом система показывает:
  - % данных complete;
  - количество warnings (outliers, partial);
  - количество blocking issues (missing mandatory);
  - список конкретных пробелов;

**Экспорт:**

| Формат | Описание |
|--------|----------|
| **GRI Content Index** | Таблица раскрытий со статусами и ссылками на страницы |
| **PDF Report** | Полный отчёт с данными, графиками, evidence references |
| **Excel Data Dump** | Все data points с метаданными для дальнейшей обработки |
| **XBRL** (Phase 3) | Электронная отчётность для регуляторов |

**Публикация:**
- Перевод проекта в `published`;
- Блокировка всех данных (read-only);
- Генерация финального snapshot (версия отчёта);
- Запись в audit_log.

**Связь с БД:** `reporting_projects.status`, `audit_log`

**UI:** `/report` — Export экран с readiness check

### 3.8. Добавление стандарта к проекту

При добавлении нового стандарта к уже работающему проекту:

1. ESG-менеджер выбирает стандарт (например, IFRS S2);
2. Система показывает **impact preview:**
   > "Добавление IFRS S2:
   > - 12 из 18 требований уже покрыты (reuse)
   > - 3 дельты: нужно дозаполнить
   > - 3 новых требования: нужен ввод данных
   > - Текущий coverage IFRS: 67% (из reuse)"
3. ESG-менеджер подтверждает;
4. Система:
   - создаёт `requirement_item_statuses` для новых требований;
   - помечает reused данные как `complete`;
   - помечает дельты и новые как `missing`;
   - пересчитывает completeness.

### 3.9. Data Ownership Model

Каждая метрика (shared_element в контексте проекта) должна иметь чёткую модель владения данными:

| Роль | Поле в `metric_assignments` | Описание |
|------|---------------------------|----------|
| Primary owner | `collector_id` | Основной ответственный за сбор данных |
| Backup owner | `backup_collector_id` | Резервный ответственный (подхватывает при недоступности primary) |
| Escalation rule | `escalation_after_days` | Через сколько дней просрочки запускается эскалация |

**Расширение таблицы `metric_assignments`:**

```sql
ALTER TABLE metric_assignments
    ADD COLUMN backup_collector_id    bigint REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN escalation_after_days  integer NOT NULL DEFAULT 7;
```

**Правила:**
- `backup_collector_id` опционален, но рекомендован для critical metrics
- `backup_collector_id` не может совпадать с `collector_id` и `reviewer_id`
- При эскалации backup_collector получает уведомление с полным контекстом задачи
- ESG-менеджер видит в матрице назначений: primary owner, backup owner, escalation status
- Если primary owner не заполнил данные за `escalation_after_days` дней после дедлайна — backup owner получает задачу

### 3.10. SLA и логика эскалации

Система должна поддерживать SLA (Service Level Agreement) для процесса сбора данных с автоматической эскалацией.

**Пороги SLA breach:**

| Уровень | Условие | Действие |
|---------|---------|----------|
| Warning | Дедлайн через 3 дня, данные не отправлены | Уведомление collector (in-app + email) |
| Breach Level 1 | Дедлайн просрочен на 3 дня | Уведомление backup_collector + ESG-менеджер |
| Breach Level 2 | Дедлайн просрочен на 7 дней | Уведомление admin + пометка critical в dashboard |

**Цепочка эскалации:**

```
collector → backup_collector → ESG-менеджер → admin
```

**Автоматические уведомления:**
- За 3 дня до дедлайна: reminder collector
- В день дедлайна: urgent reminder collector
- +3 дня: эскалация на backup_collector и ESG-менеджер
- +7 дней: эскалация на admin, метрика помечается как critical

**Dashboard-индикатор SLA:**
- Зелёный: в пределах SLA
- Жёлтый: warning (< 3 дней до дедлайна)
- Оранжевый: breach level 1 (просрочено 1-6 дней)
- Красный: breach level 2 (просрочено 7+ дней)

ESG-менеджер должен видеть на Dashboard:
- Количество метрик в каждом SLA-статусе
- Список метрик с breach (с возможностью drill-down)
- Историю эскалаций

**Связь с БД:** `metric_assignments.deadline`, `metric_assignments.escalation_after_days`, `notifications`

---

## 4. Пользовательские сценарии

### Сценарий 1. Запуск проекта

1. ESG-менеджер создаёт проект: "ESG Report 2025"
2. Выбирает период: FY 2025
3. Выбирает стандарты: GRI (base) + IFRS S2
4. Система формирует unified requirement set
5. ESG-менеджер назначает сборщиков и ревьюеров через матрицу
6. Устанавливает дедлайн: June 30
7. Переводит проект в `in_progress`
8. Сборщики получают уведомления

### Сценарий 2. Контроль прогресса

1. ESG-менеджер открывает Dashboard
2. Видит: 68% complete, 6 missing, 5 overdue
3. Кликает "6 missing" → переход к списку
4. Видит: Scope 3 data отсутствует, ответственный Иванов, deadline просрочен
5. Отправляет reminder (или переназначает на другого сборщика)

### Сценарий 3. Добавление стандарта

1. ESG-менеджер решает добавить SASB к проекту
2. Система показывает preview: 8 из 12 покрыты, 4 новых
3. ESG-менеджер подтверждает
4. Назначает ответственных на 4 новых requirement items
5. Coverage обновляется: GRI 72%, IFRS 45%, SASB 67%

### Сценарий 4. Публикация отчёта

1. ESG-менеджер открывает Export
2. Readiness check: 95% complete, 3 warnings, 0 blocking
3. Просматривает warnings → все некритичные
4. Генерирует GRI Content Index (PDF)
5. Генерирует полный PDF-отчёт
6. Переводит проект в `published`
7. Все данные блокируются, audit_log фиксирует публикацию

---

## 5. Ограничения

- ESG-менеджер **не меняет** структуру стандартов (это admin);
- ESG-менеджер **не вводит данные напрямую** (если нет дополнительной роли collector);
- Зависит от настроек администратора (стандарты, requirements);
- Публикация невозможна при наличии blocking issues (missing mandatory);
- Откат published → in_progress требует обоснования и фиксируется в audit_log.

---

## 6. Критерии приемки

- [ ] Можно создать проект с выбором стандартов и периода
- [ ] Можно назначить сборщиков и ревьюеров (индивидуально и массово)
- [ ] Dashboard показывает прогресс по стандартам / темам / пользователям
- [ ] Merge View доступен с drill-down
- [ ] При добавлении стандарта показывается impact preview
- [ ] Readiness check работает перед экспортом
- [ ] Можно экспортировать GRI Content Index (PDF/Excel)
- [ ] Можно перевести проект в `published` (с блокировкой данных)
- [ ] Все действия логируются в audit_log
- [ ] Уведомления о дедлайнах отправляются корректно
