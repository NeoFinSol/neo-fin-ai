# Extractor Confidence Calibration Corpus Contract

## Scope

Этот документ фиксирует corpus/harness contract для prepare-only wave вокруг confidence calibration.

Волна не retune-ит runtime policy. Она делает calibration corpus расширяемым, suite-aware и machine-checkable.

## Execution Tiers

Corpus делится на два execution tier:

- `fast`
- `gated`

Их смысл:

- `fast` — compact deterministic default CI suite;
- `gated` — real-fixture-backed gated/nightly suite.

Ключевой инвариант:

- suite membership determines execution topology, not assertion strictness.

То есть strictness никогда не выводится из `fast/gated` неявно.

## Case Shape

Каждый case обязан иметь:

- `case_id`
- `suite_id`
- `suite_tier`
- `decision_surface`
- `risk_tags`
- `anchor`

Дополнительно, по типу кейса:

- `candidate_threshold`
- `parse`
- `merge`

`case_id` — глобальный идентификатор кейса. Duplicate `case_id` across suites запрещены и валят schema validation.

`suite_id` — имя suite, а не identity конкретного manifest file path.

## Primary Decision Surface

`decision_surface` single-valued и обозначает primary reason the case exists.

Required surfaces:

- `threshold_boundary`
- `winner_selection`
- `merge_replacement`
- `expected_absent`

Expansion-priority surfaces:

- `threshold_survival`
- `authoritative_override`
- `approximation_separation`

Required surfaces machine-gated для этой волны. Expansion-priority surfaces репортятся отдельно, но не блокируют acceptance, пока явно не повышены в статусе.

## Risk Tags

`risk_tags` — secondary traits, не заменяющие `decision_surface`.

Controlled vocabulary в этой волне:

- `historically_flaky`
- `ocr_fragile`
- `low_confidence`
- `source_sensitive`
- `replacement_path`
- `false_positive_trap`
- `boundary_near_0_5`
- `weak_keyword`
- `weak_ocr_direct`

Unknown risk tags запрещены и валят schema validation.

## Anchors

`anchor` intentionally binary в этой волне:

- `true`
- `false`

В этой волне не вводятся:

- `anchor_weight`
- `anchor_strength`
- ranked anchor classes

Anchor нужен как governance marker для high-value cases, а не как отдельная scoring system.

## Source Strictness

Source expectations поддерживают tri-state strictness:

- `unspecified`
- `advisory`
- `critical`

Правила:

- `unspecified` — source expectation отсутствует и не проверяется;
- `advisory` — mismatch репортится, но не валит case;
- `critical` — mismatch валит case.

Это case-local contract, а не suite-level policy.

Explainability в этой волне остаётся observational, кроме source strictness. Runtime `reason_code`, decision log и аналогичные richer explainability assertions в corpus contract не включаются.

## Fixture References

`gated` suite может ссылаться на committed real fixtures через `fixture_ref`.

Fixture resolution contract intentionally minimal:

- `id`
- `filename`
- `sha256`

Calibration layer не должен зависеть от:

- fixture-side semantics labels;
- notes;
- layout tags;
- runner-specific metadata;
- любых неустойчивых вспомогательных полей.

`pipeline_mode` принадлежит calibration case, а не fixture manifest.

## Multi-Metric Parse Cases

`parse` cases могут содержать несколько metric expectations.

Outcome ids нормализуются как:

- `case_id::metric_key`

Determinism contract:

- metric keys canonicalized;
- report ordering stable;
- JSON export stable across runs;
- no hidden dependence on dict insertion order or parse order.

## Coverage Governance

Coverage audit обязан различать:

- missing required surfaces;
- under-anchored required surfaces;
- advisory source mismatches;
- critical source mismatches.

Machine-checkable coverage rules для этой волны:

- required surfaces присутствуют в `fast`;
- required surfaces присутствуют в `all`;
- `gated` содержит real-fixture anchor cases для required surfaces;
- `all` также имеет anchor coverage по required surfaces.

Expansion-priority surfaces отражаются в audit, но не блокируют acceptance.

## Corpus Growth Rule

Новые real-fixture cases добавляются только если они:

- вводят новый decision-risk signal;
- усиливают anchor coverage;
- закрывают наблюдавшийся blind spot.

Добавление кейсов “по инерции” ради объёма противоречит этой волне.

## Harness Contract

Harness CLI:

```powershell
python scripts/run_extractor_confidence_calibration.py --suite fast --format markdown
python scripts/run_extractor_confidence_calibration.py --suite gated --format markdown
python scripts/run_extractor_confidence_calibration.py --suite all --format json
```

Expected report layers:

- aggregate summary;
- per-suite summaries;
- suite-level case diffs;
- threshold sweep;
- invariant checks;
- source mismatch audit;
- coverage audit;
- anchor audit.

## Non-Goals

Эта волна не делает:

- runtime retune;
- public API changes;
- consumer-policy redesign;
- shadow-policy leakage into runtime;
- explainability strictness expansion beyond source tri-state.
