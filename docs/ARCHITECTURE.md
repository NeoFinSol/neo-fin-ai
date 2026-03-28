# Архитектура системы NeoFin AI

## 1. Общий обзор

**NeoFin AI** — гибридная платформа финансового анализа предприятий на основе PDF-отчётности.

Система решает задачу, которую не решают классические финансовые инструменты: она не просто считает коэффициенты, но и **объясняет происхождение каждого числа**, оценивает надёжность источника, генерирует рекомендации, привязанные к конкретным метрикам, и поддерживает анализ динамики за несколько периодов.

**Ключевые задачи:**
- Автоматическое извлечение 15 финансовых показателей из PDF-отчётов (текст, таблицы, сканы через OCR)
- Оценка надёжности каждого извлечённого показателя через Confidence Score
- Расчёт 13 коэффициентов по четырём группам (РСБУ/МСФО) с нормализацией по отраслевым бенчмаркам
- Интегральный скоринг 0–100 с уровнем риска, факторами влияния и нормализованными значениями
- NLP-анализ рисков и генерация рекомендаций через языковые модели
- Многопериодный анализ с хронологической сортировкой и визуализацией динамики

---

## 2. Архитектурный подход

Система построена на **строгой послойной архитектуре**. Каждый слой имеет единственную зону ответственности и взаимодействует только с соседним нижним слоем. Зависимости строго однонаправлены — сверху вниз.

```
┌─────────────────────────────────────────────────────┐
│                    Routers (API)                    │
│   FastAPI endpoints · Pydantic validation · Auth    │
│   Rate limiting · WebSocket (ws_manager)            │
├─────────────────────────────────────────────────────┤
│               Tasks (Orchestration)                 │
│   Phased execution · WebSocket updates · Error iso  │
│   Confidence filter · Key mapping                   │
├─────────────────────────────────────────────────────┤
│               Analysis (Domain Logic)               │
│   pdf_extractor · ratios · scoring · nlp            │
│   recommendations · confidence · ExtractionMetadata │
├─────────────────────────────────────────────────────┤
│              AI Service (LLM Abstraction)           │
│   BaseAIAgent · Singleton Session · Retry logic     │
│   GigaChat · DeepSeek · Ollama · деградация         │
├─────────────────────────────────────────────────────┤
│                  DB (Persistence)                   │
│   PostgreSQL · SQLAlchemy async · JSONB · Alembic   │
└─────────────────────────────────────────────────────┘
```

**Роль каждого слоя:**

| Слой | Модуль | Ответственность |
|---|---|---|
| Routers | `src/routers/` | HTTP-контракт, WebSocket соединения, валидация входных данных, аутентификация |
| Tasks | `src/tasks.py` | Оркестрация pipeline (пофазно), WebSocket broadcast статусов, фильтрация по Confidence Score |
| Analysis | `src/analysis/` | Чистые функции: извлечение, расчёты, скоринг, NLP, рекомендации |
| AI Service | `src/core/` | `BaseAIAgent` (базовый класс), `AIService` (единая точка доступа), управление ресурсами (Singleton session) |
| DB | `src/db/` | Персистентность, миграции; единственный слой, содержащий SQL |

**Жёсткие архитектурные ограничения:**

| Правило | Пример нарушения |
|---|---|
| SQL только в `src/db/crud.py` | `tasks.py` вызывает `session.execute()` напрямую |
| Доступ к LLM только через `ai_service.py` | `nlp_analysis.py` импортирует `gigachat_agent` напрямую |
| `analysis/*` не зависит от FastAPI/SQLAlchemy | `ratios.py` импортирует `from fastapi import ...` |
| Бизнес-логика только в `tasks.py` и ниже | `routers/upload.py` вызывает `calculate_ratios()` напрямую |

---

## 3. Pipeline обработки данных

Полный цикл от загрузки PDF до сохранения результата и уведомления через WebSocket:

```
POST /upload  →  BackgroundTask запущена, клиент получает task_id немедленно
   │
   ▼
┌──────────────────────────────────────────────────────┐
│  [1] Extraction Phase  (_run_extraction_phase)       │
│                                                      │
│  Определение типа документа:                         │
│  • Анализ первых 3 страниц на наличие /Image объектов│
│  • Smart PDF Detection: если текста мало и есть      │
│    изображения → автоматический запуск OCR           │
│  • Текстовый PDF  →  PyPDF2       →  raw text        │
│  • Скан           →  pytesseract  →  OCR text        │
│  • Таблицы        →  camelot      →  structured data │
│                                                      │
│  ws_manager.broadcast(task_id, status="extracting")  │
└──────────────────────────────────────────────────────┘
   │
   ▼
┌──────────────────────────────────────────────────────┐
│  [2] Scoring Phase  (_run_scoring_phase)             │
│                                                      │
│  • Расчет 13 коэффициентов по 4 группам              │
│  • Нормализация по бенчмаркам РСБУ                   │
│  • Интегральный скоринг 0–100                        │
│  • Расчёт confidence_score (полнота данных)          │
│                                                      │
│  ws_manager.broadcast(task_id, status="scoring")     │
└──────────────────────────────────────────────────────┘
   │
   ▼
┌──────────────────────────────────────────────────────┐
│  [3] AI Analysis Phase  (_run_ai_analysis_phase)     │
│                                                      │
│  • nlp_analysis: риски и факторы (LLM)               │
│  • recommendations: 3–5 советов (LLM)                │
│                                                      │
│  ws_manager.broadcast(task_id, status="analyzing")   │
└──────────────────────────────────────────────────────┘
   │
   ▼
┌──────────────────────────────────────────────────────┐
│  [4] Finalization Phase  (_finalize_task)            │
│                                                      │
│  • crud.update_analysis(status="completed")          │
│  • ws_manager.broadcast(status="completed", result)  │
│  • finally: cleanup_temp_file(file_path)             │
└──────────────────────────────────────────────────────┘

Frontend: useAnalysisSocket.ts (WebSocket) ↔ ws_manager.py
```

---

## 4. Гибридная AI-архитектура

NeoFin AI — не pipeline с LLM на конце. Это **двухуровневая система**, где каждый уровень решает отдельную задачу и может работать независимо.

### Уровень 1 — Детерминированный (всегда активен)

Обеспечивает воспроизводимый числовой результат при любых условиях: без сети, без API-ключей, без GPU. Составляет шаги 1–4 pipeline.

| Компонент | Задача | Ключевое свойство |
|---|---|---|
| `pdf_extractor.py` | Извлечение 15 показателей из PDF/сканов с Confidence Score | Детерминировано, воспроизводимо |
| `ratios.py` | Расчёт 13 коэффициентов по математическим формулам | Прозрачная математика |
| `scoring.py` | Нормализация по бенчмаркам РСБУ, скоринг 0–100 | Объяснимые веса и пороги |

- **Воспроизводимость**: одинаковый PDF → одинаковый числовой результат
- **Объяснимость**: каждый коэффициент имеет формулу, источник данных и Confidence Score
- **Независимость**: не требует внешних сервисов и сетевого доступа
- **OCR hardening**: newline-safe number matching не склеивает соседние строки отчёта, а mock/fallback OCR path всё равно соблюдает `MAX_OCR_PAGES`
- **Corpus regression guard**: сложные table layouts закреплены dataset-driven tests (`tests/data/pdf_regression_corpus.json`)
- **Real-PDF smoke guard**: committed annual-report fixtures в `tests/data/pdf_real_fixtures/` валидируют text-layer extraction по manifest-driven expectations и `sha256` provenance

### Уровень 2 — Вероятностный (AI-слой, опциональный)

Активируется при наличии хотя бы одного настроенного LLM-провайдера. Добавляет качественную интерпретацию поверх числового результата — шаг 5 pipeline.

| Компонент | Задача |
|---|---|
| `nlp_analysis.py` | Анализ текста отчёта: риски и ключевые факторы |
| `recommendations.py` | 3–5 рекомендаций с явными ссылками на числовые метрики |

- **Плавная деградация**: при сбое или недоступности LLM возвращаются пустые списки — числовой результат не прерывается
- **Timeout guard**: `asyncio.wait_for` с лимитом 60–90 секунд предотвращает зависание
- **Token budget control**: перед LLM входной текст детерминированно ужимается — удаляются дубли, page/year noise и low-signal OCR-строки; recommendations используют компактный JSON-контекст вместо длинного prose prompt
- **Результат**: `nlp.risks[]`, `nlp.key_factors[]`, `nlp.recommendations[]`

**Принципиальное разделение**: недоступность LLM-провайдера не влияет на Уровень 1. Пользователь всегда получает числовой результат — в том числе в полностью offline-среде.

---

## 5. Explainability как архитектурный принцип

Explainability — не дополнительная функция, а **сквозной принцип**, реализованный на каждом уровне системы: от извлечения данных до UI.

### Проблема

Классические финансовые инструменты дают число без объяснения. Пользователь видит «ROA = 4.2%», но не знает: это из таблицы или из текста? Насколько можно доверять этому числу? Почему скоринг именно 68, а не 75?

NeoFin AI отвечает на эти вопросы явно на каждом шаге.

### Confidence Score

Каждый извлечённый показатель получает оценку надёжности на основе метода извлечения:

| Confidence | Метод извлечения | ExtractionSource | Уровень надёжности |
|:---:|---|---|---|
| `0.9` | Точное совпадение ключевого слова в таблице | `table_exact` | Высокая |
| `0.7` | Частичное совпадение в таблице | `table_partial` | Хорошая |
| `0.5` | Извлечение через regex из текста | `text_regex` | Приемлемая |
| `0.3` | Производный расчёт (обязательства = активы − капитал) | `derived` | Низкая |
| `0.0` | Показатель не найден в документе | `derived` | Отсутствует |

### Фильтрация по порогу

```python
# tasks._apply_confidence_filter()
# Правило:
#   confidence >= CONFIDENCE_THRESHOLD → передаётся в calculate_ratios()
#   confidence <  CONFIDENCE_THRESHOLD → заменяется на None
#
# Важно: все 15 ключей сохраняются в extraction_metadata.
# Ненадёжные показатели отображаются в UI, но не влияют на коэффициенты.
if meta.confidence < threshold:
    filtered_metrics[key] = None        # исключён из расчёта
else:
    filtered_metrics[key] = meta.value  # участвует в расчёте
```

### Explainability в ответе API

Каждый ответ содержит полный контекст для объяснения результата:

- `extraction_metadata` — `{"confidence": float, "source": str}` для каждого из 15 показателей
- `score.factors[]` — список факторов с `impact: positive | neutral | negative`
- `score.normalized_scores` — нормализованные значения `[0.0, 1.0]` для каждого коэффициента (видно, какой «тянет» вниз)

### Explainability в UI

- **`ConfidenceBadge`** — цветовая маркировка каждого показателя: 🟢 ≥ 0.8 / 🟡 0.5–0.8 / 🔴 < 0.5
- **Tooltip** при наведении — структурированный блок: «Источник», «Метод», «Уверенность»
- **Приглушённый стиль** строки при `confidence < CONFIDENCE_THRESHOLD`
- **Сводная строка**: «Извлечено надёжно: N из 15 показателей»
- **Hint**: «Показатели с низкой уверенностью (🔴) могут быть исключены из расчёта коэффициентов»

**Отличие от black-box**: система не просто выдаёт скоринг — она показывает, какие данные использовались, насколько им можно доверять, и какой вклад внёс каждый коэффициент в итоговую оценку.

---

## 6. Multi-Period Analysis

### Архитектура сессии

```
POST /multi-analysis  (multipart: до 5 PDF + period_labels)
   │
   ▼
crud.create_multi_session()
   →  БД: status="processing", progress={completed:0, total:N}
   →  клиент получает session_id немедленно
   │
   ▼
BackgroundTask: process_multi_analysis(session_id, periods)
   │
   ├── [period 1]  _process_single_period()  →  PeriodResult
   │               update_multi_session(progress={completed:1, total:N})
   │
   ├── [period 2]  _process_single_period()  →  PeriodResult
   │               update_multi_session(progress={completed:2, total:N})
   │   ...
   │
   ├── Timeout guard: если обработка > 600 сек → status="failed"
   │
   └── sort_periods_chronologically(results)
       update_multi_session(status="completed", result={periods:[...]})

GET /multi-analysis/{session_id}
   ├── status="processing"  →  {status, progress: {completed, total}}
   ├── status="completed"   →  {status, periods: [PeriodResult, ...]}
   └── session не найден    →  HTTP 404
```

### Ключевые архитектурные решения

| Решение | Обоснование |
|---|---|
| Последовательная обработка периодов | Предсказуемое потребление ресурсов, нет конкуренции за CPU и память |
| Частичные сбои не прерывают сессию | Сбойный период помечается `{"error": "processing_failed"}`, остальные обрабатываются |
| Timeout сессии 600 сек | Защита от зависания при большом количестве периодов или медленных PDF |
| Хронологическая сортировка результатов | `parse_period_label` нормализует форматы `YYYY` и `Q{n}/YYYY` в ключ `(year, quarter)` |
| NLP не вызывается для multi-period | Снижает общее время сессии; числовой результат сохраняется в полном объёме |

### Форматы period_label

| Формат | Пример | Ключ сортировки |
|---|---|---|
| Год | `2023` | `(2023, 0)` |
| Квартал | `Q1/2023` | `(2023, 1)` |
| Нераспознанный | `abc` | `(9999, 0)` — помещается в конец |

### Ограничения

- Максимум 5 периодов в одной сессии — HTTP 422 при превышении
- Длина `period_label` не более 20 символов — HTTP 422 при превышении
- Максимальный размер одного PDF — 50 МБ (тот же лимит, что у одиночного анализа)

---

## 7. AI Service Layer

### Архитектура агентов (BaseAIAgent)

Для унификации работы с различными AI-провайдерами внедрена иерархия классов на базе `BaseAIAgent`.

```
      BaseAIAgent (abstract)
      │ • Singleton aiohttp.ClientSession
      │ • Exponential backoff retry logic
      │ • Common resource cleanup
      │
      ├── GigaChatAgent
      │     • OAuth2 flow with token caching
      │     • SSL certificate handling
      │
      ├── DeepSeekAgent (HuggingFace)
      │     • Bearer token auth
      │
      └── OllamaAgent
            • Local endpoint communication
```

### Принцип работы

`ai_service.py` — единственная точка доступа к LLM во всей системе. Модули `nlp_analysis.py` и `recommendations.py` не импортируют LLM-провайдеров напрямую: все вызовы проходят через `AIService.invoke()`.

**Управление ресурсами**:
- Использование **Singleton ClientSession** в `BaseAIAgent` предотвращает исчерпание портов (port exhaustion) при высокой нагрузке.
- Сессия автоматически пересоздается при закрытии или ошибках.
- Реализованы экспоненциальные повторы (retries) для обработки временных сбоев сети или API.

### Выбор провайдера при запуске

Провайдер выбирается **один раз при старте** приложения — в FastAPI lifespan, до обработки первого запроса. В runtime смены провайдера не происходит.

```
AIService._configure()  (вызывается однократно при старте FastAPI)
   │
   ├─ 1. GIGACHAT_CLIENT_ID + GIGACHAT_CLIENT_SECRET заданы?
   │      └─ ✅  GigaChat (OAuth2, Singleton ClientSession, кеш токена 55 мин)
   │
   ├─ 2. HF_TOKEN задан?
   │      └─ ✅  DeepSeek-R1 через HuggingFace Inference API
   │             модель: DeepSeek-R1-Distill-Qwen-7B
   │
   ├─ 3. LLM_URL задан?
   │      └─ ✅  Ollama (локальная LLM, полный offline)
   │             поддерживаемые модели: deepseek-r1:7b, llama3, mistral
   │
   └─ 4. Ни один не настроен?
          └─ ⚠️  Плавная деградация
                 NLP полностью отключён
                 risks=[], key_factors=[], recommendations=[]
                 Числовой результат не затрагивается
```

### Поведение при сбое провайдера

Провайдер выбран при старте и не меняется. При сбое во время обработки запроса:

| Тип сбоя | Поведение |
|---|---|
| `asyncio.TimeoutError` (> 60–65 сек) | NLP-блок перехватывает исключение, возвращает пустые списки |
| `NetworkError`, HTTP `5xx` | Аналогично — пустые списки, числовой результат сохраняется |
| Провайдер не настроен | NLP-вызов не происходит вообще |

Все сбои логируются с уровнем `WARNING`. Числовой результат (коэффициенты, скоринг, extraction_metadata) в любом случае сохраняется в базе данных.

### Offline-режим

При `LLM_URL=http://ollama:11434/api/generate` система работает полностью без интернета:
- Числовой результат — всегда доступен, не зависит от Ollama
- NLP-анализ — через локальную модель Ollama
- Внешние зависимости — отсутствуют

---

## 8. AI Pipeline и Fallback Chain

### Fallback chain при вызове AIService.invoke()

Это детализация поведения внутри одного вызова `ai_service.invoke(prompt)`. Архитектура выбора провайдера при старте описана в разделе 7.

```
ai_service.invoke(prompt)
   │
   ├── GigaChat  (если выбран при старте)
   │   ├── Получить/обновить OAuth2-токен (кеш 55 мин)
   │   ├── POST /chat/completions, timeout=120s
   │   └── Ошибка → logging.warning(); исключение передаётся выше
   │
   ├── HuggingFace / DeepSeek  (если выбран при старте)
   │   ├── Bearer HF_TOKEN
   │   ├── POST inference API, timeout=120s
   │   └── Ошибка → logging.warning(); исключение передаётся выше
   │
   ├── Ollama local  (если выбран при старте)
   │   ├── POST {LLM_URL}, timeout=120s
   │   └── Ошибка → logging.warning(); исключение передаётся выше
   │
   └── Провайдер не настроен
       └── raise AINotConfiguredError
           → перехватывается в nlp_analysis.py / recommendations.py
           → возвращаются пустые списки; pipeline продолжается
```

**Ключевое свойство**: нет автоматического переключения между провайдерами при сбое в runtime. Это осознанное решение — предсказуемое поведение важнее скрытого восстановления с непрозрачной логикой. При сбое провайдера NLP-блок деградирует явно и управляемо.

### Таймауты

| Параметр | Значение | Где задан |
|---|---|---|
| `AI_TIMEOUT` | 120 сек | `agent.py`, `gigachat_agent.py`, `ai_service.py` — менять синхронно во всех трёх |
| `NLP_TIMEOUT` | 60 сек | `asyncio.wait_for` в `tasks.py` |
| `REC_TIMEOUT` | 90 сек | `timeout=90` в `recommendations.py` → `ai_service.invoke()` |

60–65 секунд на уровне `tasks.py` — осознанный компромисс: достаточно для покрытия 99% запросов к GigaChat и HuggingFace при нормальной нагрузке, но не настолько долго, чтобы ощутимо задержать ответ пользователю.

---

## 9. Хранение данных

Хранение стало гибридным. Полный результат анализа по-прежнему остаётся в JSONB как канонический snapshot, а наиболее горячие поля (`filename`, `score`, `risk_level`, `scanned`, `confidence_score`, `completed_at`, `error_message`) дополнительно вынесены в typed summary columns. Это даёт быстрый history/list path и основу для bounded cleanup jobs, не ломая внешний API и не отказываясь от гибкости JSONB.

### Таблица `analyses`

```sql
CREATE TABLE analyses (
    id          SERIAL PRIMARY KEY,
    task_id     VARCHAR(64) UNIQUE NOT NULL,
    status      VARCHAR(32) NOT NULL DEFAULT 'processing',
    filename    VARCHAR(255),
    score       DOUBLE PRECISION,
    risk_level  VARCHAR(16),
    scanned     BOOLEAN,
    confidence_score DOUBLE PRECISION,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    result      JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_analyses_task_id    ON analyses(task_id);
CREATE INDEX idx_analyses_created_at ON analyses(created_at DESC);
ALTER TABLE analyses
  ADD CONSTRAINT ck_analyses_status_valid
  CHECK (status IN ('uploading', 'processing', 'completed', 'failed', 'cancelled'));
ALTER TABLE analyses
  ADD CONSTRAINT ck_analyses_risk_level_valid
  CHECK (risk_level IS NULL OR risk_level IN ('low', 'medium', 'high', 'critical'));
ALTER TABLE analyses
  ADD CONSTRAINT ck_analyses_score_range
  CHECK (score IS NULL OR (score >= 0 AND score <= 100));
ALTER TABLE analyses
  ADD CONSTRAINT ck_analyses_confidence_score_range
  CHECK (confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1));
```

**Структура `result` (JSONB):**

```json
{
  "data": {
    "scanned": false,
    "metrics": {
      "revenue": 1000000,
      "net_profit": 85000
    },
    "ratios": {
      "current_ratio": 2.1,
      "roa": 0.08
    },
    "score": {
      "score": 72.5,
      "risk_level": "medium",
      "factors": [
        {"name": "Текущая ликвидность", "impact": "positive"}
      ],
      "normalized_scores": {
        "current_ratio": 0.87,
        "roa": 0.64
      }
    },
    "nlp": {
      "risks": ["..."],
      "key_factors": ["..."],
      "recommendations": ["..."]
    },
    "extraction_metadata": {
      "revenue":     {"confidence": 0.9, "source": "table_exact"},
      "net_profit":  {"confidence": 0.5, "source": "text_regex"},
      "liabilities": {"confidence": 0.3, "source": "derived"}
    }
  }
}
```

**Принцип хранения `analyses`:**

- `result` остаётся canonical snapshot для detail API и будущих расширений payload shape
- typed summary columns dual-write'ятся из того же snapshot в `create_analysis()` / `update_analysis()`
- `/analyses` предпочитает typed columns и откатывается к JSONB только для legacy rows, где бэкфилл ещё не был применён
- status-only update не должен стирать уже сохранённый snapshot: при `result=None` сохраняется предыдущий payload

### Таблица `multi_analysis_sessions`

```sql
CREATE TABLE multi_analysis_sessions (
    id          SERIAL PRIMARY KEY,
    session_id  VARCHAR(64) UNIQUE NOT NULL,
    user_id     VARCHAR(64),
    status      VARCHAR(32) NOT NULL DEFAULT 'processing',
    progress    JSONB,
    result      JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_multi_sessions_session_id  ON multi_analysis_sessions(session_id);
CREATE INDEX idx_multi_sessions_created_at  ON multi_analysis_sessions(created_at DESC);
CREATE INDEX idx_multi_sessions_status_updated_at
  ON multi_analysis_sessions(status, updated_at);
ALTER TABLE multi_analysis_sessions
  ADD CONSTRAINT ck_multi_sessions_status_valid
  CHECK (status IN ('processing', 'completed', 'failed'));
```

- **`progress`**: `{"completed": 2, "total": 3}` — обновляется после каждого обработанного периода
- **`result`**: `{"periods": [PeriodResult, ...]}` — заполняется при `status="completed"`
- **`updated_at`**: обновляется ORM-слоем на каждом `update_multi_session()`, а composite index ускоряет operational queries по lifecycle state

### Миграции

Управляются через Alembic и применяются автоматически при запуске production-контейнера через `scripts/start-prod.sh`.

```
migrations/versions/
├── 0001_create_analyses.py                       — таблица analyses
├── 0002_add_status_created_at_indexes.py         — индексы analyses
├── 0003_add_multi_analysis_sessions.py           — таблица multi_analysis_sessions
├── 0004_harden_db_status_constraints.py          — status constraints + lifecycle index
└── 0005_add_analysis_summary_columns.py          — typed summary columns + JSONB backfill
```

### Runtime notes for persistence

- `src/db/database.py` применяет `DB_POOL_TIMEOUT` и `DB_POOL_RECYCLE` в реальный async engine config, а не только логирует их.
- При `TESTING=1` engine предпочитает `TEST_DATABASE_URL`, чтобы не смешивать test traffic с основной БД.
- FastAPI lifespan вызывает `dispose_engine()` на shutdown, чтобы не оставлять stale pooled connections при restart/test teardown.
- Router boundary (`analyses`, `pdf_tasks`, `multi_analysis`) переводит SQLAlchemy read/write failures в явный `DatabaseError`, а не в `None`/ложный `404`.
- `src/db/crud.py` держит dual-write invariant: typed summary columns выводятся из того же `result` snapshot и не становятся отдельным source of truth.
- cleanup helpers (`find_analysis_cleanup_candidates`, `cleanup_analyses`, `find_multi_session_cleanup_candidates`, `cleanup_multi_sessions`) работают batch-wise и поддерживают `dry_run`, чтобы maintenance/delete path можно было запускать безопасно и наблюдаемо.

---

## 10. Frontend архитектура

### Стек

- **React 18** + **TypeScript** — строгая типизация, без `any`
- **Mantine UI** — компонентная библиотека
- **@mantine/charts** (Recharts) — `LineChart` для `TrendChart`
- **Vite** — сборка и dev-сервер с proxy (`/api` → `http://localhost:8000`)

### Структура модулей

```
frontend/src/
├── api/
│   ├── client.ts       — axios-клиент, baseURL=/api (через Vite proxy)
│   └── interfaces.ts   — единственный источник типов; types.ts удалён
├── context/
│   ├── AnalysisContext.tsx        — состояние анализа на уровне приложения
│   └── AnalysisHistoryContext.tsx — история записей
├── pages/
│   ├── Dashboard.tsx       — загрузка PDF, запуск анализа
│   ├── DetailedReport.tsx  — результат анализа (одиночный + multi-period)
│   ├── AnalysisHistory.tsx — список анализов с пагинацией
│   └── Auth.tsx            — валидация API-ключа
└── components/
    ├── ConfidenceBadge.tsx — индикатор надёжности показателя
    ├── TrendChart.tsx      — график динамики коэффициентов
    └── Layout.tsx          — навигация, обёртка страниц
```

### Ключевые компоненты

**`AnalysisContext.tsx`** — контекст анализа на уровне приложения.
Хранит `status`, `result`, `filename`, `error`; предоставляет `analyze()` и `reset()`. Переживает навигацию между страницами, так как не привязан к жизненному циклу конкретного компонента.

**`DetailedReport.tsx`** — главная страница результата.
- Вкладки: «Обзор» (одиночный анализ) / «Динамика» (multi-period)
- Polling `GET /multi-analysis/{session_id}` через `setTimeout` с очисткой при unmount
- Discriminated union для типобезопасной обработки состояний:

```typescript
type MultiAnalysisResponse =
  | MultiAnalysisProcessingResponse  // status: "processing" → progress
  | MultiAnalysisCompletedResponse;  // status: "completed"  → periods[]
```

**`TrendChart.tsx`** — интерактивный график динамики коэффициентов.
- `LineChart` из `@mantine/charts`, `connectNulls={false}` — явный разрыв линии при `null`; нет интерполяции отсутствующих данных
- Checkbox-селектор: пользователь выбирает, какие коэффициенты отображать
- Trend indicators: стрелки ↑↓ по сравнению двух последних значений
- Anomaly detection: маркер ⚠ при `abs(delta) > anomalyThreshold`
- `series` и `trendMap` мемоизированы через `useMemo`

**`ConfidenceBadge.tsx`** — индикатор надёжности показателя.
- Цветовая маркировка: 🟢 ≥ 0.8 / 🟡 0.5–0.8 / 🔴 < 0.5
- Tooltip: «Источник», «Метод», «Уверенность»
- Приглушённый стиль строки при `confidence < CONFIDENCE_THRESHOLD`

### Polling-механизм

```
POST /upload  →  task_id
   │
   └── AnalysisContext.analyze()
         └── setTimeout (2000 мс, рекурсивный)
               └── GET /result/{task_id}
                     ├── status="processing"  →  продолжить polling
                     ├── status="completed"   →  setResult(data), остановить
                     └── status="failed"      →  setError(), остановить

clearTimeout при unmount — нет утечек памяти
```

---

## 11. Production архитектура

```
Internet
   │
   ▼
┌──────────────────────────────────────────────────────┐
│  Nginx  (порт 80)                                    │
│  • Reverse proxy: /api/ → FastAPI :8000              │
│  • Статика React baked into image                    │
│  • gzip для JS/CSS/JSON                              │
│  • Cache-Control: immutable для статических ассетов  │
│  • Rate limiting                                     │
└──────────────┬───────────────────────────────────────┘
               │
       ┌───────┴────────┐
       ▼                ▼
┌─────────────┐   ┌─────────────────────────────┐
│  FastAPI    │   │  React (статика)             │
│  uvicorn    │   │  Multi-stage build inside    │
│  :8000      │   │  `frontend/Dockerfile.frontend` │
└──────┬──────┘   └─────────────────────────────┘
       │
  ┌────┴────┐
  ▼         ▼
┌──────┐  ┌────────┐
│  PG  │  │ Ollama │  (опционально, только если LLM_URL задан)
│ :5432│  │ :11434 │
└──────┘  └────────┘
```

### Docker Compose сервисы (`docker-compose.prod.yml`)

| Сервис | Образ | Порт | Описание |
|---|---|---|---|
| `db` | `postgres:16-alpine` | 5432 | PostgreSQL; health check: `pg_isready`, interval 10s |
| `backend` | `./Dockerfile.backend` (multi-stage) | 8000 | FastAPI + uvicorn; health check: `GET /health`, interval 30s, timeout 10s |
| `nginx` | `./frontend/Dockerfile.frontend` (multi-stage) | 80 | Self-contained Nginx + production build React + `/api` reverse proxy |

`backend` запускается только после `db: condition: service_healthy`.

### Multi-stage Dockerfiles

**`Dockerfile.backend`:**
- Stage `build`: установка Python-зависимостей
- Stage `runtime`: минимальный образ без dev-зависимостей

**`frontend/Dockerfile.frontend`:**
- Stage `build`: Node.js + `npm ci` + `npm run build` (Vite → `dist/`)
- Stage `serve`: Nginx + статика из `dist/` + production proxy config из `frontend/nginx.prod.conf`

### SSL-конфигурация

Текущий production compose разворачивает HTTP-only путь на `:80`. Блок HTTPS в `frontend/nginx.prod.conf` остаётся шаблоном для отдельной future hardening-итерации.

### Запуск production

```bash
./scripts/deploy-prod.sh
# Проверяет наличие .env — завершается с ошибкой если файл отсутствует
# docker compose -f docker-compose.prod.yml config
# docker compose -f docker-compose.prod.yml up -d --build
# Запускает backend-migrate отдельным контейнером перед стартом backend
```

После запуска система доступна на порту 80 без дополнительной настройки.

### Операционные заметки после audit wave 1

- `backend-migrate` зависит от наличия `entrypoint.sh` внутри backend image; `Dockerfile.backend` должен копировать этот файл и делать его executable.
- `GET /analyses/{task_id}` возвращает inner payload `result.data`, а не целиком JSONB-объект результата.
- `tasks.py` шлёт промежуточные WebSocket-статусы `extracting`, `scoring`, `analyzing` до финального `completed|failed`.
- `process_multi_analysis()` нормализует частично успешные сессии к статусу `completed`, а ошибки отдельных периодов остаются внутри `periods[].error`.

---

## 12. Преимущества архитектуры

### Надёжность

- **Детерминированный базис**: числовой результат доступен всегда — даже без сети и без LLM-провайдеров
- **Плавная деградация**: при сбое LLM NLP-блок возвращает пустые списки; числовой результат не затрагивается
- **Timeout guard**: `asyncio.wait_for` на все AI-вызовы исключает зависание pipeline
- **Частичная устойчивость в multi-period**: сбой одного периода не прерывает обработку остальных
- **Offline-ready**: при настроенном Ollama система полностью независима от внешних сервисов

### Explainability

- **Confidence Score** на каждом показателе — система объясняет происхождение данных, а не скрывает его
- **extraction_metadata** в ответе API — полная трассируемость от сырого PDF до числа в UI
- **score.factors[]** с `impact` — пользователь видит, что именно повлияло на скоринг
- **score.normalized_scores** — видно, какой коэффициент «тянет» оценку вниз
- В отличие от black-box моделей, каждое решение системы воспроизводимо и объяснимо без интерпретации внутреннего состояния

### Гибкость AI-слоя

- Единый интерфейс `AIService` скрывает детали провайдера от бизнес-логики
- Добавление нового LLM-провайдера требует реализации одного метода, без изменений pipeline
- Выбор провайдера управляется переменными окружения без перекомпиляции
- Система работает с любым набором провайдеров: только GigaChat, только Ollama, или несколько одновременно (первый по приоритету)

### Масштабируемость

- **Stateless FastAPI**: горизонтальное масштабирование без изменений кода
- **JSONB в PostgreSQL**: расширение структуры результатов без новых миграций схемы
- **Фоновые задачи через asyncio**: HTTP-слой не блокируется во время обработки PDF
- **Code splitting по маршрутам в Vite**: frontend загружается частями, уменьшая initial bundle

### Тестируемость

- Чистые функции в `analysis/` тестируются изолированно — без FastAPI и без базы данных
- Property-based тесты (Hypothesis) верифицируют инварианты Confidence Score и фильтрации для произвольных входных данных
- Discriminated union на frontend: TypeScript статически запрещает доступ к `periods` в состоянии `"processing"`
- Моки AI-провайдеров через стандартный `unittest.mock` — тесты не требуют реальных API-ключей
