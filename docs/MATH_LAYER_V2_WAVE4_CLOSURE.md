# Math Layer v2 — Wave 4 (outward reason governance) — closure note

**Дата:** 2026-04-20  
**Ветка:** `feat/math-wave3-layer-v2` (совместно с завершением Wave 3 runtime / Phase 6–7).

## Итог волны

- **Единый реестр канонических outward-кодов:** `src/analysis/math/reason_codes.py` (`ALL_REASON_CODES`, `validate_reason_code_registry()`), вызывается из `startup_validation.validate_wave3_contract`.
- **Финальный выбор primary + supporting:** `src/analysis/math/reason_resolution.py`; сборка в `src/analysis/math/engine.py` через `resolve_outward_reasons_for_success` / `resolve_outward_reasons_for_non_success`.
- **Граница emission:** `src/analysis/math/emission_guard.py` + валидатор на `DerivedMetric` (`contracts.py`) — согласование `ValidityState` с outward-полями; `PARTIAL` заблокирован до явного `ALLOW_PARTIAL_OUTWARD_EMISSION`.
- **Trace vs outward:** `src/analysis/math/trace_reason_semantics.py` — снимок `final_outward`, сырьё кандидатов и диагностика разведены по ключам; тесты в `tests/test_reason_trace_consistency.py`.
- **Phase 8 cleanup:** удалён migration shim `resolver_reason_codes.py`; импорты переведены на `reason_codes`; AST-scan legacy `wave3_*` литералов в критичных math-модулях без ложного allowlist.

## Тесты (репозиторий)

После правки `.gitignore` в индекс включены ранее игнорировавшиеся файлы:

- `tests/test_reason_*.py`, `tests/test_comparative_reason_governance.py`
- `tests/analysis/math/test_wave4_engine_reason_governance.py`
- `tests/analysis/math/test_ratio_helper_safety.py` (re-include)

Рекомендуемый локальный прогон перед merge:

```bash
pytest tests/analysis/math/ tests/test_reason_code_usage.py tests/test_reason_state_compatibility.py \
  tests/test_reason_resolution.py tests/test_comparative_reason_governance.py tests/test_reason_trace_consistency.py \
  tests/test_reason_proof_of_usage.py tests/test_reason_codes_registry.py tests/test_math_engine.py
```

## Остаточный долг (не блокирует merge)

См. **`docs/TECH_DEBT_BACKLOG.md`** в репозитории и локальный **`.agent/tech_debt_backlog.md`** (если ведёте агентский backlog у себя): **TD-023–TD-026** — ladder tier 999 для новых кодов, `PARTIAL`, переименование `validate_wave3_contract` / `_WAVE3_*` literal scan, публикация `math_layer_v2_wave4_spec.md`.

## Последующие волны

- Расширение **NORMALIZATION_*** / **SYNTHETIC_*** в `reason_codes` — появление кодов + proof-of-usage + обновление `_PRIORITY_LADDER`.
- Усиление CI (например, явная проверка «каждый `ALL_REASON_CODES` имеет tier в лестнице») — см. TD-025.
