# Tasks — wave8-websocket-auth

## Task List

- [x] 1. Implement auth in `src/routers/websocket.py`
  - [x] 1.1 Replace `import logging` with `from src.utils.logging_config import get_logger` and update `logger = get_logger(__name__)`
  - [x] 1.2 Add `import hmac` to imports
  - [x] 1.3 Add `Query` to the `fastapi` import line
  - [x] 1.4 Add module-level constant `_WS_CLOSE_UNAUTHORIZED: int = 4001` (no magic numbers)
  - [x] 1.5 Implement `_is_ws_auth_valid(api_key: str | None) -> bool` with guard clauses: dev_mode bypass → unconfigured-key bypass → None-key deny → `hmac.compare_digest` → `except (UnicodeEncodeError, AttributeError): return False`
  - [x] 1.6 Add `api_key: str | None = Query(default=None, alias="api_key")` parameter to `websocket_endpoint`
  - [x] 1.7 Add auth guard block at the top of `websocket_endpoint`: call `_is_ws_auth_valid`, log WARNING with task_id and reason (no key value), close with `_WS_CLOSE_UNAUTHORIZED`, return
  - [x] 1.8 Fix `logger.error(f"...")` → `logger.error("...", task_id, exc)` (no f-string, project standard)
  - [x] 1.9 Add `-> None` return type annotation to `websocket_endpoint`
  - [x] 1.10 Verify `isort --profile black` and `black --check` pass on `websocket.py`

- [x] 2. Write unit tests for `_is_ws_auth_valid` in `tests/test_wave8_websocket_auth.py`
  - [x] 2.1 Example: dev_mode=True, key=None → True
  - [x] 2.2 Example: dev_mode=True, key="wrong" → True
  - [x] 2.3 Example: api_key not configured, key=None → True
  - [x] 2.4 Example: api_key not configured, key="anything" → True
  - [x] 2.5 Example: api_key configured, correct key → True
  - [x] 2.6 Example: api_key configured, wrong key → False
  - [x] 2.7 Example: api_key configured, key=None → False
  - [x] 2.8 Example: api_key configured, empty string → False
  - [x] 2.9 Example: api_key configured, non-ASCII key → False (no raise)
  - [x] 2.10 [PBT] P1: dev_mode=True → always True for any api_key (Hypothesis)
  - [x] 2.11 [PBT] P2: api_key not configured → always True for any api_key (Hypothesis)
  - [x] 2.12 [PBT] P3: api_key configured, non-matching → always False (Hypothesis)
  - [x] 2.13 [PBT] P4: result is always bool, never raises for any input (Hypothesis)

- [x] 3. Write integration tests for `websocket_endpoint` in `tests/test_wave8_websocket_auth.py`
  - [x] 3.1 No key + api_key configured → close(4001), ws_manager.connect NOT called
  - [x] 3.2 Wrong key + api_key configured → close(4001), ws_manager.connect NOT called
  - [x] 3.3 Correct key → ws_manager.connect called
  - [x] 3.4 dev_mode=True, no key → ws_manager.connect called
  - [x] 3.5 api_key not configured, no key → ws_manager.connect called
  - [x] 3.6 Rejection logged: logger.warning called with task_id
  - [x] 3.7 No credential leak: log message does NOT contain the api_key value

- [x] 4. SOLID + Clean Code verification pass
  - [x] 4.1 Verify `_is_ws_auth_valid` ≤ 15 lines
  - [x] 4.2 Verify guard clauses used (no nested ifs)
  - [x] 4.3 Verify `_WS_CLOSE_UNAUTHORIZED` constant used (no magic number 4001 inline)
  - [x] 4.4 Verify no f-strings in logger calls
  - [x] 4.5 Verify no api_key value appears in any log message
  - [x] 4.6 Verify `_is_ws_auth_valid` has no side effects (no logging, no I/O)
  - [x] 4.7 Verify `websocket_endpoint` delegates auth decision to `_is_ws_auth_valid` (SRP)

- [x] 5. Update audit findings registry
  - [x] 5.1 Mark `SEC-002` as `fixed` in `.agent/audit_findings_registry.md`
  - [x] 5.2 Update `.agent/overview.md` with Wave 8 status
  - [x] 5.3 Add entry to `.agent/PROJECT_LOG.md`
