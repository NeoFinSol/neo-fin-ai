# Math Layer v2 — Wave 3 Phase 7 Freeze (TASK-038)

**Дата:** 2026-04-19  
**Статус:** Wave 3 runtime + Phase 6 startup validation + Phase 7 test matrix — **закрыты для текущего объёма реестра**.  
**Не является:** финальным Wave 4 reason-governance freeze.

---

## 1. Spec compliance (краткий аудит)

| Область | Статус |
|---------|--------|
| Typed `MetricCandidate` / `CandidateSet` / отказ от raw dict в resolver path | Соответствует Wave 3 spec + design |
| Synthetic contract (`DECLARED_SYNTHETIC_KEYS`, producers) | Реализовано + startup (Phase 6) + unit suite (Phase 7) |
| Coverage как runtime-affecting | `enforce_coverage` + тесты классов в реестре |
| Resolver registry + precedence canonical home | Да |
| Средний pipeline: precompute → set → eligibility → resolver → coverage → basis → compute | Реализовано в `engine.py`; Phase 7 добавляет E2E/детерминизм проверки |
| Startup validation deliverables 11–12 (Phase 6) | Выполнено ранее в этой ветке |

Известные **намеренные** упрощения относительно полного текста design: упрощённый `ResolverDecision` против длинного DTO в design-документе (зафиксировано в tech debt / prior review).

---

## 2. SOLID / Clean Code (freeze pass)

- Крупные orchestrator-функции в `engine.py` остаются зоной будущего рефакторинга (не блокер freeze тестов).
- Новые Phase 7 тесты разнесены по файлам по TASK-032…037; длинные фикстуры минимизированы.
- Inline `wave3_*` reason literals — блокируются Phase 6 AST scan + Phase 7 spot-check `precompute.py` (канонические строки — `reason_codes.py`).

---

## 3. Anti-regression freeze

Запуск матрицы Phase 7:

```bash
pytest -m wave3_phase7 tests/analysis/math/
```

Полный math-пакет:

```bash
pytest tests/analysis/math/
```

Стартовая валидация Wave 3 (Phase 6):

```bash
pytest -m wave3_integrity tests/analysis/math/test_wave3_phase6_integrity.py
```

---

## 4. Proof-of-usage / completeness — вердикт

- **Каждый зарегистрированный resolver slot** используется хотя бы одной метрикой в `REGISTRY` — проверяется `test_wave7_task036_proof_of_usage.py`.
- **Каждый фактически присутствующий в `REGISTRY` `MetricCoverageClass`** имеет engine path (для текущего реестра: `FULLY_SUPPORTED`, `INTENTIONALLY_SUPPRESSED`).
- **Average-balance метрики** `roa`, `roe`, `asset_turnover` — явный engine path с `eligibility_fragment`.
- Классы **`REPORTED_ONLY` / `DERIVED_FORMULA` / `APPROXIMATE_ONLY` / `OUT_OF_SCOPE`** в **текущем** `REGISTRY` не используются; отдельные unit-тесты покрывают `REPORTED_ONLY` gate (TASK-032). При появлении метрик в реестре — расширить proof-of-usage тест.

---

## 5. Determinism / regression — вердикт

- Детерминизм snapshot по `(validity_state, reason_codes)` на полном выводе `MathEngine.compute` для фиксированных входов.
- Стабильный порядок `build_candidate_set` при перестановке ключей входа.
- Отсутствие `resolve_metric_family` / `RESOLVER_REGISTRY` в `precompute.py` (строковая проверка).
- Отчётливый `invalid` при отсутствии opening для ROA.
- EBITDA reported path: `approximation_semantics` не `True` при reported-only сценарии (через monkeypatch FULLY_SUPPORTED margin).

---

## 6. Wave 3 — **done** для объявленного scope

**Done:** Phases 1–7 по текущему репозиторию: runtime Wave 3, Phase 6 startup, Phase 7 матрица тестов + этот freeze-документ.

**Not done (вне Wave 3 или отложено):** см. раздел 7.

---

## 7. Сознательно остаётся для **Wave 4** (и не входит в Wave 3 freeze)

- Централизованный **reason vocabulary** (`MATH_*` / единый `reason_codes.py`), слияние comparative/period reason drift.
- **Governance** Wave 4 для refusal reason taxonomy и cross-layer policy.
- Расширение **registry** метриками с `REPORTED_ONLY` / `APPROXIMATE_ONLY` / `OUT_OF_SCOPE` — с обновлением proof-of-usage и fingerprint (Phase 6).
- Полный **cross-layer** audit scoring boundary vs math (отдельная волна).
- Доп. **property-based** / огромные numeric корпуса (master-spec billions×billions) — roadmap Wave 5 / отдельные задачи.
