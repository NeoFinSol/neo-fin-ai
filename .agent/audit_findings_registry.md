# Audit Findings Registry

> This file is the detailed handoff for the audit backlog.
> Status values here are the working truth for the next dialog.

## Status Key

- `fixed` — implemented in the current branch
- `pending_verification` — not yet proven locally; do not fix blindly
- `verified_but_deferred` — proven, but intentionally left for later
- `follow_up_fixed` — post-push CI/review tail already closed
- `needs_recheck` — exact claim must be re-read from the synthesis file before coding

## Already Fixed In The Immediate Wave

### `BUG-001` — orphan ORM package with broken imports

- **Status:** `fixed`
- **Outcome:** delete path
- **What happened:** removed unsupported `src/models/database/` instead of repairing it
- **Evidence preserved by:** `tests/test_dead_paths.py`
- **Notes:** `src/db/models.py` is the canonical ORM surface

### `SEC-001` — timing-attack prone API key compare

- **Status:** `fixed`
- **Files touched:** `src/core/auth.py`, `tests/test_core_auth.py`
- **Outcome:** constant-time compare via `hmac.compare_digest` on UTF-8 bytes
- **Important invariant:** exact-match semantics were preserved

### `ARCH-008` — `retry_with_timeout()` retried arbitrary exceptions

- **Status:** `fixed`
- **Files touched:** `src/utils/retry_utils.py`, `tests/test_retry_utils.py`
- **Outcome:** retry narrowed to `asyncio.TimeoutError` only
- **Important invariant:** non-timeout exceptions now fail fast

### `BUG-004` — float-repr artifacts explode fractional masking width

- **Status:** `fixed`
- **Files touched:** `src/utils/masking.py`, `tests/test_masking.py`
- **Outcome:** fractional mask width capped by `MAX_FRACTIONAL_MASK_WIDTH = 4`
- **Important invariant:** integer/sign/zero semantics unchanged

### `SEC-003` — `/system/ready` leaked raw DB exception text

- **Status:** `fixed`
- **Files touched:** `src/routers/system.py`, `tests/test_routers_system*.py`, `docs/API.md`
- **Outcome:** fixed sanitized `503` detail returned to clients
- **Important invariant:** full error detail remains server-side only

### `SEC-004` — committed credential-bearing Alembic URL

- **Status:** `fixed`
- **Files touched:** `alembic.ini`, `tests/test_migrations.py`
- **Outcome:** tracked URL replaced with intentional nonsecret placeholder
- **Important invariant:** runtime migrations still rely on `DATABASE_URL`

### `HC-003` — naive UTC timestamps in system endpoints

- **Status:** `fixed`
- **Files touched:** `src/routers/system.py`, `tests/test_routers_system*.py`, `docs/API.md`
- **Outcome:** shared UTC-aware timestamp helper

## Post-Push Follow-Ups Already Closed

### `CI-001` — workflow mypy target still referenced deleted file

- **Status:** `follow_up_fixed`
- **Files touched:** `.github/workflows/code-quality.yml`, `tests/test_github_workflows.py`
- **Outcome:** canonical target is now `src/db/models.py`

### `CI-002` — non-ASCII API key input raised `TypeError`

- **Status:** `follow_up_fixed`
- **Files touched:** `src/core/auth.py`, `tests/test_core_auth.py`
- **Outcome:** non-ASCII values degrade to mismatch instead of `500`

### `CI-003` — timeout exhaustion looked like AI success

- **Status:** `follow_up_fixed`
- **Files touched:** `src/core/ai_service.py`, `tests/test_core_ai_service.py`
- **Outcome:** timeout exhaustion now records breaker/metrics failure and returns `None`

### `CI-004` — `isort` import-order tail in AI service tests

- **Status:** `follow_up_fixed`
- **Files touched:** `tests/test_core_ai_service.py`
- **Outcome:** import order synced to canonical `isort --profile black` output

## Pending Verification Backlog

> For the findings below, the wording is the working hypothesis from the audit/wave planning.
> Before writing code, re-open `superpowers/audit/2026-04-14-ultra-deep-audit-final-synthesis.md` and verify the exact claim against the current code.

### Wave 2 — Financial Truth

#### `BUG-002` — line `2300` may incorrectly win as `net_profit`

- **Status:** `fixed` (2026-04-14)
- **Files touched:** `src/analysis/extractor/rules.py`, `src/analysis/extractor/legacy_helpers.py`
- **Outcome:** `2300` removed from `net_profit` routing; `2400`-only semantics enforced
- **Evidence preserved by:** targeted regression pack in `tests/test_pdf_extractor.py`, `tests/test_extractor_guardrail_debug.py`, `tests/test_scoring.py`

### Wave 3 — Upload Boundary

#### `BUG-003` — multi-analysis upload boundary weaker than single-upload boundary

- **Status:** `fixed` (2026-04-15)
- **Files touched:** `src/utils/upload_validation.py` (new), `src/routers/multi_analysis.py`, `src/routers/pdf_tasks.py`
- **Outcome:** full validation parity — content-type, magic header, size limit all enforced via shared `save_uploaded_pdf()`
- **Important invariant:** `multi_analysis.py` no longer imports from `pdf_tasks.py`

#### `TEST-004` — missing negative tests for upload validation parity

- **Status:** `fixed` (2026-04-15)
- **Files touched:** `tests/test_multi_analysis_router.py`
- **Outcome:** 10 new tests in `TestMultiAnalysisUploadValidation` — content-type, magic, empty, truncated, size limit, exact-at-limit, cleanup on failure

### Wave 4 — AI Contract

#### `ARCH-003` — duplicate `ConfigurationError` identity

- **Status:** `fixed` (2026-04-15)
- **Files touched:** `src/core/agent.py`, `src/core/base_agent.py`
- **Outcome:** duplicate class removed from `agent.py`; canonical class lives in `base_agent.py`

#### `ARCH-004` — concrete agents raise the wrong error family

- **Status:** `fixed` (2026-04-15)
- **Files touched:** `src/core/gigachat_agent.py`, `src/core/huggingface_agent.py`
- **Outcome:** both agents now raise `ConfigurationError` instead of `ValueError`

#### `ARCH-005` — AI service depends on private configuration state

- **Status:** `fixed` (2026-04-15)
- **Files touched:** `src/core/base_agent.py`, `src/core/ai_service.py`
- **Outcome:** public `is_configured` property added; `ai_service._configure()` uses it

#### `ARCH-007` — AI provider configuration contract is not unified

- **Status:** `fixed` (2026-04-15)
- **Outcome:** all three providers now share the same `ConfigurationError` + `is_configured` contract

#### `TEST-003` — AI contract/regression coverage is incomplete

- **Status:** `fixed` (2026-04-15)
- **Files touched:** `tests/test_wave4_ai_contract.py` (new), `tests/test_core_gigachat_agent.py`, `tests/test_core_ai_service.py`
- **Outcome:** 27 new contract tests; existing tests updated to use `ConfigurationError` and `is_configured`

### Wave 5 — Runtime / Settings / Metadata

#### `SETTINGS-001` — settings fallback path may silently mask invalid config

- **Status:** `pending_verification`
- **Likely source:** `src/models/settings.py`
- **Working claim:** invalid settings may be swallowed into fallback defaults

#### `CONTRACT-001` — `extraction_metadata` may be lost in route projection

- **Status:** `pending_verification`
- **Working claim:** stored metadata exists but does not survive to API payload consumers

#### `HC-002` — Ollama session lifecycle is per-call instead of shared

- **Status:** `pending_verification`
- **Working claim:** session management still needs dedicated runtime verification beyond the CI follow-up path

#### `DOC-006` — docs claim behavior that runtime does not actually have

- **Status:** `pending_verification`
- **Working claim:** docs around Ollama/runtime behavior drift from code truth

### Wave 6 — Layering

#### `ARCH-001` — raw SQL in router layer

- **Status:** `pending_verification`
- **Likely source:** `src/routers/system.py`
- **Working claim:** direct SQL belongs in CRUD/DB boundary, not routers

#### `ARCH-002` — upward dependency pressure in `src/db/database.py`

- **Status:** `pending_verification`
- **Working claim:** DB layer imports upward into core, violating layering direction

### Wave 7 — Math / Comparative

#### `MATH-001` — two sources of truth for comparative reason codes

- **Status:** `pending_verification`
- **Likely files:** `src/analysis/math/comparative_reasons.py`, `periods.py`

#### `MATH-002` — denominator policy gap in math engine

- **Status:** `pending_verification`
- **Likely file:** `src/analysis/math/engine.py`
- **Working claim:** current denominator policy may be too permissive for zero/negative cases

#### `DEAD-003` — `STRICT_AVERAGE_BALANCE_METRICS` may be stale or misleading

- **Status:** `pending_verification`
- **Likely file:** `src/analysis/math/registry.py`

#### `DEAD-004` — `ALL_COMPARATIVE_REASON_CODES` may be dead or unsafely unused

- **Status:** `pending_verification`
- **Likely file:** `src/analysis/math/comparative_reasons.py`

#### `DEAD-006` — EBITDA routing gap / dead path around canonical variants

- **Status:** `pending_verification`
- **Likely file:** `src/analysis/math/precompute.py`

### Wave 8 — Security Backlog

#### `SEC-002` — WebSocket endpoint lacks authentication

- **Status:** `pending_verification`
- **Likely file:** `src/routers/websocket.py`
- **Priority:** highest in this wave

#### `SEC-005` — dev-mode security bypass needs explicit classification

- **Status:** `pending_verification`
- **Working claim:** dev-only behavior may be too permissive or too poorly documented

#### `SEC-006` — `/metrics` exposure must be re-checked

- **Status:** `pending_verification`
- **Working note:** exact scope should be re-read from the audit synthesis before coding

#### `SEC-007` — dev tooling / compose exposure must be classified as risk vs tradeoff

- **Status:** `pending_verification`
- **Working note:** re-check exact audit wording before implementation

#### `SEC-008` — CSP or frontend security policy mismatch

- **Status:** `pending_verification`
- **Working note:** exact files and runtime surface should be re-verified

### Wave 9 — Tests / Docs

#### `TEST-001` — missing circuit breaker lifecycle coverage

- **Status:** `pending_verification`
- **Likely file:** `src/core/circuit_breaker.py`

#### `TEST-002` — extraction pipeline lacks dedicated coverage

- **Status:** `pending_verification`
- **Likely file:** `src/analysis/extractor/pipeline.py`

#### `DOC-001` to `DOC-006` — public docs drift backlog

- **Status:** `pending_verification`
- **Working note:** keep docs work last unless it blocks safety or operator understanding

## Recommended Next Investigation

If resuming the audit immediately, start here:

1. Re-open the synthesis file
2. Re-verify `BUG-002`
3. Produce a narrow verdict note:
   - exact failure mode
   - downstream impact
   - minimal safe fix
   - required regression tests
