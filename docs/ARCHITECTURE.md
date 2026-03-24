# Архитектура системы NeoFin AI

## 1. Общий обзор

**NeoFin AI** — гибридная AI-платформа финансового анализа предприятий.

Система решает задачу, которую не решает ни один классический финансовый инструмент: она не просто считает коэффициенты — она **объясняет, откуда взялось каждое число**, оценивает надёжность источника и генерирует рекомендации, привязанные к конкретным метрикам.

**Ключевые задачи:**
- Автоматическое извлечение финансовых показателей из PDF-отчётов (текст, таблицы, сканы)
- Расчёт 13 коэффициентов по четырём группам (РСБУ/МСФО) с нормализацией по отраслевым бенчмаркам
- Интегральный скоринг 0–100 с уровнем риска, факторами влияния и нормализованными значениями
- NLP-анализ рисков и генерация рекомендаций через языковые модели
- Многопериодный анализ с хронологической сортировкой и визуализацией динамики

**Почему это AI-система, а не калькулятор:**
---

## 2. Архитектурный подход

### Layered Architecture

Система построена на **строгой послойной архитектуре**. Каждый слой имеет единственную зону ответственности и взаимодействует только с соседними слоями.

```
┌─────────────────────────────────────────────────────┐
│                    Routers (API)                    │
│   FastAPI endpoints · Pydantic validation · Auth    │
│   Rate limiting · HTTP response contracts           │
├─────────────────────────────────────────────────────┤
│               Tasks (Orchestration)                 │
│   Async pipeline · Confidence filter · Key mapping  │
│   Error isolation · Progress tracking               │
├─────────────────────────────────────────────────────┤
│               Analysis (Domain Logic)               │
│   pdf_extractor · ratios · scoring · nlp_analysis   │
│   recommendations · ExtractionMetadata              │
├─────────────────────────────────────────────────────┤
│              AI Service (LLM Abstraction)           │
│   GigaChat · DeepSeek/HF · Ollama · graceful degrade│
│   Единый интерфейс · Fallback chain · Timeout guard │
├─────────────────────────────────────────────────────┤
│                  DB (Persistence)                   │
│   PostgreSQL · SQLAlchemy async · JSONB · Alembic   │
└─────────────────────────────────────────────────────┘
```

**Роль каждого слоя:**

| Слой | Модуль | Ответственность |
|---|---|---|
---

## 3. Pipeline обработки данных

Полный цикл от загрузки PDF до сохранения результата в БД:

```
PDF-файл (загружен через POST /upload)
   │
   ▼
┌──────────────────────────────────────────────────────┐
│  [1] Extractor  (pdf_extractor.py)                   │
│                                                      │
│  Определение типа документа:                         │
│  • Текстовый PDF → PyPDF2 → raw text                 │
│  • Скан → pytesseract OCR → raw text                 │
│  • Таблицы → pdfplumber → structured data            │
│                                                      │
│  Парсинг показателей → ExtractionMetadata:           │
│  { value: float, confidence: 0.3–0.9, source: str }  │
└──────────────────────────────────────────────────────┘
   │
   ▼
┌──────────────────────────────────────────────────────┐
│  [2] Confidence Filter  (_apply_confidence_filter)   │
│                                                      │
│  confidence >= CONFIDENCE_THRESHOLD → value          │
│  confidence <  CONFIDENCE_THRESHOLD → None           │
│                                                      │
│  Все ключи сохраняются в extraction_metadata:        │
│  ненадёжные данные видны в UI, но не влияют на расчёт│
└──────────────────────────────────────────────────────┘
   │
   ▼
┌──────────────────────────────────────────────────────┐
│  [3] Ratios  (ratios.py)                             │
│                                                      │
│  13 коэффициентов по 4 группам:                      │
│  • Ликвидность (3): current, quick, absolute         │
│  • Рентабельность (4): ROA, ROE, ROS, EBITDA margin  │
│  • Устойчивость (3): equity ratio, leverage, coverage│
│  • Активность (3): asset, inventory, receivables     │
│                                                      │
│  Показатель = None → коэффициент = None (не ломает)  │
└──────────────────────────────────────────────────────┘
   │
   ▼
┌──────────────────────────────────────────────────────┐
│  [4] Scoring  (scoring.py)                           │
│                                                      │
│  • Нормализация каждого коэффициента по бенчмаркам   │
│    РСБУ → [0.0, 1.0]                                 │
│  • Взвешенная сумма (веса: ликв. 25%, рент. 35%,     │
│    устойч. 25%, актив. 15%) → скоринг 0–100          │
│  • Отсутствующие коэффициенты исключаются,           │
│    веса перераспределяются автоматически             │
│  • risk_level: низкий (≥75) / средний (≥50) / высокий│
│  • factors[]: impact = positive / neutral / negative │
└──────────────────────────────────────────────────────┘
   │
   ▼
┌──────────────────────────────────────────────────────┐
│  [5] AI Analysis  (nlp_analysis.py + recommendations)│
---

## 4. Гибридная AI-архитектура

NeoFin AI — не pipeline с LLM на конце. Это **двухуровневая система**, где каждый уровень решает свою задачу и может работать независимо.

### Уровень 1 — Детерминированный (всегда активен)

Обеспечивает базовый результат при любых условиях: без сети, без API-ключей, без GPU.

| Компонент | Задача | Свойство |
|---|---|---|
| `pdf_extractor.py` | Извлечение показателей из PDF/сканов | Детерминировано, воспроизводимо |
| `ratios.py` | Расчёт 13 коэффициентов по формулам | Прозрачная математика |
| `scoring.py` | Нормализация по бенчмаркам РСБУ, скоринг 0–100 | Объяснимые веса и пороги |

**Ключевые свойства:**
- Воспроизводимость: одинаковый PDF → одинаковый числовой результат
- Объяснимость: каждый коэффициент имеет формулу, источник данных и confidence
- Независимость: не требует внешних сервисов

### Уровень 2 — Вероятностный (AI-слой)

Активируется при наличии хотя бы одного настроенного LLM-провайдера. Добавляет интерпретацию поверх числового результата.

| Компонент | Задача |
|---|---|
| `nlp_analysis.py` | Анализ текста отчёта: риски, ключевые факторы |
| `recommendations.py` | Рекомендации с явными ссылками на числовые метрики |

**Ключевые свойства:**
- Graceful degradation: при сбое LLM возвращаются пустые списки — числовой анализ не прерывается
- Timeout guard: `asyncio.wait_for` с лимитом 60–65 секунд на каждый вызов
- Результат: `nlp.risks[]`, `nlp.key_factors[]`, `nlp.recommendations[]`
---

## 5. Explainability как архитектурный принцип

Explainability в NeoFin AI — это не дополнительная функция. Это **сквозной принцип**, реализованный на каждом уровне системы.

### Проблема, которую решает Explainability

Классические финансовые инструменты дают число без объяснения. Пользователь видит «ROA = 4.2%», но не знает: это из таблицы или из текста? Насколько можно доверять этому числу? Почему скоринг именно 68, а не 75?

NeoFin AI отвечает на эти вопросы явно.

### Confidence Score

Каждый извлечённый показатель получает оценку надёжности на основе метода извлечения:

| Confidence | Метод извлечения | Тип источника | Интерпретация |
|:---:|---|---|---|
| `0.9` | Точное совпадение ключевого слова в таблице | `table_exact` | Высокая надёжность |
| `0.7` | Частичное совпадение в таблице | `table_partial` | Хорошая надёжность |
| `0.5` | Извлечение через regex из текста | `text_regex` | Приемлемая надёжность |
| `0.3` | Производный расчёт (обязательства = активы − капитал) | `derived` | Низкая надёжность |

### Фильтрация по порогу

```python
# _apply_confidence_filter в tasks.py
# Правило: confidence >= CONFIDENCE_THRESHOLD → включить в расчёт
#           confidence <  CONFIDENCE_THRESHOLD → заменить на None
#
# Важно: все ключи сохраняются в extraction_metadata —
# ненадёжные данные видны в UI, но не влияют на коэффициенты
if meta.confidence < CONFIDENCE_THRESHOLD:
    filtered_metrics[key] = None
else:
    filtered_metrics[key] = meta.value
```

### Explainability в API-ответе

Каждый ответ API содержит полный контекст для объяснения результата:

- `extraction_metadata` — `{confidence, source}` для каждого показателя
- `score.factors[]` — список факторов с `impact: positive | neutral | negative`
- `score.normalized_scores` — нормализованные значения [0, 1] для каждого коэффициента (видно, что «тянет» вниз)

### Explainability в UI

- `ConfidenceBadge` — цветовая маркировка каждого показателя: 🟢 ≥ 0.8 / 🟡 0.5–0.8 / 🔴 < 0.5
- Tooltip с методом извлечения (`source`) при наведении
- Сводка: «Извлечено надёжно: N из 15 показателей»

**Отличие от black-box моделей:** система не просто выдаёт скоринг — она показывает, какие данные использовались, насколько им можно доверять, и какой вклад внёс каждый коэффициент в итоговую оценку.
│  [6] Persistence  (crud.py → PostgreSQL JSONB)       │
│                                  │
│  status: completed / failed                          │
│  data: { metrics, ratios, score, nlp,                │
│          extraction_metadata }                       │
└──────────────────────────────────────────────────────┘
   │
   ▼
React / Mantine UI  ←  GET /result/{task_id}  (polling)
```

---

## 4. Гибридная AI-архитектура

NeoFin AI — не pipeline с LLM на конце. Это **двухуровневая система**, где каждый уровень решает свою задачу и может работать независимо.

### Уровень 1 — Детерминированный (всегда активен)

Обеспечивает базовый результат при любых условиях: без сети, без API-ключей, без GPU.

| Компонент | Задача | Свойство |
|---|---|---|
| `pdf_extractor.py` | Извлечение показателей из PDF/сканов | Детерминировано, воспроизводимо |
| `ratios.py` | Расчёт 13 коэффициентов по формулам | Прозрачная математика |
| `scoring.py` | Нормализация по бенчмаркам РСБУ, скоринг 0–100 | Объяснимые веса и пороги |

**Ключевые свойства:**
- Воспроизводимость: одинаковый PDF → одинвой результат
- Объяснимость: каждый коэффициент имеет формулу, источник данных и confidence
- Независимость: не требует внешних сервисов

### Уровень 2 — Вероятностный (AI-слой)

Активируется при наличии хотя бы одного настроенного LLM-провайдера. Добавляет интерпретацию поверх числового результата.

| Компонент | Задача |
|---|---|
| `nlp_analysis.py` | Анализ текста отчёта: риски, ключевые факторы |
| `recommendations.py` | Рекомендации с явными ссылками на числовые метрики |

**Ключевые свойства:**
- Gceful degradation: при сбое LLM возвращаются пустые списки — числовой анализ не прерывается
- Timeout guard: `asyncio.wait_for` с лимитом 60–65 секунд на каждый вызов
- Результат: `nlp.risks[]`, `nlp.key_factors[]`, `nlp.recommendations[]`

**Принципиальное разделение:**

Детупность внешнего API делает систему неработоспособной.

---

## 5. Explainability как архитектурный принцип

Explainability в NeoFin AI — это не дополнительная функция. Это **сквозной принцип**, реализованный на каждом уровне системы.

### Проблема, которую решает Explainability

Классические финансовые инструменты дают число без объяснения. Пользователь видит «ROA = 4.2%», но не знает: это из таблицы или из текста? Насколько можно доверять этому числу? Почему скоринг именно 68, а не 75?

NeoFin AI отвечает на эти вопросы явно.

### Confidence Score

Каждый извлечённый показатель получает оценку надёжности на основе метода извлечения:

| Confidence | Метод извлечения | Тип источника | Интерпретация |
|:---:|---|---|---|
| `0.9` | Точное совпадение ключевого слова в таблице | `table_exact` | Высокая надёжность |
| `0.7` | Частичное совпадение в таблице | `table_partial` | Хорошая надёжность |
| `0.5` | Извлечение через regex из текста | `text_regex` | Приемлемая надёжность |
| `0.3` | Производный расчёт (обязательства = активы − капитал) | `derived` | Низкая надёжность |

### Фильтрация по порогу

```python
# _apply_confidence_filter в tasks.py
# Правило: confidence >= CONFIDENCE_THRESHOLD → включить в расчёт
#           confidence <  CONFIDENCE_THRESHOLD → заменить на None
#
# Важно: все ключи сохраняются в extraction_metadata —
# ненадёжные данные видны в UI, но не влияют на коэффициенты
if meta.confidence < CONFIDENCE_THRESHOLD:
    filtered_metrics[key] = None
else:
    filtered_metrics[key] = meta.value
```

nability в API-ответе

Каждый ответ API содержит полный контекст для объяснения результата:

- `extraction_metadata` — `{confidence, source}` для каждого показателя
- `score.factors[]` — список факторов с `impact: positive | neutral | negative`
- `score.normalized_scores` — нормализованные значения [0, 1] для каждого коэффициента (видно, что «тянет» вниз)

### Explainability в UI

- `ConfidenceBadge` — цветовая маркировка каждого показателя: 🟢 ≥ 0.8 / 🟡 0.5–0.8 / 🔴 < 0.5
- Torce`) при наведении
- Сводка: «Извлечено надёжно: N из 15 показателей»

**Отличие от black-box моделей:** система не просто выдаёт скоринг — она показывает, какие данные использовались, насколько им можно доверять, и какой вклад внёс каждый коэффициент в итоговую оценку.

---

## 6. Multi-Period Analysis

### Архитектура сессии

```
POST /multi-analysis  (multipart: N PDF + period_labels)
   │
   ▼
MultiAnalysisSession → БД (status=processing)
   │
   ▼
process_multi_analysis()  — фоновая задача (asyncio)
   │
   ├── [period 1] _process_single_period() → PeriodResult
   │              update_multi_session(progress={completed:1, total:N})
   │
   ├── [period 2] _process_single_period() → PeriodResult
   │              update_multi_session(progress={completed:2, total:N})
   │   ...
   │
   └── sort_periods_chronologically(results)
       update_multi_session(status=completed, result={periods:[...]})

GET /multi-analysis/{session_id}
   └── Polling: processing → {progress} / completed → {periods}
```

### Кле архитектурные решения

| Решение | Обоснование |
|---|---|
| Последовательная обработка периодов | Предсказуемое потребление ресурсов, нет конкуренции за CPU/память |
| Частичные сбои не прерывают сессию | `{period_label, error: "processing_failed"}` — остальные периоды обрабатываются |
| NLP пропускается для multi-period | Снижает latency сессии, числовой анализ сохраняется в полном объёме |
| Timeout сессии: 600 сек | Защита от зависания при большом количестве периодов или медленных PDF |
| Х сортировка | `parse_period_label` нормализует форматы `YYYY` и `Q{n}/YYYY` в `(year, quarter)` |

### Форматы period_label

| Формат | Пример | Ключ сортировки |
|---|---|---|
| Год | `2023` | `(2023, 0)` |
| Квартал | `Q1/2023` | `(2023, 1)` |
| Невалидный | `abc` | `(9999, 0)` — в конец списка |

---

## 7. AI Service Layer

### Принцип работы

`AIService` — единственная точка входенений бизнес-логики.

### Fallback Chain

Провайдер выбирается **один раз при старте** приложения в порядке приоритета:

```
AIService._configure()  (вызывается при старте FastAPI)
   │
   ├─ 1. GIGACHAT_CLIENT_ID + GIGACHAT_CLIENT_SECRET заданы?
   │      └─ ✅ GigaChat  (российский LLM, OAuth2, кеш токена 55 мин)
   │
   ├─ 2. HF_TOKEN задан?
   │      └─ ✅ DeepSeek через HuggingFace Inference API
   │             (бесплатный доступ, модель: DeepSeek-R1-Distill-Qwen-7B)
   │
   ├─ 3. LLM_URL задан?
   │      └─ ✅ Ollama  (локальная модель, полный offline)
   │             (deepseek-r1:7b / llama3 / mistral)
   │
   └─ 4. Ни один не настроен?
          └─ ⚠️  Graceful degrade
                 NLP отключён → risks=[], recommendations=[]
                 Числовой анализ продолжается без изменений
```

### Поведение при сбое провайдера

Автоматического переключения на следующий провайдер при сбое **не происходит** — провайдер выбирается один раз при старте. При сбое во время запроса:

| Тип сбоя | Поведение |
|---|---|
| `asyncio.TimeoutError` (> 60–65 сек) | NLP-блок перехватывает, возвращает пустые списки |
| `NetworkError`, `HTTP 5xx` | Аналогично — пустые списки, числовой результат сохраняется |
| Провайдер не настроен | NLP не вызывается вообще |

Ошибка логируется с уровнем `WARNING`. Числовой результат (коэффициенты, скоринг) сохраняется в БД в полном объёме.

### Latency vs Reliability

Timeout в 60–65 секунд — осознанный компромисс:
- Слишком короткий timeout → частые ложные сбои при медленных провайдерах
- Слишком длинный → пользователь ждёт результата неприемлемо долго
- 60–65 сек покрывает 99% реальных запросов к GigaChat и HuggingFace при нормальной нагрузке

### Offline-режим

При `LLM_URL=http://ollama:11434/api/generate` система работает полностью без интернета:
- Числовой анализ: всегда доступен (не зависит от Ollama)
- NLP-анализ: через локальную модель Ollama
- Внешние зависимости: отсутствуют

---

## 8. Хранение данных

### PostgreSQL + JSONB

s`, `created_at`). Результаты анализа хранятся в JSONB — это позволяет расширять структуру данных без миграций схемы.

### Таблица `analyses`

```sql
CREATE TABLE analyses (
    id          SERIAL PRIMARY KEY,
    task_id     VARCHAR(64) UNIQUE NOT NULL,  -- UUID задачи
    created_at  TIMESTAMPTZ DEFAULT now(),
    status      VARCHAR(32) NOT NULL,          -- processing / completed / failed
    result      JSONB                          -- полный результат анализа
);
```

**Структура `result` (JSONB):**
```json
{
  "data": {
    "scanned": false,
    "metrics":  { "revenue": 1000000, "net_profit": 85000, "..." : "..." },
    "ratios":   { "current_ratio": 2.1, "roa": 0.08, "..." : "..." },
    "score":    { "score": 72.5, "risk_level": "medium",
                  "factors": [{ "name": "...", "impact": "positive" }],
                  "normalized_scores": { "current_ratio": 0.87, "..." : "..." } },
    "nlp":      { "risks": ["..."], "key_factors": ["..."], "recommendations": ["..."] },
    "extraction_metadata": {
      "revenue": { "confidence": 0.9, "source": "table_exact" },
      "net_profit": { "confidence": 0.5, "source": "text_regex" }
    }
  }
}
```

### Таблица `multi_analysis_sessions`

```sql
CREATE TABLE multi_analysis_sessions (
    id          SERIAL PRIMARY KEY,
    session_id  VARCHAR(64) UNIQUE NOT NULL,
    user_id     VARCHAR(64),
    status      VARCHAR(32) DEFAULT 'processing',  -- processing / completed / failed
    progress    JSONB,    -- {"completed": 2, "total": 3}
NB,    -- {"periods": [PeriodResult, ...]}
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);
```

### Миграции

Управляются через Alembic. Применяются автоматически при старте контейнера (`entrypoint.sh`).

```
migrations/versions/
├── 0001_initial.py                    — базовая схема
├── 0002_add_analyses.py               — таблица analyses + индексы
└── 0003_add_multi_analysis_sessions.py — таблица multi_analysis_sessions
```

---

## 9. Frontend архитектура

### Стек

- **React 18** + **TypeScript** — строгая типизация, нет `any`
- **Mantine UI** — компонентная библиотека
- **@mantine/charts** (Recharts) — LineChart для TrendChart
- **Vite** — сборка и dev-сервер с proxy на FastAPI

### Ключевые компоненты

**`DetailedReport.tsx`** — главная страница результата анализа
- Вкладки: «Обзор» (одиночный анализ) / «Динамика» (multi-period)
- Хук `useMultiAnalysisPolling` — `setTimeout`-based polling, cleanup при unmount
- Polling останавливается при `status=completed` или ошибке — нет утечек памяти

**`TrendChart.tsx`** — интерактивный график динамики коэффициентов
- `LineChart` из `@mantine/charts`, `connectNulls={false}` — разрывы при `null` (не интерполирует отсутствующие данные)
- Checkbox-селектор коэффициентов — пользователь выбирает, что отображать
- Trend indicators: ↑ рост / ↓ снижение (сравнение последних двух значений)
# Гибкость AI

- Единый интерфейс `AIService` скрывает детали провайдера от бизнес-логики
- Добавление нового LLM-провайдера — реализация одного метода, без изменений pipeline
- Fallback chain настраивается через переменные окружения без перекомпиляции
- Система работает с любым сочетанием провайдеров: только GigaChat, только Ollama, или все три
— система объясняет происхождение данных
- `score.factors[]` с `impact` — прозрачность скорингового решения
- `score.normalized_scores` — видно, какой коэффициент «тянет» вниз
- Принципиальное отличие от black-box: пользователь понимает, почему скоринг именно такой

### Масштабируемость

- Stateless FastAPI — горизонтальное масштабирование без изменений кода
- JSONB в PostgreSQL — расширение схемы результатов без миграций
- Фоновые задачи через `asyncio` — HTTP-слой не блокируется во время обработки PDF

##яет .env → docker-compose.prod.yml up → alembic upgrade head
```

---

## 11. Преимущества архитектуры

### Надёжность

- Детерминированный слой работает без AI-провайдеров — система никогда не возвращает пустой результат
- Graceful degrade при недоступности LLM — числовой анализ не прерывается
- Timeout guard на все AI-вызовы — система не зависает при медленных провайдерах
- Offline-ready через Ollama — полная независимость от внешних сервисов

### Explainability

- Каждый показатель имеет `confidence` и `source`  ┌────────┐
│  PG  │  │ Ollama │  (опционально, только если LLM_URL задан)
│ :5432│  │ :11434 │
└──────┘  └────────┘
```

### Docker Compose сервисы

| Сервис | Образ | Порт | Описание |
|---|---|---|---|
| `nginx` | `nginx:alpine` | 80, 443 | Reverse proxy + раздача статики |
| `backend` | `./Dockerfile` | 8000 | FastAPI + uvicorn |
| `db` | `postgres:16` | 5432 | PostgreSQL |
| `ollama` | `ollama/ollama` | 11434 | Локальная LLM (опционально) |

### Запуск production

```bash
./scripts/start-prod.sh
# Проверционально, cert.pem / key.pem)│
│  • Rate limiting на уровне Nginx                    │
└──────────────┬──────────────────────────────────────┘
               │
       ┌───────┴────────┐
       ▼                ▼
┌─────────────┐   ┌─────────────────────────────┐
│  FastAPI    │   │  React (статика)             │
│  uvicorn    │   │  Собрана Vite → dist/        │
│  :8000      │   │  Раздаётся Nginx напрямую    │
└──────┬──────┘   └─────────────────────────────┘
       │
  ┌────┴────┐
  ▼         ▼
┌──────┐ ted"  → periods[]

// Polling останавливается при completed — нет гонок состояний
if (data.status === "completed") {
  setMultiAnalysisData(data);  // TypeScript знает: data.periods существует
  return;
}
```

---

## 10. Production архитектура

```
Internet
   │
   ▼
┌─────────────────────────────────────────────────────┐
│  Nginx  (порт 80 / 443)                             │
│  • Reverse proxy → FastAPI :8000                    │
│  • Раздача статики React (dist/)                    │
│  • SSL termination (опeBadge.tsx`** — индикатор надёжности показателя
- Цветовая маркировка: 🟢 ≥ 0.8 / 🟡 0.5–0.8 / 🔴 < 0.5
- Tooltip с методом извлечения (`source`) при наведении

### Типизация API

Все типы — в `frontend/src/api/interfaces.ts`. Discriminated union для безопасной обработки состояний:

```typescript
// Discriminated union — TypeScript сужает тип по полю status
type MultiAnalysisResponse =
  | MultiAnalysisProcessingResponse  // status: "processing" → progress
  | MultiAnalysisCompletedResponse   // status: "comple- Anomaly detection: маркер ⚠ при `abs(delta) > anomalyThreshold`
- `series` и `trendMap` мемоизированы через `useMemo` — нет лишних ре-рендеров

**`Confidenc