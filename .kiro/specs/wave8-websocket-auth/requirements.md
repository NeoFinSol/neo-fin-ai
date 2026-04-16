# Requirements Document — wave8-websocket-auth

## Introduction

**Finding:** SEC-002 (Wave 8 Security Backlog)

The WebSocket endpoint `/ws/{task_id}` currently accepts connections from any client without
authentication. All other HTTP endpoints in NeoFin AI require an API key via the
`X-API-Key` header. This creates an inconsistent security boundary: an attacker who knows
a valid `task_id` can subscribe to real-time status updates for any analysis task without
credentials.

This feature closes the gap by adding equivalent authentication to the WebSocket handshake
using a query parameter (`?api_key=...`), which is the only mechanism available to
browser-native WebSocket clients (`new WebSocket(url)` cannot set custom headers).

**Scope:** single-file change to `src/routers/websocket.py`. No schema changes, no new
modules, no API contract changes for authenticated callers.

---

## Glossary

| Term | Definition |
|------|-----------|
| **WebSocket_Endpoint** | FastAPI route handler at `src/routers/websocket.py` serving `/ws/{task_id}` |
| **Auth_Guard** | Private helper `_is_ws_auth_valid(api_key: str | None) -> bool` in `websocket.py` |
| **WS_Manager** | `ConnectionManager` singleton (`ws_manager`) in `src/core/ws_manager.py` tracking active connections |
| **App_Settings** | `app_settings` singleton from `src/models/settings.py` providing `dev_mode` and `api_key` |
| **Close_Code_4001** | WebSocket application-level close code meaning "Unauthorized" (RFC 6455, range 4000–4999) |
| **Dev_Mode** | `DEV_MODE=true` runtime flag that disables authentication across all endpoints |
| **Constant-time compare** | `hmac.compare_digest` — prevents timing-oracle attacks on key comparison |

---

## Requirements

### Requirement 1: WebSocket Endpoint Authentication

**User Story:** As a security engineer, I want the WebSocket endpoint to require a valid API
key, so that unauthenticated clients cannot receive real-time task status updates for
arbitrary task IDs.

#### Acceptance Criteria

1. WHEN a client connects to `/ws/{task_id}` without an `api_key` query parameter AND
   `App_Settings.api_key` is configured, THE `WebSocket_Endpoint` SHALL close the
   connection with `Close_Code_4001` and return immediately.
2. WHEN a client connects with an `api_key` that does not match `App_Settings.api_key`,
   THE `WebSocket_Endpoint` SHALL close the connection with `Close_Code_4001` and return
   immediately.
3. WHEN a client connects with an `api_key` that matches `App_Settings.api_key`, THE
   `WebSocket_Endpoint` SHALL accept the connection and proceed with normal operation.
4. THE `WebSocket_Endpoint` SHALL close the connection BEFORE calling
   `WS_Manager.connect()`, so that `WS_Manager` never registers a rejected connection.
5. THE `WebSocket_Endpoint` SHALL NOT call `await websocket.accept()` before the auth
   check — the connection must be rejected at the upgrade stage.

### Requirement 2: Dev Mode Bypass

**User Story:** As a developer, I want authentication to be disabled in development mode,
so that local testing does not require API key configuration.

#### Acceptance Criteria

1. WHILE `App_Settings.dev_mode` is `True`, THE `Auth_Guard` SHALL return `True` for any
   value of `api_key`, including `None`, empty string, and arbitrary strings.
2. WHILE `App_Settings.dev_mode` is `True`, THE `WebSocket_Endpoint` SHALL accept
   connections regardless of whether an `api_key` query parameter is present.
3. THE `Auth_Guard` SHALL check `dev_mode` FIRST, before reading `App_Settings.api_key`
   (guard clause ordering — fail fast on the cheapest check).

### Requirement 3: Unconfigured API Key Bypass

**User Story:** As an operator, I want the WebSocket endpoint to remain open when no API
key is configured, so that the behavior is consistent with all other HTTP endpoints.

#### Acceptance Criteria

1. WHILE `App_Settings.api_key` is `None` or empty string, THE `Auth_Guard` SHALL return
   `True` for any value of `api_key`, including `None`.
2. WHILE `App_Settings.api_key` is `None` or empty string, THE `WebSocket_Endpoint` SHALL
   accept connections regardless of whether an `api_key` query parameter is present.
3. This behavior MUST be consistent with `get_api_key()` in `src/core/auth.py`, which also
   allows requests when `api_key` is not configured.

### Requirement 4: Query Parameter Transport

**User Story:** As a frontend developer, I want to authenticate WebSocket connections via a
query parameter, so that browser-native WebSocket clients can authenticate.

#### Acceptance Criteria

1. THE `WebSocket_Endpoint` SHALL read the API key from the `api_key` query parameter of
   the WebSocket upgrade request.
2. A missing `api_key` query parameter SHALL be treated as equivalent to providing no key
   (i.e., `None`).
3. THE `WebSocket_Endpoint` SHALL NOT require the `X-API-Key` header for WebSocket
   connections — browser `WebSocket` API cannot set custom headers.
4. The query parameter name SHALL be exactly `api_key` (lowercase, underscore).

### Requirement 5: Auth Logic Encapsulation (SRP + Testability)

**User Story:** As a developer, I want the WebSocket authentication logic isolated in a
pure, testable helper, so that the decision function can be unit-tested independently of
the WebSocket lifecycle and FastAPI internals.

#### Acceptance Criteria

1. THE `Auth_Guard` SHALL be a pure synchronous function `_is_ws_auth_valid(api_key: str | None) -> bool`.
2. THE `Auth_Guard` SHALL have a single responsibility: determine whether a given API key
   is valid for the current settings. It SHALL NOT log, raise exceptions, or close
   connections — those are the endpoint's responsibilities.
3. THE `Auth_Guard` SHALL use `App_Settings` to read `dev_mode` and `api_key`. It SHALL
   NOT duplicate `_api_keys_match` from `src/core/auth.py` — use `hmac.compare_digest`
   directly with identical semantics.
4. THE `Auth_Guard` SHALL use constant-time comparison (`hmac.compare_digest`) on UTF-8
   bytes when comparing keys, consistent with `_api_keys_match` in `src/core/auth.py`.
5. WHEN `App_Settings.dev_mode` is `True`, THE `Auth_Guard` SHALL return `True` without
   reading `App_Settings.api_key` (guard clause, not nested if).
6. WHEN `App_Settings.api_key` is `None` or empty, THE `Auth_Guard` SHALL return `True`
   without comparing keys.
7. WHEN `App_Settings.api_key` is configured and `api_key` matches, THE `Auth_Guard` SHALL
   return `True`.
8. WHEN `App_Settings.api_key` is configured and `api_key` does not match or is `None`,
   THE `Auth_Guard` SHALL return `False`.
9. WHEN `api_key` contains non-ASCII characters that cause `UnicodeEncodeError`, THE
   `Auth_Guard` SHALL return `False` without raising — consistent with CI-002 fix in
   `src/core/auth.py`.
10. THE `Auth_Guard` function body SHALL NOT exceed 15 lines (Clean Code: functions do one
    thing, are short).

### Requirement 6: Logging (Observability)

**User Story:** As an operator, I want rejected WebSocket connections to be logged, so that
I can detect unauthorized access attempts.

#### Acceptance Criteria

1. WHEN a connection is rejected due to auth failure, THE `WebSocket_Endpoint` SHALL log a
   WARNING with the `task_id` and the reason (`"missing api_key"` or `"invalid api_key"`).
2. THE `WebSocket_Endpoint` SHALL use the project-standard `get_logger` from
   `src.utils.logging_config` (not `logging.getLogger`).
3. The log message SHALL NOT include the provided `api_key` value to avoid credential
   leakage in logs.

### Requirement 7: Preserved Post-Auth Behavior (No Regression)

**User Story:** As a backend developer, I want the WebSocket endpoint behavior after
successful authentication to be identical to the current behavior, so that no regressions
are introduced in the happy path.

#### Acceptance Criteria

1. WHEN authentication passes, THE `WebSocket_Endpoint` SHALL call
   `WS_Manager.connect(websocket, task_id)` as the first operation after the auth check.
2. WHEN authentication passes, THE `WebSocket_Endpoint` SHALL maintain the receive loop
   and handle `WebSocketDisconnect` exactly as the current implementation does.
3. WHEN an unexpected exception occurs during the receive loop, THE `WebSocket_Endpoint`
   SHALL log the error and call `WS_Manager.disconnect(websocket, task_id)`.
4. THE `WebSocket_Endpoint` SHALL use `logger.error` (not `f"..."` format string) for
   exception logging — consistent with project logging standards.

---

## SOLID Compliance Analysis

### S — Single Responsibility Principle

- `_is_ws_auth_valid` has exactly one responsibility: evaluate whether a key is valid.
  It does not log, does not close connections, does not interact with `ws_manager`.
- `websocket_endpoint` has one responsibility: orchestrate the WebSocket lifecycle
  (auth check → connect → receive loop → disconnect). Auth decision is delegated to
  `_is_ws_auth_valid`.
- **Violation risk:** if auth logic is inlined into the endpoint, the function gains two
  responsibilities. The helper prevents this.

### O — Open/Closed Principle

- Adding a new auth mechanism (e.g., JWT) in the future requires only replacing
  `_is_ws_auth_valid` — the endpoint orchestration does not change.
- **Current scope:** API key only. JWT or OAuth2 are out of scope for this wave.

### L — Liskov Substitution Principle

- Not directly applicable (no inheritance in this change).

### I — Interface Segregation Principle

- `_is_ws_auth_valid` takes only what it needs: `api_key: str | None`. It does not
  receive the full `WebSocket` object or `Request` — callers are not forced to provide
  unused context.

### D — Dependency Inversion Principle

- `_is_ws_auth_valid` reads `app_settings` directly (module-level singleton). This is
  acceptable for a private helper in the same layer. If testability requires it, tests
  can patch `src.routers.websocket.app_settings`.
- **Not introducing:** no new concrete dependencies on `auth.py` internals.

---

## Clean Code Checklist

- [ ] `_is_ws_auth_valid` ≤ 15 lines
- [ ] Guard clauses instead of nested ifs (early return pattern)
- [ ] No magic numbers — close code `4001` extracted as named constant `_WS_CLOSE_UNAUTHORIZED = 4001`
- [ ] No f-string in `logger.error` — use `%s` format
- [ ] No credential values in log messages
- [ ] Function name describes action: `_is_ws_auth_valid` → "is WebSocket auth valid?"
- [ ] `import logging` replaced with `get_logger` from `src.utils.logging_config`
