# Audit Wave Execution Board

> Read this file first when starting a new dialog about the audit backlog.
> Read `.agent/audit_findings_registry.md` second for per-finding detail.

## Snapshot

- **Date:** 2026-04-15
- **Working branch:** `codex/solid-clean-code-2026-04-15`
- **Latest relevant commits:** see PROJECT_LOG.md
- **Primary source audit:** `superpowers/audit/2026-04-14-ultra-deep-audit-final-synthesis.md`
- **Current state:** Wave 1A/1B, 2A/2B, 3A/3B implemented. SOLID/Clean Code remediation pack complete. Wave 4A onwards pending.

## How To Work The Audit

### Core execution rule
Each wave goes in this order:

1. `Verification`
2. `Triage checkpoint`
3. only then either:
   - `Immediate remediation`
   - `Confirmed but defer`
   - `Fold into larger future pack`

### Allowed verdicts

- `confirmed`
- `partially_confirmed`
- `false_positive`
- `stale_but_harmless`
- `real_but_rescope`
- `confirmed_but_defer`

### Global stop rules

Stop the current wave and re-plan if any of these becomes true:

- the finding depends on a larger schema/domain change
- the fix would cross wave boundaries and expand scope
- the safe boundary is no longer clear
- a supposedly dead/orphan path suddenly has a live consumer
- the work touches the math source-of-truth layer without a dedicated math verification pass

## Already Completed

### Wave 1A / 1B — Quick Wins + Immediate Hardening

- **Status:** implemented
- **Findings:** `BUG-001`, `SEC-001`, `ARCH-008`, `BUG-004`, `SEC-003`, `SEC-004`, `HC-003`
- **What landed:**
  - orphan `src/models/database/` boundary deleted
  - API key compare hardened
  - readiness error sanitized
  - health timestamps moved to UTC-aware helper
  - retry narrowed to timeout-only
  - float masking bounded
  - Alembic tracked URL replaced with nonsecret placeholder
- **Post-push follow-ups also landed:**
  - mypy workflow target moved to `src/db/models.py`
  - non-ASCII API key mismatch no longer raises `TypeError`
  - timeout exhaustion now records failure, not false success
  - `isort` import-order tail fixed in `tests/test_core_ai_service.py`

### Verification slices that were green locally

- `python -m pytest tests/test_core_auth.py tests/test_routers_system.py tests/test_routers_system_full.py -q`
- `python -m pytest tests/test_retry_utils.py tests/test_masking.py tests/test_migrations.py tests/test_core_ai_service.py -q`
- `python -m pytest tests/test_dead_paths.py tests/test_migrations.py -q`
- `python -m pytest tests/test_core_auth.py tests/test_core_ai_service.py tests/test_routers_system.py tests/test_routers_system_full.py tests/test_github_workflows.py -q`
- `python -m isort --profile black --check-only src tests`
- local CI-equivalent mypy slice for `src/db/models.py`

## Waves Still Pending

### Wave 2A / 2B — Financial Truth

- **Status:** implemented (2026-04-14)
- **Primary finding:** `BUG-002`
- **What landed:** `2300` removed from `net_profit` routing; `2400`-only semantics; targeted regression pack green.

### Wave 3A / 3B — Upload Boundary Hardening

- **Status:** implemented (2026-04-15)
- **Findings:** `BUG-003`, `TEST-004`
- **What landed:**
  - created `src/utils/upload_validation.py` — shared content-type, magic-header, size-limit validation
  - `multi_analysis.py` now uses `save_uploaded_pdf()` — full parity with single-upload
  - 10 new tests in `TestMultiAnalysisUploadValidation` covering all three defects + cleanup
  - `multi_analysis.py` no longer imports from `pdf_tasks.py` (DIP fix bundled)

### Wave 4A / 4B — AI Contract Repair

- **Status:** implemented (2026-04-15)
- **Findings:** `ARCH-003`, `ARCH-004`, `ARCH-005`, `ARCH-007`, `TEST-003`
- **What landed:**
  - duplicate `ConfigurationError` in `agent.py` removed — imported from `base_agent`
  - `GigaChatAgent` and `HuggingFaceAgent` now raise `ConfigurationError` instead of `ValueError`
  - public `is_configured` property added to `BaseAIAgent`
  - `ai_service._configure()` uses `is_configured` instead of `._configured`
  - `tests/test_wave4_ai_contract.py` — 27 regression tests on unified error hierarchy and public contract

### Wave 5A / 5B — Runtime / Settings / Metadata Reliability

- **Status:** implemented (2026-04-15/16)
- **Findings:** `SETTINGS-001`, `HC-002`; `CONTRACT-001` deferred; `DOC-006` deferred
- **What landed:**
  - `ai_timeout`, `ai_retry_count`, `ai_retry_backoff` validators added to `AppSettings`
  - `OllamaAgent` singleton uses `app_settings.ai_timeout` for session timeout
  - stale `self.model` attribute removed from `OllamaAgent.__init__`
  - `get_logger` replaces `logging.getLogger` in `ollama_agent.py`

### Wave 6A / 6B — Layering Cleanup

- **Status:** implemented (2026-04-16)
- **Findings:** `ARCH-001`, `ARCH-002`
- **What landed:**
  - `check_database_connectivity() -> bool` added to `src/db/crud.py`
  - `src/routers/system.py` no longer imports `sqlalchemy.text` or `get_engine`
  - `DatabaseConfig` frozen dataclass added to `src/db/database.py`
  - `get_engine(config: DatabaseConfig | None = None)` — decoupled from global `app_settings`
  - `tests/test_wave6_layering_cleanup.py` — 20 tests including 2 PBT suites

### Wave 7A / 7B — Math / Comparative Coherence

- **Status:** pending
- **Findings:** `MATH-001`, `MATH-002`, `DEAD-003`, `DEAD-004`, `DEAD-006`
- **Goal:** separate real math issues from dangerous false-positive dead-code cleanup
- **Special caution:** do not casually delete anything in comparative/math until ownership and source-of-truth are explicit

### Wave 8A / 8B — Security Backlog

- **Status:** pending
- **Findings:** `SEC-002`, `SEC-005`, `SEC-006`, `SEC-007`, `SEC-008`
- **Goal:** split real prod-facing risk from intentional dev-only tradeoffs
- **Likely first priority:** WebSocket authentication

### Wave 9A / 9B — Tests / Docs

- **Status:** pending
- **Findings:** `TEST-001`, `TEST-002`, `TEST-003`, `DOC-001`, `DOC-002`, `DOC-003`, `DOC-004`, `DOC-005`, `DOC-006`
- **Goal:** treat tests and docs as follow-up stabilization after code truth is settled
- **Rule:** docs follow code; docs-only cleanup does not mix with correctness/security waves

## Recommended Next Move

Start with **Wave 5A — Runtime / Settings / Metadata Reliability**.

## Strong Parts That Must Be Preserved

Do not casually disturb these while working the remaining audit:

- `src/analysis/math/` foundation
- `src/analysis/extractor/decision_trace.py`
- extractor staged pipeline contract
- calibration harness and corpus contracts
- canonical metric registry
- comparative math v1.5 work
- upload boundary decomposition in `src/routers/pdf_tasks.py`
- CI workflow regression tests

## Suggested New-Dialog Start Prompt

If a new chat needs to continue the audit, start from:

1. `.agent/audit_wave_execution_board.md`
2. `.agent/audit_findings_registry.md`
3. `superpowers/audit/2026-04-14-ultra-deep-audit-final-synthesis.md`

Then proceed directly into `Wave 2A — BUG-002 verification`.
