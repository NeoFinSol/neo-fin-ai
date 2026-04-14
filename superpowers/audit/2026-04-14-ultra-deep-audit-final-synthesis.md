# Ultra-Deep Audit — Phase 8: Final Synthesis

**Дата:** 2026-04-14
**Аудитор:** opencode (4 субагента + 1 дополнительный)
**Scope:** Python backend NeoFin AI — runtime core, orchestration, analysis/math/scoring, schemas/contracts, tests, docs

---

## 1. Final Verdict

**Проект функционально работоспособен, но несёт существенный technical debt в infrastructure layer и cross-cutting concerns.** Анализ-пайплайн (extractor → math → scoring → AI) был значительно усилен за 7 предыдущих волн, однако infra/core/auth/DB-слои остались без системного внимания. Критичных runtime-крашей в happy path нет, но есть 2 BLOCKING import defect и ~30 HIGH issues, часть из которых — реальные security/concurrency/safety риски.

**Рекомендация:** реализовать Immediate roadmap (2 BLOCKING + 5 HIGH security/concurrency) в первую очередь; Short-term roadmap параллельно с продуктовыми задачами; Medium-term — плановый рефакторинг.

---

## 2. Issue Registry — Ranked

### BLOCKING (2) — Runtime crash при import

| # | File | Issue | Impact |
|---|------|-------|--------|
| B1 | `src/models/database/user.py:6` | `from src.core.database import Base` — модуль не существует | `ModuleNotFoundError` при любом import User |
| B2 | `src/models/database/project.py:7` | `from src.core.database import Base` — модуль не существует | `ModuleNotFoundError` при любом import Project |

**Контекст:** `src/models/database/` — orphan directory; реальные ORM models в `src/db/models.py` с правильным `from src.db.database import Base`. Ни user.py, ни project.py не импортируются в runtime path. Defect латентный, но любой `from src.models.database.user import User` — instant crash.

**Fix:** удалить orphan `src/models/database/` целиком, либо исправить import на `src.db.database` если модули нужны.

---

### HIGH — Security (2)

| # | File | Issue | Impact |
|---|------|-------|--------|
| H1 | `src/core/auth.py:40` | Timing-attack: `!=` вместо `hmac.compare_digest` для password compare | Утечка информации через timing side-channel |
| H2 | `src/routers/websocket.py` | Нет authentication на WS endpoint | Unauthorized WebSocket connections |

### HIGH — Concurrency / Runtime Safety (2)

| # | File | Issue | Impact |
|---|------|-------|--------|
| H3 | `src/core/circuit_breaker.py:140-149` | Mutation state без lock; race condition при concurrent open→half-open→close | Flaky circuit breaker behaviour под load |
| H4 | `src/core/ai_service.py:381` | `aiohttp.ClientSession()` создается на каждый Ollama вызов | Resource leak; connection pool exhaustion |

### HIGH — Architecture / SOLID Violations (6)

| # | File | Issue | Impact |
|---|------|-------|--------|
| H5 | `src/core/agent.py:18` | Дублирующий `ConfigurationError` (отличный class identity от `base_agent.ConfigurationError`) | LSP violation: catch в ai_service не ловит agent.ConfigurationError |
| H6 | `src/core/gigachat_agent.py:97`, `huggingface_agent.py:37` | `raise ValueError` вместо `ConfigurationError` | LSP violation: callers ожидают ConfigurationError, получают ValueError |
| H7 | `src/core/ai_service.py:92,104,116` | Доступ к приватному `._configured` на синглтонах | Encapsulation breach; coupling к implementation detail |
| H8 | `src/analysis/nlp_analysis.py:8`, `recommendations.py:9` | Прямой import `ai_service` singleton | DIP violation: analysis layer зависит от конкретной реализации |
| H9 | `src/routers/system.py:49,96,132` | Raw SQL в router, violates "SQL only in crud" rule | Layering violation; SQL injection surface |
| H10 | `src/db/database.py:15` | Upward dependency: db imports from core | Зависимость направлена вверх; violates layered architecture |

### HIGH — Function Length / SRP (5)

| # | File | Issue | Lines |
|---|------|-------|-------|
| H11 | `src/analysis/llm_extractor.py:714-844` | `extract_with_llm` | 132 |
| H12 | `src/analysis/extractor/legacy_helpers.py:497-579, 769-880` | Функции 83 и 112 строк, критические пути без тестов | 83+112 |
| H13 | `src/analysis/extractor/guardrails.py:128-339` | `_apply_form_like_pnl_sanity` | 212 |
| H14 | `src/tasks.py:502-648` | `_try_llm_extraction` — SRP + layering violation | 147 |
| H15 | `src/tasks.py:1124-1293` | `process_multi_analysis` | 170 |

### HIGH — Math/Analysis Layer (5)

| # | File | Issue | Impact |
|---|------|-------|--------|
| H16 | `src/analysis/math/comparative_reasons.py` vs `periods.py:ComparabilityFlag` | Два source of truth для reason codes; уже разъехались (3 кода существуют только в одном из двух) | Inconsistent cross-module semantics |
| H17 | `src/analysis/math/comparative.py:33-34` | `ComparativePeriodInput.metrics: dict[str, Any]` — полностью бестиповый вход | Type safety gap; silent malformed input |
| H18 | `src/analysis/ratios.py:12` | `translate_ratios(ratios: dict)` — полностью бестиповый параметр | Type safety gap |
| H19 | `src/analysis/math/engine.py:112-114` | `ALLOW_ANY_NON_ZERO` пропускает zero/negative denominators | Incorrect denominator validation |
| H20 | `src/analysis/math/precompute.py:21-22,58-73` | Dead `ebitda_canonical`; EBITDA routing gap | Dead code + semantic gap |

### HIGH — Infrastructure (5)

| # | File | Issue | Impact |
|---|------|-------|--------|
| H21 | `src/analysis/pdf_extractor.py:66-80` | Monkey-patching module globals; не thread-safe | Race condition при concurrent requests |
| H22 | `src/analysis/pdf_extractor.py:83-88` | `__getattr__` прячет import errors | Silent import failures; debugging nightmare |
| H23 | `src/core/logging_config.py:102,106` | `TextFormatter.format()` мутирует `record.msg` | Breaks multi-handler setups; side effect in formatter |
| H24 | `src/models/settings.py:423` | Silent `except ValueError` создаёт fallback settings | Invalid settings silently accepted |
| H25 | `src/core/app.py:142-147` | Dev-mode CORS обходит security validation | Security bypass in dev profile |

---

### MEDIUM — Dead/Stale/Redundant Code (5)

| # | File | Issue |
|---|------|-------|
| M1 | `src/analysis/math/registry.py:19` | `STRICT_AVERAGE_BALANCE_METRICS` — dead code (не импортируется) |
| M2 | `src/analysis/math/comparative_reasons.py` | `ALL_COMPARATIVE_REASON_CODES` — dead (declared but never consumed) |
| M3 | `src/exceptions/PdfExtractException.py` | Dead code; candidate for deletion |
| M4 | `src/controllers/` | Пустая директория (1 entry: `__pycache__`) |
| M5 | `src/analysis/extractor/semantics.py:449-526` | `normalize_legacy_metadata` 78 строк с DRY violations |

### MEDIUM — Naming/Semantics (3)

| # | File | Issue |
|---|------|-------|
| M6 | `src/analysis/extractor/rules.py:15-16` | `_LINE_CODE_MAP` маппит 2300 (pre-tax profit) в `net_profit` — semantic mismatch |
| M7 | `src/analysis/math/validators.py` | `classify_denominator` возвращает bare string вместо enum |
| M8 | `src/analysis/llm_extractor.py:133-206` | Дублирование number normalization (3 реализации в проекте) |

### MEDIUM — Docs Mismatches (7)

| # | Issue |
|---|-------|
| D1 | "15 показателей" — реально 19 metrics |
| D2 | Qwen provider не документирован (ARCHITECTURE.md, README) |
| D3 | `OllamaAgent` класс не существует — в docs есть |
| D4 | Ollama не использует shared ClientSession — docs claim единая session |
| D5 | Внутреннее противоречие ARCHITECTURE.md §7 vs §8 (graceful degradation vs exception) |
| D6 | README описывает 3-level architecture, ARCHITECTURE.md — 2-level |
| D7 | Period format inconsistency между API.md и ARCHITECTURE.md |

---

## 3. Test Coverage Gaps — TOP 10

| # | Gap | Risk Level |
|---|-----|------------|
| T1 | Circuit breaker: open→half-open→close lifecycle never tested | HIGH |
| T2 | Extraction pipeline (`pipeline.py`): нет dedicated теста вообще | HIGH |
| T3 | Все metrics ниже confidence threshold → score payload shape | MEDIUM |
| T4 | AI provider malformed/partial JSON response | MEDIUM |
| T5 | `broadcast_task_event` silent failure path | MEDIUM |
| T6 | HuggingFace agent — zero тестов | MEDIUM |
| T7 | Keyword extraction rules regression | MEDIUM |
| T8 | Retry utils infinite loop / wrong delay | MEDIUM |
| T9 | `ws_manager` stale connection crash | MEDIUM |
| T10 | `runtime_decisions.should_prefer_llm_metric` policy change | LOW |

---

## 4. Strong Parts To Preserve

Эти элементы были усилены за 7 волн и являются архитектурно прочными — не трогать без явной причины:

1. **Math Layer v1 foundation** (`src/analysis/math/`) — contracts, policies, engine, registry, projections. Typed, fail-closed, registry-driven.
2. **Decision Transparency** (`src/analysis/extractor/decision_trace.py`) — typed trace projection layer с reason codes.
3. **Extractor staged pipeline** (`src/analysis/extractor/pipeline.py`) — explicit stage contract, no reflection dispatch.
4. **Confidence calibration harness** (`src/analysis/extractor/calibration.py`) — suite-aware corpus, operational metrics, policy diffs.
5. **Canonical Metric Registry** (`src/analysis/math/registry.py`) — `MetricDefinition` как single source of truth для naming, domain constraints, suppression.
6. **Comparative math v1.5** (`src/analysis/math/comparative.py`, `periods.py`) — typed period handling, inconsistency detection, fail-closed linkage.
7. **CI workflow regression tests** (`tests/test_github_workflows.py`) — validates compose, secrets, port mapping, Dockerfile routing.
8. **Upload boundary decomposition** (`src/routers/pdf_tasks.py`) — thin boundary wrapper с explicit helpers.

---

## 5. Refactor Roadmap

### Immediate (1–3 дня) — BLOCKING + Security + Concurrency

| # | Task | Files | Risk |
|---|------|-------|------|
| I1 | Удалить orphan `src/models/database/` (B1, B2) | `src/models/database/` | local-low-risk |
| I2 | Timing-attack fix: `hmac.compare_digest` (H1) | `src/core/auth.py` | local-low-risk |
| I3 | Circuit breaker: добавить `asyncio.Lock` для state mutations (H3) | `src/core/circuit_breaker.py` | cross-module |
| I4 | Ollama: shared `aiohttp.ClientSession` (H4) | `src/core/ai_service.py` | cross-module |
| I5 | WebSocket authentication (H2) | `src/routers/websocket.py` | contract-sensitive |

### Short-term (1–2 недели) — Architecture + SOLID + Typing

| # | Task | Files | Risk |
|---|------|-------|------|
| S1 | Unify `ConfigurationError` (H5, H6) | `agent.py`, `gigachat_agent.py`, `huggingface_agent.py`, `base_agent.py` | cross-module |
| S2 | Encapsulate `_configured` check (H7) | `ai_service.py`, `base_agent.py` | cross-module |
| S3 | DIP: inject AI service interface (H8) | `nlp_analysis.py`, `recommendations.py` | cross-layer |
| S4 | Raw SQL → crud migration (H9) | `system.py`, `crud.py` | cross-layer |
| S5 | Fix `db.database` upward import (H10) | `db/database.py` | cross-module |
| S6 | Type `ComparativePeriodInput.metrics` (H17) | `comparative.py` | local-low-risk |
| S7 | Type `translate_ratios` parameter (H18) | `ratios.py` | local-low-risk |
| S8 | Unify comparative reason codes (H16) | `comparative_reasons.py`, `periods.py` | cross-module |

### Medium-term (2–4 недели) — Function Decomposition + Dead Code + Docs

| # | Task | Files | Risk |
|---|------|-------|------|
| M1 | Decompose `_apply_form_like_pnl_sanity` (H13) | `guardrails.py` | cross-module |
| M2 | Decompose `extract_with_llm` (H11) | `llm_extractor.py` | cross-module |
| M3 | Decompose `_try_llm_extraction` (H14) | `tasks.py` | cross-layer |
| M4 | Decompose `process_multi_analysis` (H15) | `tasks.py` | cross-layer |
| M5 | Remove dead code (M1-M4) | registry, reasons, exceptions, controllers | local-low-risk |
| M6 | Fix `ALLOW_ANY_NON_ZERO` denominator policy (H19) | `engine.py` | cross-module |
| M7 | Thread-safe pdf_extractor globals (H21) | `pdf_extractor.py` | cross-module |
| M8 | Fix logging mutation side effect (H23) | `logging_config.py` | local-low-risk |
| M9 | Unify number normalization (M8) | `llm_extractor.py` + callers | cross-module |
| M10 | Docs synchronization (D1-D7) | docs/* | local-low-risk |

### Test Coverage Roadmap (parallel)

| # | Task | Priority |
|---|------|----------|
| TC1 | Circuit breaker lifecycle test (T1) | HIGH |
| TC2 | Extraction pipeline dedicated test (T2) | HIGH |
| TC3 | HuggingFace agent baseline tests (T6) | MEDIUM |
| TC4 | AI provider malformed JSON test (T4) | MEDIUM |
| TC5 | broadcast_task_event failure test (T5) | MEDIUM |

---

## 6. Dependency Graph Between Roadmap Items

```
I1 (orphan delete) ─────────────────────────────── no deps
I2 (timing attack) ─────────────────────────────── no deps
I3 (circuit breaker lock) ←────── TC1 (lifecycle test)
I4 (shared ClientSession) ──────────────────────── no deps
I5 (WS auth) ←─────────────────── contract-sensitive, needs review

S1 (ConfigurationError) ←──────── H5, H6 both need change together
S7 (type comparative) ──────────────────────────── no deps, standalone
S8 (unify reason codes) ←─────── H16, needs both files in sync

M1-M4 (decompositions) ────────── can be done independently per function
M6 (denominator policy) ←───────── depends on H19 analysis
```

---

## 7. Residual Debt Register

From previous waves, carried forward:

1. `_run_extraction_phase()` ~120 строк — pre-existing structural debt
2. `_try_llm_extraction()` ~150 строк — pre-existing maintainability debt (overlaps with M3)
3. `dict[str, str]` boundary weakness у `upload_pdf()`
4. Parameter threading pressure в `_run_process_pdf()`
5. `_collect_table_candidates` вне `StageCollector` Protocol
6. `AMBIGUOUS_PERIOD_LABEL` flag declared but never emitted
7. `INCOMPATIBLE_PERIOD_CLASS` vs `MISSING_PRIOR_PERIOD` semantic gap
8. `STRICT_AVERAGE_BALANCE_METRICS` drift risk с `averaging_policy` в registry
9. `precompute.py` не должен стать вторым math engine (open item from local_notes)

---

## 8. Recommended Execution Order for Programmers

### Программист 1 (Frontend / Low-risk Backend)
- I1 → I2 → S6 → S7 → M5 → M10 → TC3 → TC4 → TC5

### Программист 2 (Backend Core / Architecture)
- I3 → I4 → I5 → S1 → S2 → S3 → S4 → S5 → S8 → M1-M4 → M6-M9 → TC1 → TC2

B2 (characterization-first before refactor), I5 (contract-sensitive review gate), and S3 (cross-layer DIP) require owner review before merge.

---

## 9. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| Circuit breaker race condition in production | HIGH under load | HIGH | I3 + TC1 |
| Timing attack on auth | LOW (requires proximity) | HIGH | I2 |
| WebSocket unauthorized access | MEDIUM | HIGH | I5 |
| Orphan import crash triggered by future feature | MEDIUM | BLOCKING | I1 |
| Comparative reason code drift | HIGH (already diverged) | MEDIUM | S8 |
| `_configured` encapsulation breach breaks refactoring | MEDIUM | MEDIUM | S2 |
| Logging mutation breaks production monitoring | LOW | MEDIUM | M8 |

---

*End of Phase 8 Final Synthesis. Audit complete.*
