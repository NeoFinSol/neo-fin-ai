# Math Layer v1.5 Comparative — Design

## 1. Design Goal

`v1.5 Comparative` adds a canonical comparative lane to `Math Layer` that can:
- normalize period semantics;
- build canonical comparative links;
- prepare period-scoped comparative inputs;
- pass them into the existing `MathEngine`;
- enable existing public metrics `roa`, `roe`, and `asset_turnover` without expanding the public contract.

The design intentionally does not build a new public product surface and does not turn the comparative foundation into a chain of ad hoc helpers spread across `tasks.py`, `scoring.py`, and adapters.

## 2. Core Architectural Decision

### 2.1 Single Comparative Entrypoint

Inside `src/analysis/math/`, there MUST be a single math-owned orchestration entrypoint for period-set comparative processing.

Conceptually:
- `run_comparative_math(...)`
- or `compute_metrics_for_period_set(...)`

The exact name can be chosen in the implementation plan, but the semantics are fixed:
- the entrypoint accepts a period set;
- it internally calls canonical comparative internals;
- it returns already computed per-period math outputs.

### 2.2 Tasks Boundary

`tasks.py` may orchestrate only phase boundaries:
- extraction phase;
- handoff into the comparative math lane;
- scoring consumption.

`tasks.py` MUST NOT orchestrate comparative semantics internals step by step.

It is forbidden for `tasks.py` to manually call, piece by piece:
- the period resolver;
- the linker;
- the comparative input preparer;
- the engine;
- the status policy path.

Normative rule:
- `tasks.py may orchestrate phase boundaries, but MUST NOT orchestrate internal comparative semantics step-by-step.`

## 3. Target Runtime Architecture

Target flow:

`raw period inputs -> raw period parsing -> canonical period resolution -> canonical linkage resolution -> comparative prepared inputs -> MathEngine -> DerivedMetric -> projections -> scoring consumers`

### 3.1 Phase Ownership

- `raw period parsing` extracts signal from raw labels.
- `canonical period resolution` builds typed canonical period entities.
- `canonical linkage resolution` builds semantic links.
- `comparative prepared inputs` builds fully resolved per-period input bags.
- `MathEngine` handles metric execution only.
- `projections` preserve the unchanged public contract.
- `scoring` only consumes outputs and reason signals.

### 3.2 No Downstream Semantic Reconstruction

No downstream layer may:
- reconstruct comparative semantics;
- recalculate links;
- replace canonical linkage with its own heuristics.

## 4. Module Design

### 4.1 New Modules

#### `src/analysis/math/periods.py`

Home of period vocabulary and typed period entities.

Contains:
- `PeriodClass`
- `ComparabilityState`
- `ComparabilityFlag`
- raw parse result type
- canonical period entity type

#### `src/analysis/math/comparative.py`

Home of the canonical comparative lane.

Contains:
- the math-owned comparative entrypoint;
- canonical linkage resolution;
- comparability evaluation;
- comparative prepared input construction;
- centralized status ownership for comparative-enabled metrics.

#### `src/analysis/math/comparative_reasons.py`

Home of the canonical reason vocabulary for comparative semantics.

Reasons for a dedicated module:
- reason codes participate in failure determinism;
- reason codes participate in traceability;
- reason codes participate in testability;
- reason vocabulary must not drift across `comparative.py`, `periods.py`, `engine.py`, and tests.

If the eventual vocabulary is tiny, co-location is technically allowed, but the design default is a separate module.

### 4.2 Existing Modules

#### [contracts.py](E:/neo-fin-ai/src/analysis/math/contracts.py)

Remains home for:
- `MetricInputRef`
- `MetricComputationResult`
- `DerivedMetric`

It must not become the home of period graph logic.

#### [registry.py](E:/neo-fin-ai/src/analysis/math/registry.py)

Remains the canonical registry for metric definitions.

It should contain runtime-enabled definitions for:
- `roa`
- `roe`
- `asset_turnover`

The registry only declares:
- required prepared keys;
- denominator policy;
- averaging requirement semantics.

The registry does not resolve comparative context.

#### [engine.py](E:/neo-fin-ai/src/analysis/math/engine.py)

Its boundary stays unchanged:
- `compute(TypedInputs) -> dict[str, DerivedMetric]`

The engine:
- does not parse period labels;
- does not build links;
- does not interpret `partially_comparable`;
- does not select opening balance;
- does not decide comparative incomparability.

#### [precompute.py](E:/neo-fin-ai/src/analysis/math/precompute.py)

Remains a narrow single-period precompute layer.

Comparative preparation must not be moved here.

This is a hard design boundary so that `precompute.py` does not turn into a second engine.

#### [projections.py](E:/neo-fin-ai/src/analysis/math/projections.py)

The projection layer remains responsible for preserving the unchanged public contract.

Comparative internals may enrich internal trace, but:
- the projection layer must not invent comparative semantics;
- the projection layer must not reconstruct comparative semantics;
- the projection layer only exposes allowed outputs.

## 5. Data Model Design

### 5.1 Raw Parse Result vs Canonical Period Entity

These are two distinct entities and must not collapse into one.

#### A. Raw Period Parse Result

Purpose:
- reflect the result of parsing a raw `period_label`;
- retain ambiguity and debug information.

It should contain roughly:
- raw label;
- parse status;
- parse ambiguity flags;
- candidate period class/year/end if parsing succeeded only partially.

This is not a canonical business object.

#### B. Canonical Period Entity

Purpose:
- serve as the single canonical runtime representation of a period.

It should contain:
- `period_id`
- `period_class`
- `period_end`
- `fiscal_year`
- `source_period_label`

This is the canonical comparative object.

Normative rule:
- `Canonical period entity is separated from raw period-label parse result.`

### 5.2 Immutability

`PeriodRef` and linkage structures should be immutable or treated-as-immutable value objects.

Why:
- the resolver should not silently mutate period identity;
- the linker should not rewrite the canonical period entity;
- the preparer should not mutate linkage post factum;
- deterministic reasoning and tests become much easier.

Design recommendation:
- `PeriodRef and comparative linkage structures should be immutable or treated as immutable value objects.`

### 5.3 Comparability State

Vocabulary:
- `comparable`
- `partially_comparable`
- `not_comparable`

In `v1.5`:
- `partially_comparable` is a semantic state;
- `partially_comparable` is useful for trace, debug, and calibration;
- `partially_comparable` is operationally non-permissive for strict metrics.

This means:
- future-ready vocabulary;
- almost no permissive runtime role in `v1.5`.

## 6. Linkage Design

### 6.1 Link Types

The period graph must contain at minimum:
- `prior_comparable_link`
- `opening_balance_link`

#### `prior_comparable_link`

Used for:
- comparative delta logic;
- future growth metrics.

#### `opening_balance_link`

Used for:
- average-balance metrics.

These relation types are:
- semantically distinct;
- not interchangeable;
- not derivable from each other without explicit canonical rules.

### 6.2 Cross-Metric Reuse Ban

Comparative linkage is resolved in a metric-agnostic canonical layer.

But metric execution:
- may not reinterpret linkage semantics;
- may not reuse linkage at its own discretion;
- may not apply “linkage for growth” as an “opening balance candidate.”

Normative rule:
- `Comparative linkage MUST be resolved in a metric-agnostic canonical layer, but metric execution MUST NOT reinterpret linkage semantics beyond what is explicitly provided.`

## 7. Comparative Prepared Inputs Design

### 7.1 Scope of Prepared Inputs

Comparative prepared inputs must be period-scoped, not bespoke per metric.

That means:
- the substrate prepares one common prepared input set per period;
- metric definitions read the keys they need from it;
- the substrate does not become a custom preparer separately for `ROA`, `ROE`, and `asset_turnover`.

Normative rule:
- `comparative prepared inputs are period-scoped, with metric definitions consuming required prepared keys.`

### 7.2 Content of Prepared Inputs

The comparative prepared input bag must contain:
- base reported inputs for the period;
- explicit opening values where required;
- explicit closing values where required;
- derived average values where required;
- resolved comparability state;
- no unresolved period ambiguity.

### 7.3 Naming Convention

Prepared comparative inputs must use a single canonical naming pattern:

- `opening_<base_metric_key>`
- `closing_<base_metric_key>`
- `average_<base_metric_key>`

Examples:
- `opening_total_assets`
- `closing_total_assets`
- `average_total_assets`
- `opening_equity`
- `closing_equity`
- `average_equity`

Ad hoc aliases in the runtime path are forbidden.

## 8. Comparative Lane Entry Point

### 8.1 Single Entry Point Contract

The math layer must provide one coherent entrypoint for period-set comparative processing.

This entrypoint:
- accepts a set of period results or extracted metrics;
- internally performs parse -> resolve -> link -> prepare -> engine;
- returns per-period derived metric outputs and comparative-aware trace/status decisions.

### 8.2 Why This Matters

This is needed so that:
- `tasks.py` does not become the hidden owner of comparative semantics;
- comparative internals do not split into five manual calls;
- review can verify one-lane canonical ownership.

## 9. Metric Enablement Design

### 9.1 Strict Metrics in v1.5

The public-existing metrics runtime-enabled in this wave are:
- `roa`
- `roe`
- `asset_turnover`

They are strict average-balance metrics.

### 9.2 Formula Class

For these metrics, the design fixes a class-of-formula contract rather than a full formula standardization:

- computation uses a two-point balance representation;
- it uses `opening` and `closing`;
- it uses a derived average from them;
- it does not use a single-period ending balance approximation.

### 9.3 Registry Responsibility

The registry should only:
- declare required prepared keys;
- declare average-balance requirement semantics;
- use canonical prepared inputs.

The registry must not:
- search for opening values;
- construct averages;
- resolve incomplete linkage.

## 10. Shadow Metrics Design

Optional shadow metrics, if implemented:
- `revenue_growth`
- `dso`
- `dio`
- `dpo`

They:
- must be computed inside the canonical comparative lane;
- must not create parallel calculation paths;
- must not live partly in scoring, partly in adapters, or partly in trace builders.

Normative rule:
- `optional shadow metrics, if implemented, MUST be computed within the canonical comparative lane and MUST NOT introduce parallel calculation paths.`

Additionally, they:
- do not appear in public projections;
- do not appear in the frontend contract;
- do not participate in public scoring;
- do not affect availability, confidence, or suppression of public metrics.

## 11. Status Ownership: invalid vs suppressed

The `invalid` vs `suppressed` distinction remains useful, but ownership must be centralized.

The correct owner:
- the canonical comparative lane or math-layer policy path.

Incorrect owners:
- scoring;
- frontend adapters;
- router layer.

Operational distinction:
- `invalid` means the metric is formally supported, but insufficient comparative context prevents computation;
- `suppressed` means the metric is blocked by wave-level or registry-level policy.

This decision must be made inside the math-owned comparative lane, not by downstream consumers.

## 12. Single-Period Integration Behavior

The single-period path is not required to pass through the comparative lane.

This matters.

In `v1.5`, it is forbidden to build a hidden synthetic one-period comparative wrapper just for “architectural unification.”

Rule:
- the single-period execution path remains separate;
- if a strict metric requires comparative context, single-period execution stays fail-closed;
- no synthetic one-period comparative emulation is introduced in this wave.

Normative rule:
- `Single-period execution path remains separate; strict comparative metrics stay fail-closed without synthetic comparative emulation.`

## 13. Projection Boundary

Comparative internals may enrich internal trace, but:
- the projection layer remains responsible for preserving the unchanged public contract;
- the projection layer must not invent comparative semantics;
- the projection layer must not reconstruct comparative semantics;
- the projection layer only exposes allowed outputs.

## 14. Design Decisions

### DD-1

Comparative lane has a single math-owned entrypoint for period-set processing.

### DD-2

Tasks orchestrate phase boundaries, but do not manually orchestrate comparative semantics internals.

### DD-3

Canonical period entity is separated from raw period-label parse result.

### DD-4

Comparative prepared inputs are period-scoped, not bespoke per metric.

### DD-5

Prepared comparative inputs follow canonical naming conventions for opening, closing, and average derived keys.

### DD-6

Optional shadow metrics, if implemented, stay inside the canonical comparative lane.

### DD-7

`invalid` vs `suppressed` decision ownership is centralized and not delegated to scoring.

### DD-8

Single-period execution path remains separate; strict comparative metrics stay fail-closed without synthetic comparative emulation.

## 15. Design Risks

Main implementation risks:
- `tasks.py` becomes the comparative orchestrator-owner;
- `scoring.py` starts reconstructing period semantics;
- `precompute.py` turns into a comparative engine;
- linkage semantics drift between growth and average-balance use cases;
- optional shadow metrics create a hidden parallel runtime path;
- permissive interpretation of `partially_comparable` turns strict metrics into a gray zone.

This design is specifically intended to suppress those risks.

## 16. Implementation Notes

### IN-1 `periods.py` must stay narrow

`periods.py` is acceptable as the home for:
- canonical vocabularies;
- raw parse result types;
- canonical period value objects.

`periods.py` must not become the home of heavy resolution logic, linkage rules, or runtime orchestration.

### IN-2 `comparative.py` must not become a god-module

`comparative.py` is the home of the canonical comparative lane, but in implementation it must be logically decomposed into at least four internal areas:
- parse/normalize handoff;
- linkage resolution;
- prepared input construction;
- status/failure decision path.

This can be achieved either by:
- several helper functions inside the file;
- or adjacent split modules if the density grows too much.

### IN-3 `comparative_reasons.py` needs an initial fixed vocabulary

The implementation plan should immediately fix the initial reason-code set to prevent drift in the first commit.

Recommended initial vocabulary:
- `ambiguous_period_label`
- `unsupported_period_class`
- `missing_prior_period`
- `missing_opening_balance`
- `incompatible_period_class`
- `partially_comparable_context`
- `inconsistent_units`
- `inconsistent_currency`
- `average_balance_context_missing`

The last one is especially useful as an umbrella reason for strict average-balance metrics.

## 17. Recommended Implementation Direction

Recommended `v1.5` implementation:
- add a new canonical comparative lane in `src/analysis/math/`;
- refactor the multi-period path into extract-first / comparative-second / score-third flow;
- do minimal registry enablement only for `roa`, `roe`, and `asset_turnover`;
- add optional shadow metrics only if they naturally follow from the already built substrate.

Hard boundaries:
- do not over-touch the single-period path beyond compatibility needs;
- do not teach scoring to perform period pairing;
- do not change the public contract at all.
