# Extractor Confidence Calibration

## Контекст

Extractor confidence живёт в двух уже разделённых слоях:

- runtime calibration policy;
- offline calibration corpus and harness.

Runtime calibration policy была landed в предыдущей волне как `Internal-First+`:

- public V2 wire shape не меняется;
- frontend contract не меняется;
- default `CONFIDENCE_THRESHOLD=0.5` не меняется;
- меняется только extractor-side runtime confidence math.

Текущая hardening wave поверх этого runtime не retune-ит policy заново. Она делает corpus/harness слой более устойчивым и управляемым:

- suite-aware corpus layout;
- real-fixture-backed gated tier;
- explicit source strictness tri-state;
- machine-checkable coverage audit;
- stricter isolation между execution tier и assertion strictness.

## Runtime Policy

В runtime единым source of truth остаётся declarative-first policy layer в [confidence_policy.py](/E:/neo-fin-ai/src/analysis/extractor/confidence_policy.py).

Policy по-прежнему централизует:

- profile baselines;
- quality bands;
- structural bonus;
- guardrail penalty;
- conflict penalty;
- strong direct threshold.

Итоговый landed runtime policy остаётся:

- `RUNTIME_CONFIDENCE_POLICY = CALIBRATED_RUNTIME_CONFIDENCE_POLICY`

Текущая corpus hardening wave этот выбор не меняет.

## Corpus Hardening Wave

Новая волна переводит calibration corpus из single-manifest shape в suite-aware contract под [tests/data/extractor_confidence_calibration](/E:/neo-fin-ai/tests/data/extractor_confidence_calibration):

- [fast.json](/E:/neo-fin-ai/tests/data/extractor_confidence_calibration/fast.json)
- [gated.json](/E:/neo-fin-ai/tests/data/extractor_confidence_calibration/gated.json)

Execution topology теперь tiered:

- `fast` — compact deterministic suite для default CI;
- `gated` — real-fixture-backed suite для gated/nightly runs.

Важный инвариант:

- suite membership определяет только execution topology;
- assertion strictness определяется на уровне конкретного case/expectation.

То есть:

- `fast` case может быть source-critical;
- `gated` case может быть outcome-only;
- strictness не выводится автоматически из suite tier.

## Case Contract

Каждый calibration case теперь несёт явный suite-aware contract:

- `case_id`
- `suite_id`
- `suite_tier`
- `decision_surface`
- `risk_tags`
- `anchor`

`anchor` intentionally остаётся бинарным в этой волне:

- без `anchor_weight`;
- без `anchor_strength`;
- без ranked anchor model.

Primary `decision_surface` single-valued и фиксирует, ради какой load-bearing surface кейс вообще существует.

Machine-required surfaces для этой волны:

- `threshold_boundary`
- `winner_selection`
- `merge_replacement`
- `expected_absent`

Expansion-priority surfaces пока только репортятся и используются для роста corpus:

- `threshold_survival`
- `authoritative_override`
- `approximation_separation`

Weak OCR / weak keyword paths остаются вторичными risk patterns через controlled `risk_tags`, а не отдельными primary surfaces.

## Source Strictness

Source expectations formalized как tri-state:

- `unspecified`
- `advisory`
- `critical`

Смысл:

- `unspecified` — source expectation отсутствует и не проверяется;
- `advisory` — mismatch попадает в report, но не валит case;
- `critical` — mismatch валит case.

Explainability в этой волне остаётся observational, кроме явно объявленного source strictness. Никакие `reason_code`, decision log или richer explainability assertions в gating contract не добавляются.

## Real Fixture References

Gated corpus использует `fixture_ref` на [manifest.json](/E:/neo-fin-ai/tests/data/pdf_real_fixtures/manifest.json), но calibration layer зависит только от минимального fixture contract:

- `id`
- `filename`
- `sha256`

Calibration layer сознательно **не** зависит от:

- fixture-side expected values;
- fixture-side expected sources;
- notes/layout tags;
- test-runner metadata;
- любых нестабильных вспомогательных полей.

`pipeline_mode` живёт в calibration case, а не в fixture manifest.

## Harness

Offline harness lives in:

- [calibration.py](/E:/neo-fin-ai/src/analysis/extractor/calibration.py)
- [run_extractor_confidence_calibration.py](/E:/neo-fin-ai/scripts/run_extractor_confidence_calibration.py)

CLI теперь suite-aware:

```powershell
python scripts/run_extractor_confidence_calibration.py --suite fast --format markdown
python scripts/run_extractor_confidence_calibration.py --suite gated --format markdown
python scripts/run_extractor_confidence_calibration.py --suite all --format json
```

`fast` остаётся default suite для локального и CI smoke path.

Harness output включает:

- aggregate summary;
- per-suite summaries;
- suite-level diffs;
- threshold sweep;
- trust-order invariant checks;
- source mismatch audit;
- coverage audit с required surfaces и anchor coverage.

## Evidence

Checked-in evidence pack теперь строится на `--suite all` и отражает suite-aware corpus:

- Human-readable evidence pack: [EXTRACTOR_CONFIDENCE_CALIBRATION_EVIDENCE.md](/E:/neo-fin-ai/docs/EXTRACTOR_CONFIDENCE_CALIBRATION_EVIDENCE.md)
- Machine-readable evidence pack: [EXTRACTOR_CONFIDENCE_CALIBRATION_EVIDENCE.json](/E:/neo-fin-ai/docs/EXTRACTOR_CONFIDENCE_CALIBRATION_EVIDENCE.json)

Отдельный corpus/harness contract зафиксирован в [EXTRACTOR_CONFIDENCE_CALIBRATION_CORPUS.md](/E:/neo-fin-ai/docs/EXTRACTOR_CONFIDENCE_CALIBRATION_CORPUS.md).

## Что сознательно НЕ менялось

- runtime confidence policy;
- public extractor metadata contract;
- frontend explainability rendering;
- consumer-policy redesign;
- shadow policy isolation rules.

Shadow consumer semantics остаются strictly offline-only:

- не импортируются в production decision path;
- не влияют на persisted outputs;
- используются только в harness/reports и future design exploration.
