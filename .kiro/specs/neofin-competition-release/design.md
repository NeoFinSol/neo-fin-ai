# Design Document: NeoFin Competition Release

## Overview

NeoFin AI combines **rule-based structured extraction** with **AI-assisted NLP analysis**, augmented by a **confidence scoring mechanism** that ensures interpretability and reliability of financial insights. The system processes financial statements (МСФО/РСБУ) end-to-end: from raw PDF (including scanned documents via OCR) to actionable recommendations — with every decision traceable and explainable.

Финальный этап подготовки к конкурсу «Молодой финансист 2026» закрывает четыре gap-а:

1. **Confidence Score & Explainability** — `pdf_extractor.py` возвращает `Extraction_Metadata` вместо `float | None`; pipeline фильтрует ненадёжные показатели; UI показывает цветные индикаторы с полным explainability tooltip.
2. **Многопериодный анализ** — новые эндпоинты `POST /multi-analysis` и `GET /multi-analysis/{session_id}`; таблица `multi_analysis_sessions` в БД; компонент `TrendChart.tsx` с индикаторами аномалий и трендов.
3. **Документация** — `README.md`, `docs/CONFIGURATION.md`, `docs/ARCHITECTURE.md`, `docs/API.md`, `docs/BUSINESS_MODEL.md`.
4. **Production Build** — `docker-compose.prod.yml`, multi-stage Dockerfiles, `scripts/start-prod.sh`, SSL-ready Nginx.

Существующая цепочка `routers → tasks → analysis pipeline → ai_service → db/crud` остаётся неизменной.

---

## AI Pipeline

NeoFin AI реализует **гибридную архитектуру**: детерминированные финансовые расчёты (коэффициенты, скоринг) комбинируются с вероятностным AI-анализом (NLP, рекомендации). Это позволяет гарантировать корректность числовых результатов при одновременном использовании генеративного AI для качественной интерпретации.

**Уровень 1 — Детерминированный (rule-based + confidence scoring):**
```
PDF → OCR (pytesseract) / table extraction (camelot/pdfplumber)
    → parse_financial_statements_with_metadata()
    → ExtractionMetadata {value, confidence, source}  per metric
    → _apply_confidence_filter(threshold=0.5)
    → 13 financial ratios (calculate_ratios)          ← детерминировано
    → integral scoring 0–100 (calculate_integral_score) ← детерминировано
```

**Уровень 2 — Вероятностный (generative AI с enterprise-grade fallback chain):**
```
PDF text → ai_service.invoke()
         ├─ GigaChat API  (primary, российский LLM)
         ├─ Qwen API      (fallback 1, cloud/local)
         ├─ Ollama local  (fallback 2, fully offline, privacy-first)
         └─ rule-based recommendations (fallback 3, graceful degradation)
    → analyze_narrative()  — риски из пояснительных записок
    → generate_recommendations()  — рекомендации со ссылками на метрики
    → nlp_result {risks, key_factors, recommendations}
```

**Ключевые свойства AI-подсистемы:**
- **High availability** — система продолжает работу при недоступности любого провайдера.
- **Provider independence** — нет привязки к единственному API.
- **Offline-ready** — система полностью функциональна в изолированных средах (Ollama local LLM), что обеспечивает приватность данных и независимость от внешних сервисов.
- **Graceful degradation** — при недоступности всех AI-провайдеров система возвращает rule-based рекомендации вместо ошибки.

Confidence scoring на уровне 1 обеспечивает **интерпретируемость** (каждое решение объяснимо). Fallback chain на уровне 2 обеспечивает **надёжность** (система работает даже в полностью offline-среде). Вместе — это Responsible AI архитектура с enterprise-grade устойчивостью.

---

## Explainability

Каждый извлечённый финансовый показатель сопровождается полным набором метаданных для обеспечения прозрачности:

| Поле | Описание | Пример |
|------|----------|--------|
| `value` | Числовое значение показателя | `312567000.0` |
| `confidence` | Уверенность модели [0.0–1.0] | `0.9` |
| `source` | Метод извлечения | `"table_exact"` |

**Цветовая шкала в UI:**
- 🟢 `confidence > 0.8` — высокая уверенность (таблица, точное совпадение)
- 🟡 `confidence 0.5–0.8` — средняя уверенность (таблица частичное / текст regex)
- 🔴 `confidence < 0.5` — низкая уверенность (производный расчёт), показатель может быть исключён

**Tooltip (Explainability_Block):**
```
Источник: таблица
Метод:    точное совпадение
Уверенность: высокая
```

**Сводная строка:** «Извлечено надёжно: N из 15 показателей»

**Hint:** «Показатели с низкой уверенностью (🔴) могут быть исключены из расчёта коэффициентов»

Это соответствует принципам **Responsible AI**: каждое решение системы прозрачно, воспроизводимо и объяснимо без необходимости интерпретировать "чёрный ящик". Confidence scoring — интерпретируемая эвристическая модель, спроектированная для замены на ML-модель в будущем (например, обученную на размеченных финансовых отчётах).

---

### Изменения в слоях

```
┌─────────────────────────────────────────────────────────────────┐
│  routers/                                                        │
│    analyses.py  (существующий)                                   │
│    multi_analysis.py  ← НОВЫЙ                                    │
├─────────────────────────────────────────────────────────────────┤
│  tasks.py  (расширяется)                                         │
│    process_pdf()  — добавляет extraction_metadata в payload      │
│    process_multi_analysis()  ← НОВАЯ функция                     │
├─────────────────────────────────────────────────────────────────┤
│  analysis/                                                       │
│    pdf_extractor.py  — возвращает ExtractionMetadata вместо      │
│                        float | None                              │
│    ratios.py  — без изменений (принимает dict[str, float|None])  │
│    scoring.py  — без изменений                                   │
├─────────────────────────────────────────────────────────────────┤
│  db/crud.py  (расширяется)                                       │
│    create_multi_session()  ← НОВАЯ                               │
│    update_multi_session()  ← НОВАЯ                               │
│    get_multi_session()  ← НОВАЯ                                  │
├─────────────────────────────────────────────────────────────────┤
│  models/schemas.py  (расширяется)                                │
│    ExtractionMetadataItem, MultiAnalysisRequest,                 │
│    MultiAnalysisResponse, PeriodResult                           │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow: Confidence Score

```
PDF → pdf_extractor.parse_financial_statements_with_metadata()
    → dict[str, ExtractionMetadata]  (15 ключей)
    → tasks._apply_confidence_filter()
    → dict[str, float | None]  (значения ниже порога → None)
    → calculate_ratios()  (без изменений)
    → payload["extraction_metadata"] = {key: {confidence, source}}
    → update_analysis(task_id, "completed", payload)
```

### Data Flow: Multi-Period Analysis

```
POST /multi-analysis  →  router  →  tasks.process_multi_analysis.delay()
                                    (BackgroundTask)
                     →  crud.create_multi_session()
                     →  return {session_id, status: "processing"}

GET /multi-analysis/{session_id}
    →  crud.get_multi_session()
    →  if processing: return {status, progress: {completed, total}}
    →  if completed:  return {status, periods: [...], trend_data: {...}}
```

---

## Components and Interfaces

### Backend: новые функции в `pdf_extractor.py`

**До:**
```python
def parse_financial_statements(tables: list, text: str) -> dict[str, float | None]:
    ...
```

**После:**
```python
ExtractionSource = Literal["table_exact", "table_partial", "text_regex", "derived"]

@dataclass
class ExtractionMetadata:
    value: float | None
    confidence: float   # [0.0, 1.0]
    source: ExtractionSource

def parse_financial_statements_with_metadata(
    tables: list, text: str
) -> dict[str, ExtractionMetadata]:
    ...

# Обратная совместимость — вызывается из tasks.py через _apply_confidence_filter
def parse_financial_statements(tables: list, text: str) -> dict[str, float | None]:
    metadata = parse_financial_statements_with_metadata(tables, text)
    return {k: v.value for k, v in metadata.items()}
```

### Backend: новые функции в `tasks.py`

```python
CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.5"))

def _apply_confidence_filter(
    metadata: dict[str, ExtractionMetadata],
    threshold: float = CONFIDENCE_THRESHOLD,
) -> tuple[dict[str, float | None], dict[str, dict]]:
    """
    Returns:
        filtered_metrics: значения ниже порога заменены на None
        extraction_metadata_payload: {key: {"confidence": float, "source": str}}
    """

async def process_multi_analysis(session_id: str, periods: list[PeriodInput]) -> None:
    """
    Обрабатывает каждый PDF из сессии через существующий pipeline,
    сохраняет результаты в multi_analysis_sessions.
    """
```

### Backend: новые эндпоинты `routers/multi_analysis.py`

```
POST /multi-analysis
  Body: MultiAnalysisRequest
  Response 202: {session_id: str, status: "processing"}

GET /multi-analysis/{session_id}
  Response 200 (processing): MultiAnalysisProcessingResponse
  Response 200 (completed):  MultiAnalysisCompletedResponse
  Response 404: {detail: "Session not found"}
```

### Frontend: новые компоненты

**`ConfidenceBadge.tsx`**
```tsx
interface ConfidenceBadgeProps {
  metricKey: string;
  confidence: number;
  source: ExtractionSource;
}
// Рендерит цветной индикатор + Tooltip с Explainability_Block
// 🟢 > 0.8 | 🟡 0.5–0.8 | 🔴 < 0.5
```

**`TrendChart.tsx`**
```tsx
interface TrendChartProps {
  periods: PeriodResult[];          // отсортированы хронологически
  selectedRatios: string[];         // ключи из RATIO_KEY_MAP
  onRatioSelect: (key: string) => void;
}
// LineChart из @mantine/charts
// None-значения → connectNulls: false (разрыв линии)
```

---

## Data Models

### Новая таблица PostgreSQL

```sql
CREATE TABLE multi_analysis_sessions (
    id          SERIAL PRIMARY KEY,
    session_id  VARCHAR(64) UNIQUE NOT NULL,
    user_id     VARCHAR(64),                    -- NULL для анонимных
    status      VARCHAR(32) NOT NULL DEFAULT 'processing',
    progress    JSONB,                          -- {"completed": N, "total": M}
    result      JSONB,                          -- массив PeriodResult после завершения
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_multi_sessions_session_id ON multi_analysis_sessions(session_id);
CREATE INDEX idx_multi_sessions_created_at ON multi_analysis_sessions(created_at DESC);
```

### Новые Pydantic-схемы (`src/models/schemas.py`)

```python
class ExtractionMetadataItem(BaseModel):
    confidence: float = Field(ge=0.0, le=1.0)
    source: Literal["table_exact", "table_partial", "text_regex", "derived"]

class PeriodInput(BaseModel):
    period_label: str = Field(max_length=20)
    # file передаётся как UploadFile в multipart

class PeriodResult(BaseModel):
    period_label: str
    ratios: dict[str, float | None]   # ключи из RATIO_KEY_MAP (EN)
    score: float | None
    risk_level: str | None
    extraction_metadata: dict[str, ExtractionMetadataItem]

class MultiAnalysisRequest(BaseModel):
    periods: list[PeriodInput] = Field(min_length=1, max_length=5)

class MultiAnalysisProcessingResponse(BaseModel):
    session_id: str
    status: Literal["processing"]
    progress: dict[str, int]          # {"completed": N, "total": M}

class MultiAnalysisCompletedResponse(BaseModel):
    session_id: str
    status: Literal["completed"]
    periods: list[PeriodResult]       # отсортированы хронологически
```

### Обновлённый `frontend/src/api/interfaces.ts`

```typescript
// --- Confidence & Extraction ---
export type ExtractionSource = "table_exact" | "table_partial" | "text_regex" | "derived";

export interface ExtractionMetadataItem {
  confidence: number;   // [0.0, 1.0]
  source: ExtractionSource;
}

// Добавить в AnalysisData:
export interface AnalysisData {
  // ... существующие поля ...
  extraction_metadata?: Record<string, ExtractionMetadataItem>;
}

// --- Multi-Period Analysis ---
export interface PeriodResult {
  period_label: string;
  ratios: Partial<FinancialRatios>;
  score: number | null;
  risk_level: "low" | "medium" | "high" | null;
  extraction_metadata: Record<string, ExtractionMetadataItem>;
}

export interface MultiAnalysisProcessingResponse {
  session_id: string;
  status: "processing";
  progress: { completed: number; total: number };
}

export interface MultiAnalysisCompletedResponse {
  session_id: string;
  status: "completed";
  periods: PeriodResult[];
}

export type MultiAnalysisResponse =
  | MultiAnalysisProcessingResponse
  | MultiAnalysisCompletedResponse;
```

### Production Docker Compose: сервисы

```yaml
# docker-compose.prod.yml — сервисы и зависимости
services:
  db:
    image: postgres:16-alpine
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $POSTGRES_USER"]
      interval: 10s

  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
      target: runtime
    depends_on:
      db: { condition: service_healthy }
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.frontend
      target: serve
    depends_on: [backend]
    ports: ["80:80", "443:443"]
```

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Confidence Score в допустимом диапазоне

*For any* набора финансовых показателей, извлечённых из PDF любым методом, значение `confidence` в `ExtractionMetadata` SHALL быть числом в диапазоне [0.0, 1.0] включительно.

**Validates: Requirements 1.1, 1.10, 5.7**

---

### Property 2: Корректность маппинга source → confidence

*For any* показателя, извлечённого с конкретным `ExtractionSource`, значение `confidence` SHALL точно соответствовать шкале: `table_exact` → 0.9, `table_partial` → 0.7, `text_regex` → 0.5, `derived` → 0.3.

**Validates: Requirements 1.3**

---

### Property 3: Фильтрация по Confidence_Threshold

*For any* набора `ExtractionMetadata` и любого значения `threshold` ∈ [0.0, 1.0], после применения `_apply_confidence_filter(metadata, threshold)` каждый показатель с `confidence < threshold` SHALL иметь значение `None` в результирующем словаре, а каждый показатель с `confidence >= threshold` SHALL сохранить исходное значение.

**Validates: Requirements 1.4, 5.2**

---

### Property 4: Подсчёт надёжных показателей

*For any* словаря `extraction_metadata` с 15 ключами и значения `threshold`, количество показателей с `confidence >= threshold` SHALL точно равняться числу N в строке «Извлечено надёжно: N из 15».

**Validates: Requirements 1.11**

---

### Property 5: Полнота extraction_metadata в API-ответе

*For any* завершённого анализа, поле `extraction_metadata` в ответе API SHALL содержать ровно 15 ключей, соответствующих всем метрикам из `_METRIC_KEYWORDS`, каждый с полями `confidence` (float) и `source` (строка из допустимого набора).

**Validates: Requirements 1.2, 1.6**

---

### Property 6: Валидация метки периода

*For any* строки `period_label`, система SHALL принять её если длина ≤ 20 символов и отклонить (HTTP 422) если длина > 20 символов.

**Validates: Requirements 2.2**

---

### Property 7: Ограничение количества PDF в сессии

*For any* запроса `POST /multi-analysis`, система SHALL принять запрос если количество периодов от 1 до 5 включительно и вернуть HTTP 422 если количество равно 0 или больше 5.

**Validates: Requirements 2.1**

---

### Property 8: Хронологическая сортировка периодов

*For any* набора периодов с метками в формате «YYYY» или «QN/YYYY», загруженных в произвольном порядке, ответ `GET /multi-analysis/{session_id}` SHALL возвращать массив `periods` отсортированным в хронологическом порядке (от раннего к позднему).

**Validates: Requirements 2.12, 5.4**

---

### Property 9: Round-trip сохранения Multi-Period Analysis

*For any* завершённой сессии с N периодами, данные, сохранённые в `multi_analysis_sessions.result`, SHALL быть идентичны данным, возвращаемым `GET /multi-analysis/{session_id}` в поле `periods`.

**Validates: Requirements 2.10**

---

## Error Handling

### Confidence Score

- Если `pdf_extractor` не может определить источник — присваивается `source: "derived"`, `confidence: 0.3` (наиболее консервативная оценка).
- Если `CONFIDENCE_THRESHOLD` задан вне диапазона [0.0, 1.0] — логируется предупреждение, используется значение по умолчанию 0.5.
- Все 15 ключей всегда присутствуют в `extraction_metadata`; для показателей, не найденных в PDF: `{"value": null, "confidence": 0.0, "source": "derived"}`.

### Multi-Period Analysis

- Если один из PDF в сессии не удалось обработать — этот период помечается `{"error": "processing_failed"}`, остальные периоды сохраняются. Сессия переходит в статус `"completed_with_errors"`.
- Если `session_id` не найден — `GET /multi-analysis/{session_id}` возвращает HTTP 404.
- Если сессия в статусе `"processing"` дольше 10 минут — статус автоматически переводится в `"failed"` (timeout guard в `process_multi_analysis`).
- Максимальный размер одного PDF в сессии — тот же лимит 50MB, что и для одиночного анализа.

### Production Build

- Если `SSL_CERT_PATH` не задан — Nginx работает только по HTTP на порту 80 без ошибки запуска.
- `scripts/start-prod.sh` завершается с ненулевым кодом и выводит сообщение об ошибке если `.env` файл отсутствует.
- Health check backend: если `/health` не отвечает за 10 секунд — Docker перезапускает контейнер после 3 неудачных попыток.

---

## Testing Strategy

### Dual Testing Approach

Используются два взаимодополняющих подхода:
- **Unit/integration тесты (pytest)** — конкретные примеры, граничные случаи, проверка эндпоинтов.
- **Property-based тесты (Hypothesis)** — универсальные свойства для всех валидных входных данных.
- **Frontend тесты (vitest)** — рендеринг компонентов с граничными данными.

### Property-Based Tests (Hypothesis, минимум 100 итераций)

Каждый тест помечается комментарием:
`# Feature: neofin-competition-release, Property N: <текст>`

```python
# tests/test_confidence_properties.py

from hypothesis import given, settings
from hypothesis import strategies as st

# Feature: neofin-competition-release, Property 1: confidence_score ∈ [0.0, 1.0]
@given(source=st.sampled_from(["table_exact", "table_partial", "text_regex", "derived"]))
@settings(max_examples=100)
def test_confidence_score_in_range(source):
    confidence = CONFIDENCE_MAP[source]
    assert 0.0 <= confidence <= 1.0

# Feature: neofin-competition-release, Property 2: source→confidence маппинг
@given(source=st.sampled_from(["table_exact", "table_partial", "text_regex", "derived"]))
@settings(max_examples=100)
def test_source_confidence_mapping(source):
    expected = {"table_exact": 0.9, "table_partial": 0.7, "text_regex": 0.5, "derived": 0.3}
    assert CONFIDENCE_MAP[source] == expected[source]

# Feature: neofin-competition-release, Property 3: фильтрация по threshold
@given(
    confidences=st.lists(st.floats(min_value=0.0, max_value=1.0), min_size=1, max_size=15),
    threshold=st.floats(min_value=0.0, max_value=1.0),
)
@settings(max_examples=200)
def test_confidence_filter_correctness(confidences, threshold):
    metadata = {f"metric_{i}": ExtractionMetadata(value=1.0, confidence=c, source="text_regex")
                for i, c in enumerate(confidences)}
    filtered, _ = _apply_confidence_filter(metadata, threshold)
    for key, meta in metadata.items():
        if meta.confidence < threshold:
            assert filtered[key] is None
        else:
            assert filtered[key] == meta.value

# Feature: neofin-competition-release, Property 4: подсчёт надёжных показателей
@given(
    confidences=st.lists(st.floats(min_value=0.0, max_value=1.0), min_size=15, max_size=15),
    threshold=st.floats(min_value=0.0, max_value=1.0),
)
@settings(max_examples=200)
def test_reliable_count_matches_filter(confidences, threshold):
    expected_n = sum(1 for c in confidences if c >= threshold)
    assert count_reliable_metrics(confidences, threshold) == expected_n

# Feature: neofin-competition-release, Property 8: хронологическая сортировка
@given(labels=st.lists(
    st.one_of(
        st.integers(min_value=2000, max_value=2030).map(str),
        st.builds(lambda q, y: f"Q{q}/{y}", st.integers(1,4), st.integers(2000,2030))
    ),
    min_size=1, max_size=5, unique=True
))
@settings(max_examples=200)
def test_periods_sorted_chronologically(labels):
    shuffled = labels.copy()
    random.shuffle(shuffled)
    sorted_result = sort_periods_chronologically(shuffled)
    assert sorted_result == sorted(labels, key=parse_period_label)
```

### Unit / Integration Tests (pytest)

```python
# tests/test_multi_analysis_router.py
def test_post_multi_analysis_returns_session_id(): ...
def test_get_multi_analysis_processing_returns_progress(): ...
def test_get_multi_analysis_not_found_returns_404(): ...
def test_post_multi_analysis_too_many_periods_returns_422(): ...
def test_post_multi_analysis_period_label_too_long_returns_422(): ...

# tests/test_confidence_score.py
def test_table_exact_confidence_is_0_9(): ...
def test_table_partial_confidence_is_0_7(): ...
def test_text_regex_confidence_is_0_5(): ...
def test_derived_confidence_is_0_3(): ...
def test_default_confidence_threshold_is_0_5(): ...
```

### Frontend Tests (vitest)

```typescript
// frontend/src/components/__tests__/TrendChart.test.tsx
// Feature: neofin-competition-release, Example: TrendChart с None-значениями
it("renders without errors when period ratios contain null values", () => {
  const periods = [
    { period_label: "2023", ratios: { current_ratio: null, roa: 0.05 }, ... },
    { period_label: "2024", ratios: { current_ratio: 1.5, roa: null }, ... },
  ];
  expect(() => render(<TrendChart periods={periods} selectedRatios={["current_ratio", "roa"]} />))
    .not.toThrow();
});

// frontend/src/components/__tests__/ConfidenceBadge.test.tsx
it("shows green badge for confidence > 0.8", () => { ... });
it("shows yellow badge for confidence between 0.5 and 0.8", () => { ... });
it("shows red badge for confidence < 0.5", () => { ... });
```

### Алгоритмы (Low-Level Design)

**Определение `extraction_source` (псевдокод):**
```
function determine_source(metric_key, row, match_type, is_derived):
    if is_derived:
        return ("derived", 0.3)
    if match_type == "table":
        keyword = find_matching_keyword(row, METRIC_KEYWORDS[metric_key])
        if keyword == row_text (exact):
            return ("table_exact", 0.9)
        else:
            return ("table_partial", 0.7)
    if match_type == "text_regex":
        return ("text_regex", 0.5)
    return ("derived", 0.3)  # fallback
```

**Сортировка периодов (псевдокод):**
```
function parse_period_label(label: str) -> (year: int, quarter: int):
    if label matches r"^(\d{4})$":
        return (int(label), 0)
    if label matches r"^Q([1-4])/(\d{4})$":
        return (int(year), int(quarter))
    # fallback: лексикографический порядок
    return (9999, 0)

function sort_periods_chronologically(periods):
    return sorted(periods, key=lambda p: parse_period_label(p.period_label))
```

**Multi-stage Dockerfile frontend (stages):**
```dockerfile
# Stage 1: build
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build   # Vite → dist/

# Stage 2: serve
FROM nginx:alpine AS serve
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.prod.conf /etc/nginx/conf.d/default.conf
EXPOSE 80 443
```

**Nginx ключевые блоки:**
```nginx
server {
    listen 80;
    gzip on;
    gzip_types text/plain application/javascript text/css application/json;

    location /api/ {
        proxy_pass http://backend:8000/;
        proxy_set_header Host $host;
    }

    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
        location ~* \.(js|css|png|jpg|svg|ico)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }
}

# SSL block (включается если SSL_CERT_PATH задан через envsubst)
# server { listen 443 ssl; ssl_certificate /etc/nginx/certs/cert.pem; ... }
```
