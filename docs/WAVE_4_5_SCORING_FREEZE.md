# Wave 4.5 Scoring Freeze Handoff

Derived from typed registries.

## Purpose of Freeze
- Convert current observed scoring-boundary behavior into executable baseline before Wave 5 decomposition.
- Preserve boundary behavior without production semantic rewrites in Wave 4.5.

## Frozen Domains
- Annualization boundary behavior.
- Guardrail and regression-prone boundary behavior.
- Payload structure and typing behavior represented by typed matrix rules.

## Hard-frozen Behaviors
- Canonical baseline case outcomes listed below.
- Blocker leakage exclusion (BUG_TO_FIX cases excluded from canonical baseline).
- Machine-field contracts exercised by freeze suites.

## Soft-frozen Behaviors
- Presentation-adjacent text/description details where not machine-consumed.
- Empty optional sections behavior where classified as preserved temporary bug.

## Informational Details
- Handoff is derived from typed registries; markdown is a view, not source of truth.
- References: `docs/scoring_freeze_payload_matrix.md`, `docs/scoring_freeze_classification.md`.

## Known Preserved Quirks
- `freeze-case-empty-factors-preserved-quirk`

## Known Label-coupled Behavior
- `freeze-case-ru-label-semantic-coupling`: Core scoring data binding currently depends on RU-labeled ratio keys in weights and benchmarks.

## Known Helper-influenced Boundary Behavior
- `freeze-case-anomaly-helper-boundary-impact`: Helper-level anomaly filtering excludes ratio values by returning None before weighted scoring.

## Canonical Cases
- `freeze-case-anomaly-helper-boundary-impact` (guardrails)
- `freeze-case-empty-factors-preserved-quirk` (payload)
- `freeze-case-period-marker-annualization` (annualization)

## Blocker Cases Excluded from Canonical Baseline
- `freeze-case-ru-label-semantic-coupling`

## Wave 5 Constraints
- Wave 5 must preserve frozen scoring-boundary behavior captured by canonical freeze suites.
- Must-fix blockers cannot be treated as accepted behavior without explicit resolution.
- Any semantic changes require explicit, versioned decision outside freeze-preservation claims.

## Equivalence Validation Method
- Run mandatory freeze suites and require green status.
- Verify blocker separation and canonical case linkage invariants.
- Verify docs sync from renderers to committed docs (drift fails tests).

## References
- Payload matrix: `docs/scoring_freeze_payload_matrix.md`
- Classification log: `docs/scoring_freeze_classification.md`

## Mandatory Gates
- canonical freeze case registry complete: PASS
- blocker cases separated: PASS
- annualization golden suite green: PASS
- guardrails golden/regression suites green: PASS
- payload matrix complete: FAIL
- payload structural tests green: PASS
- invariant suite green: PASS
- docs sync green: PASS
- handoff docs complete: PASS
- payload matrix missing classes: full_success, invalid_or_suppressed_factor, refused_payload, with_exclusions

## Wave 5 Unblock Status: BLOCKED
- Wave 5 is marked unblocked only when all mandatory gates pass.
