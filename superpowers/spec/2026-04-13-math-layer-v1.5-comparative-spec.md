# Math Layer v1.5 Comparative — Spec

## 1. Purpose

`Math Layer v1.5 Comparative` introduces a canonical comparative substrate on top of the existing `Math Layer v1` without expanding the public contract and without exposing new user-visible metrics.

This wave exists for one purpose: move the system from single-period math to a period-aware comparative foundation sufficient to safely enable already existing public metrics that require comparative and average-balance context.

This wave:
- builds an infrastructure layer;
- enables only a narrow set of already existing public metric ids through that layer;
- does not standardize public formula contracts for future comparative metrics;
- is not a public metric exposure wave.

`v1.5` defines only the comparative substrate and the enablement policy for selected existing metrics.  
`v1.5` does not standardize formula contracts or runtime exposure semantics for future comparative metrics.

## 2. Current State

### 2.1 Math Layer
- `Math Layer v1` already exists as a single-period execution foundation.
- `MathEngine` consumes `TypedInputs` and computes single-period derived metrics.
- The safe public subset is limited to metrics that do not require comparative context.
- `ROA`, `ROE`, and `asset_turnover` are not safely enabled via an average-balance substrate.

### 2.2 Multi-period Layer
- The project already has a multi-period orchestration path.
- That path operates on label-level semantics (`period_label`), not on a canonical typed period model.
- Relative period ordering currently depends on parse/sort logic over raw labels.

### 2.3 Scoring Layer
- Scoring already contains separate heuristics for:
  - `period_basis`
  - interim annualization
  - period marker detection
- These rules are ad hoc period logic and do not replace a canonical comparative math substrate.

### 2.4 Architectural Gap
The system currently lacks:
- a canonical typed period entity;
- a period graph with explicit relation types;
- a comparability model;
- opening/closing linkage;
- a canonical average-balance substrate;
- canonical comparative failure semantics.

As a result:
- average-balance metrics cannot be safely enabled;
- future `revenue_growth`, `DSO`, `DIO`, and `DPO` do not have a correct foundation;
- period/comparative semantics risk spreading into `tasks.py`, `scoring.py`, and router code as parallel logic.

## 3. Scope

### 3.1 In Scope
This wave MUST implement:
- a canonical comparative substrate inside `src/analysis/math/`;
- a typed period/comparability model;
- a canonical comparative linkage model;
- a comparative preparation layer before `MathEngine`;
- average-balance enablement for already existing public metric ids:
  - `roa`
  - `roe`
  - `asset_turnover`
- deterministic fail-closed semantics for insufficient comparative context;
- removal of reliance on scoring-only or ad hoc comparative reconstruction for these metrics.

### 3.2 Allowed Optional Scope
The following is allowed but not required for acceptance:
- internal shadow computation for:
  - `revenue_growth`
  - `dso`
  - `dio`
  - `dpo`

These shadow metrics are allowed only for:
- internal tests;
- calibration;
- debug trace;
- future readiness checks.

Internal shadow metrics are permitted but are explicitly non-normative for `v1.5` acceptance. Their absence MUST NOT fail the wave.

### 3.3 Out of Scope
This wave does not include:
- any changes to safe `v1` formulas not directly required by the comparative substrate;
- new public metric ids;
- new API fields;
- any frontend-visible additions;
- a global scoring/confidence redesign;
- a new currency normalization subsystem;
- generalized trend analytics;
- anomaly analytics;
- forecasting;
- public `CCC`.

`CCC` is fully out of scope for this wave, including optional shadow acceptance.

### 3.4 Explicitly Forbidden
The following is forbidden in `v1.5`:
- adding new comparative metrics to the public API;
- expanding the frontend contract with new comparative metric fields;
- making the public scoring/runtime surface depend on new comparative metrics;
- using shadow metrics as a hidden source of influence on public runtime behavior;
- silently falling back from comparative math to single-period math where the metric contract requires comparative or average-balance context.

## 4. Canonical Comparative Model

### 4.1 Canonical Ownership
Comparative semantics MUST have a single canonical source of truth inside `src/analysis/math/`.

Neither `tasks.py`, nor `scoring.py`, nor router code may become a parallel semantic owner of comparative pairing or opening/closing semantics.

Any attempt to reconstruct comparative semantics outside the canonical math layer is considered a specification violation.

### 4.2 Period Entity
The canonical period entity MUST contain at least:
- `period_id`
- `period_class`
- `period_end`
- `fiscal_year`
- `source_period_label`

Where:
- `period_id` is the canonical identifier of the period;
- `period_class` is the canonical enum used in runtime rules;
- `period_end` is the canonical period-end date;
- `fiscal_year` is the normalized fiscal year;
- `source_period_label` is the raw source label preserved only for trace/debug/provenance.

### 4.3 Period Class Vocabulary
`period_class` MUST be a canonical vocabulary, not free text.

Minimum `v1.5` vocabulary:
- `FY`
- `Q1`
- `H1`

The enum MAY predeclare additional values without runtime enablement:
- `Q3`
- `NINE_MONTHS`
- `LTM`

If `Q3`, `NINE_MONTHS`, or `LTM` exist in the vocabulary but are unsupported in this wave, that MUST be expressed through explicit runtime incomparability or unsupported semantics.

### 4.4 Relation Types
The canonical period graph MUST contain at least two distinct relation types:
- `prior_comparable_link`
- `opening_balance_link`

Where:
- `prior_comparable_link` points to a period suitable for comparative delta/growth logic;
- `opening_balance_link` points to a period suitable as the opening state for average-balance metrics.

`prior_comparable_link` and `opening_balance_link` represent distinct semantic relations and MUST NOT be treated as interchangeable.

These links are not interchangeable and MUST NOT be inferred from each other unless explicitly resolved by canonical period rules.

### 4.5 Comparability State
The comparability model MUST support:
- `comparable`
- `partially_comparable`
- `not_comparable`

For metrics that require strict comparative context, `partially_comparable` is treated as insufficient context unless explicitly permitted in a future wave.

Metrics requiring strict comparative context MUST treat `partially_comparable` as insufficient context and fail-closed unless explicitly defined otherwise in future waves.

### 4.6 Comparability Flags
The canonical model MUST support machine-readable flags for at least:
- `missing_prior_period`
- `missing_opening_balance`
- `incompatible_period_class`
- `ambiguous_period_label`
- `inconsistent_units`
- `inconsistent_currency`
- `unsupported_period_class`

If a `period_class` is unsupported by this wave's runtime rules, the system MUST:
- emit `unsupported_period_class`;
- set comparative state to `not_comparable`;
- apply fail-closed semantics for metrics that require comparative context.

Unsupported `period_class` MUST result in `not_comparable` state and trigger fail-closed behavior for metrics requiring comparative context.

`v1.5` does not require inventing a new currency normalization infrastructure; it only requires fail-closed handling when detected inconsistency makes comparative math unsafe.

## 5. Runtime Architecture

### 5.1 Placement
The comparative layer MUST sit logically as:

`raw/multi-period inputs -> canonical period resolution -> comparative linkage -> comparative prepared inputs -> MathEngine -> DerivedMetric`

### 5.2 Comparative Layer Responsibility
The comparative layer MUST:
- normalize raw period identity into a canonical typed model;
- build canonical linkage;
- compute comparability state and flags;
- prepare comparative and average-balance inputs for the engine;
- not compute public scoring;
- not perform router/task orchestration.

### 5.3 Prepared Inputs Contract
Comparative prepared inputs MUST represent fully resolved metric inputs, including:
- explicit opening and closing values where required;
- resolved comparability state;
- absence of unresolved period ambiguity.

`MathEngine` MUST NOT perform additional comparative resolution.

No downstream layer is allowed to mutate comparative prepared inputs.

### 5.4 Engine Boundary
`MathEngine.compute(TypedInputs)` remains the metric execution engine.

The comparative layer prepares inputs and context for metric execution, but MUST NOT turn `engine.py` into a comparative orchestrator.

### 5.5 Boundary With Scoring
Scoring MAY consume comparative outputs and reason signals, but MUST NOT independently resolve comparative pairing or opening/closing semantics.

Scoring and router layers MAY consume comparative outputs but MUST NOT independently reconstruct comparative semantics.

### 5.6 No Fallback To Label Ordering
Raw label ordering MAY be used only as a weak parsing hint and MUST NOT serve as the final source of truth for comparative linkage when canonical period metadata is absent or ambiguous.

### 5.7 Comparative Substrate vs Metric Definitions
`v1.5` defines only the comparative substrate and the enablement policy for selected existing metrics.

`v1.5` does not standardize:
- formula contracts for future comparative metrics;
- public runtime exposure semantics for future comparative metrics;
- downstream product semantics for future comparative metrics.

### 5.8 Linkage Reinterpretation Ban
Comparative linkage MUST be resolved in a metric-agnostic canonical layer, but metric execution MUST NOT reinterpret linkage semantics beyond what is explicitly provided.

This means:
- metric execution consumes already resolved canonical links;
- metric execution cannot decide that a prior comparable period is "good enough" as an opening balance;
- metric-specific reinterpretation of linkage semantics is forbidden.

## 6. Public Behavior Invariants

This wave MUST NOT change:
- the shape of the existing HTTP/API payload;
- frontend interfaces;
- the list of public metric ids;
- the legacy ratio resolution contract;
- the frontend key resolution contract;
- the public scoring surface;
- public metric availability, except for the allowed enablement of already existing `roa`, `roe`, and `asset_turnover`.

Additionally:
- new comparative metrics must not appear in the API;
- new comparative metrics must not appear in the frontend;
- shadow metrics must not influence the observable public runtime surface.

Shadow metrics, if implemented in this wave, MUST remain fully isolated from public runtime behavior and MUST NOT affect public metric availability, scoring, confidence, or suppression decisions in `v1.5`.

Shadow metrics MUST remain behaviorally isolated from the public runtime surface and MUST NOT affect public metric availability, scoring, confidence, or suppression decisions in `v1.5`.

## 7. Failure Semantics

### 7.1 General Rule
When comparative context is insufficient, the system MUST:
- mark the metric as `invalid` or `suppressed`;
- emit a deterministic reason code;
- avoid approximate or public-looking substitute values.

### 7.2 Average-Balance Non-Degradation
For metrics that require average-balance semantics, the system MUST NOT partially degrade to single-period computation when opening/closing linkage is unavailable.

Metrics requiring average-balance semantics MUST NOT degrade to single-period formulas when correct comparative context is unavailable.

### 7.3 Forbidden Recovery Paths
The system MUST NOT:
- infer opening balance from an unrelated prior comparable period;
- backfill missing opening balance from textual heuristics outside canonical comparative rules;
- silently downgrade to a single-period formula if the metric contract requires average balance;
- silently guess comparative linkage from weak label ordering alone.

Metrics whose contract requires comparative or average-balance context MUST NOT silently fall back to single-period math when such context is missing or ambiguous.

### 7.4 Determinism
Failure behavior MUST be:
- deterministic;
- machine-readable;
- traceable in metric trace/reason codes;
- stable across repeated runs on the same inputs.

Given identical inputs, comparative linkage and failure decisions MUST be identical across executions.

## 8. Metric Enablement Policy

### 8.1 Mandatory Runtime Enablement in v1.5
This wave MUST provide comparative/average-balance runtime enablement for the already existing public metric ids:
- `roa`
- `roe`
- `asset_turnover`

For these metrics, the comparative substrate becomes a required part of the runtime contract.

### 8.2 Average-Balance Formula Class
`ROA`, `ROE`, and `asset_turnover` are strict average-balance metrics in this wave.

Average-balance metrics MUST be computed using a two-point balance representation (`opening`, `closing`) and MUST NOT be approximated using single-period ending values.

### 8.3 Optional Shadow-Only Metrics
The system MAY compute:
- `revenue_growth`
- `dso`
- `dio`
- `dpo`

only as non-normative shadow metrics.

Their absence MUST NOT fail the wave.

### 8.4 Forbidden Public Runtime
`v1.5` MUST NOT expose these metrics in the public runtime:
- `revenue_growth`
- `dso`
- `dio`
- `dpo`
- `ccc`

## 9. Acceptance Criteria

### A. Comparative Substrate
- A canonical typed period/comparability model exists inside `src/analysis/math/`.
- The period graph contains at least two distinct relation types:
  - `prior_comparable_link`
  - `opening_balance_link`
- These link types are not interchangeable.

### B. Architectural Ownership
- Comparative semantics have no parallel semantic owners outside the canonical math layer.
- `tasks.py`, `scoring.py`, and router code do not reconstruct comparative semantics independently.

### C. Runtime Behavior
- `roa`, `roe`, and `asset_turnover` are no longer blocked purely because the comparative substrate is missing.
- Their runtime behavior actually depends on the average-balance/comparative foundation.
- When comparative context is insufficient, they fail-closed instead of producing guessed values.
- They do not degrade to single-period formulas.

### D. Public Surface Preservation
- API payload shape remains unchanged.
- Frontend contract remains unchanged.
- No new public metric ids appear.
- No new comparative metrics are publicly exposed.

### E. Shadow Isolation
- Optional shadow metrics, if implemented, do not affect:
  - public metric availability
  - public scoring
  - confidence
  - suppression decisions

## 10. Verification Gates

### 10.1 Mandatory Verification
The mandatory verification gate MUST include:
- unit tests for canonical period normalization;
- tests for `prior_comparable_link`;
- tests for `opening_balance_link`;
- tests proving these link types are distinct;
- tests for comparability flags;
- tests for fail-closed behavior;
- tests proving no single-period fallback for average-balance metrics;
- runtime tests for `roa`, `roe`, and `asset_turnover`;
- backward-compatibility checks for existing API/frontend contracts;
- tests proving the absence of public exposure for new comparative metrics.

### 10.2 Optional Verification
If shadow metrics are implemented:
- their tests are allowed;
- their traces are allowed;
- their calibration checks are allowed;
- but wave acceptance does not depend on their presence.

### 10.3 Evidence Rule
Passing only newly added or changed tests is not sufficient acceptance evidence.

Wave acceptance requires:
- passing the mandatory verification gate;
- no regression evidence on affected observable surfaces;
- confirmation that the public contract has not expanded.

## 11. Review Gates

After implementation, the wave MUST pass 4 review passes.

### 11.1 Spec Compliance
Review must verify:
- the implementation really built the comparative substrate;
- the public contract was not expanded;
- no new public comparative metrics appeared;
- no parallel semantic source was introduced;
- no hidden fallback to label-ordering architecture remains;
- no partial degradation of average-balance metrics occurred.

### 11.2 Test Quality
Review must verify:
- negative paths of comparative pairing are covered;
- fail-closed semantics are covered;
- the absence of silent single-period fallback is tested;
- the distinction between `prior_comparable_link` and `opening_balance_link` is tested;
- there are explicit regression tests for public non-exposure.

### 11.3 SOLID / Architecture Quality
Review must verify:
- canonical ownership of comparative semantics;
- the boundary between the comparative layer and engine;
- the boundary between math and scoring;
- the absence of a second math layer in scoring/tasks;
- the absence of `precompute.py` turning into a generalized comparative engine.

### 11.4 Clean Code / Maintainability
Review must verify:
- no semantic drift in period-class vocabulary and naming;
- no magic fallback rules;
- no excessive coupling between the period resolver, comparative linker, and metric execution;
- no fake decomposition that hides the old architecture under new wrappers.

## 12. Non-Goals

This wave is not intended to:
- publicly show new comparative metrics;
- redesign scoring;
- redesign the UI;
- expose public trend analytics;
- introduce forecasting;
- deliver a product-visible comparative feature rollout.

`v1.5` is intentionally an infrastructure-first and product-silent wave.

## 13. Normative Scope Summary

### Mandatory
- comparative substrate
- typed period/comparability model
- canonical relation model
- average-balance enablement for:
  - `roa`
  - `roe`
  - `asset_turnover`

### Optional
- internal shadow computation for:
  - `revenue_growth`
  - `dso`
  - `dio`
  - `dpo`

### Explicitly Forbidden
- any public exposure of new comparative metrics
