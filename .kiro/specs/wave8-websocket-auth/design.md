# Design Document — wave8-websocket-auth

## Overview

Add API key authentication to the WebSocket endpoint at `src/routers/websocket.py`.
Authentication is performed during the HTTP upgrade handshake via a query parameter
(`?api_key=...`). Rejected connections are closed with WebSocket close code 4001 before
`ws_manager.connect()` is ever called, so the connection manager never sees unauthorized
clients.

**Scope:** single-file change. No new modules, no schema changes, no API contract changes
for authenticated callers.

---

## Architecture

### Layer Placement

```
routers/websocket.py   ← ONLY file changed
  │
  ├── _is_ws_auth_valid()   reads → app_settings (models layer)
  │                                  (dev_mode, api_key)
  │
  └── websocket_endpoint()  calls → ws_manager (core layer)
                                     (connect, disconnect)
```

The change stays within the router layer. No upward dependencies introduced.

### Component Interaction Diagram

```
Client (browser / API consumer)
  │
  │  GET /ws/{task_id}?api_key=<key>   (HTTP Upgrade)
  ▼
websocket_endpoint(websocket, task_id, api_key)
  │
  ├─► _is_ws_auth_valid(api_key)
  │       │
  │       │  reads: app_settings.dev_mode
  │       │  reads: app_settings.api_key
  │       │  uses:  hmac.compare_digest
  │       │
  │       ├─ False → logger.warning(task_id, reason)
  │       │          await websocket.close(code=_WS_CLOSE_UNAUTHORIZED)
  │       │          return                          ← WS_Manager never touched
  │       │
  │       └─ True  → await ws_manager.connect(websocket, task_id)
  │                       │
  │                       └─► receive loop
  │                               ├─ WebSocketDisconnect → ws_manager.disconnect()
  │                               └─ Exception           → logger.error()
  │                                                         ws_manager.disconnect()
  └─► (existing behavior unchanged after auth passes)
```

### Files Changed

| File | Change type | Description |
|------|-------------|-------------|
| `src/routers/websocket.py` | Modify | Add `hmac`, `Query`, `get_logger` imports; add `_WS_CLOSE_UNAUTHORIZED` constant; add `_is_ws_auth_valid()`; update endpoint signature and add auth guard |

### Files NOT Changed

| File | Reason |
|------|--------|
| `src/core/auth.py` | No new public helpers needed; `_is_ws_auth_valid` reads `app_settings` directly |
| `src/core/ws_manager.py` | Manager is auth-unaware by design (SRP) |
| `src/models/settings.py` | No new settings fields needed |
| Any other router | Already use `Depends(get_api_key)` |

---

## Detailed Design

### Named Constant

```python
# Avoids magic number — RFC 6455 application-level "Unauthorized"
_WS_CLOSE_UNAUTHORIZED: int = 4001
```

**Why 4001 and not 1008 (Policy Violation)?**
RFC 6455 §7.4.2 reserves 4000–4999 for application-defined use. Code 1008 is a generic
"policy violation" that does not convey auth semantics. Code 4001 is the de-facto
convention for "Unauthorized" in WebSocket APIs (analogous to HTTP 401). The frontend's
hybrid WS + polling fallback strategy will treat any non-1000 close as a signal to fall
back to polling.

### `_is_ws_auth_valid(api_key: str | None) -> bool`

**SRP:** pure decision function. No side effects, no logging, no I/O.
**Guard clauses:** early return on cheapest checks first.
**Constant-time compare:** prevents timing oracle on key comparison.

```python
def _is_ws_auth_valid(api_key: str | None) -> bool:
    """Return True if the provided api_key is valid for the current settings."""
    if app_settings.dev_mode:          # guard 1: dev mode bypasses all auth
        return True
    if not app_settings.api_key:       # guard 2: no key configured → open
        return True
    if not api_key:                    # guard 3: key required but not provided
        return False
    try:
        return hmac.compare_digest(    # constant-time comparison
            api_key.encode("utf-8"),
            app_settings.api_key.encode("utf-8"),
        )
    except (UnicodeEncodeError, AttributeError):
        return False                   # non-ASCII or non-string → mismatch
```

**Decision table:**

| `dev_mode` | `settings.api_key` | `api_key` param | Result | Guard hit |
|------------|-------------------|-----------------|--------|-----------|
| `True` | any | any | `True` | Guard 1 |
| `False` | `None` / `""` | any | `True` | Guard 2 |
| `False` | configured | `None` / `""` | `False` | Guard 3 |
| `False` | configured | matches | `True` | compare_digest |
| `False` | configured | no match | `False` | compare_digest |
| `False` | configured | non-ASCII | `False` | except clause |

**SOLID check:**
- S: one responsibility — evaluate key validity
- I: takes only `api_key: str | None`, not the full `WebSocket` or `Request`
- D: reads `app_settings` (module-level singleton, same layer) — acceptable for private helper

**Clean Code check:**
- 12 lines (≤ 15 limit)
- Guard clauses, no nested ifs
- Descriptive name: `_is_ws_auth_valid` → "is WebSocket auth valid?"
- No magic numbers (uses `_WS_CLOSE_UNAUTHORIZED` at call site)

### Updated `websocket_endpoint`

```python
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

@router.websocket("/{task_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    task_id: str,
    api_key: str | None = Query(default=None, alias="api_key"),
) -> None:
    if not _is_ws_auth_valid(api_key):
        reason = "missing api_key" if not api_key else "invalid api_key"
        logger.warning(
            "WebSocket auth rejected: task_id=%s reason=%s", task_id, reason
        )
        await websocket.close(code=_WS_CLOSE_UNAUTHORIZED)
        return
    await ws_manager.connect(websocket, task_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, task_id)
    except Exception as exc:
        logger.error("WebSocket error: task_id=%s error=%s", task_id, exc)
        ws_manager.disconnect(websocket, task_id)
```

**Changes from current implementation:**
1. `import logging` → `from src.utils.logging_config import get_logger` (project standard)
2. `logger = logging.getLogger(__name__)` → `logger = get_logger(__name__)`
3. Added `api_key` query param
4. Added auth guard block (4 lines)
5. `logger.error(f"...")` → `logger.error("...", task_id, exc)` (no f-string, Clean Code)
6. Added `-> None` return type annotation

**SOLID check:**
- S: endpoint orchestrates lifecycle; auth decision delegated to `_is_ws_auth_valid`
- O: adding new auth mechanism → replace `_is_ws_auth_valid`, endpoint unchanged
- D: depends on `_is_ws_auth_valid` abstraction, not on `hmac` directly

**Clean Code check:**
- Function ≤ 25 lines (orchestration is allowed to be slightly longer)
- One level of abstraction: auth check → connect → receive loop
- No magic numbers: `_WS_CLOSE_UNAUTHORIZED` used
- No credential values in log output

---

## Why Query Parameter and Not Header?

The browser-native `WebSocket` API (`new WebSocket(url)`) cannot set custom headers during
the HTTP upgrade handshake. This is a browser security restriction, not a FastAPI
limitation. Query parameter is the standard browser-compatible approach for WS
authentication used by Slack, Pusher, Ably, and others.

Server-side clients (Python `websockets`, `curl --include`) can also use query params
trivially. The tradeoff is that the key appears in server access logs — operators should
be aware and rotate keys if logs are compromised.

---

## Security Considerations

| Concern | Mitigation |
|---------|-----------|
| Timing oracle on key comparison | `hmac.compare_digest` — constant-time |
| Non-ASCII key causes exception | `except (UnicodeEncodeError, AttributeError)` → `False` |
| Partial state in WS_Manager on rejection | Rejection happens before `ws_manager.connect()` |
| API key in access logs | Accepted tradeoff for browser compatibility; documented |
| API key in application logs | `_is_ws_auth_valid` never logs the key value |
| Brute-force key guessing | Out of scope — rate limiting is handled by middleware |

---

## Correctness Properties (PBT)

### Property P1 — dev_mode always allows

```
∀ api_key ∈ (str | None):
  given dev_mode=True
  → _is_ws_auth_valid(api_key) == True
```

Hypothesis strategy: `st.one_of(st.none(), st.text())`

### Property P2 — unconfigured key always allows

```
∀ api_key ∈ (str | None):
  given dev_mode=False, settings.api_key=None
  → _is_ws_auth_valid(api_key) == True
```

Hypothesis strategy: `st.one_of(st.none(), st.text())`

### Property P3 — non-matching key always denies

```
∀ api_key ∈ (str | None) where api_key ≠ "configured-secret":
  given dev_mode=False, settings.api_key="configured-secret"
  → _is_ws_auth_valid(api_key) == False
```

Hypothesis strategy: `st.one_of(st.none(), st.text()).filter(lambda k: k != "configured-secret")`

### Property P4 — result is always bool (never raises)

```
∀ api_key ∈ (str | None | arbitrary object):
  _is_ws_auth_valid(api_key) ∈ {True, False}  — never raises
```

This covers the UnicodeEncodeError and AttributeError guard paths.

---

## Testing Strategy

### Unit tests — `_is_ws_auth_valid` (pure function, no mocks needed)

| Test | Input | Expected |
|------|-------|----------|
| dev_mode=True, key=None | `None` | `True` |
| dev_mode=True, key="wrong" | `"wrong"` | `True` |
| no api_key configured, key=None | `None` | `True` |
| no api_key configured, key="anything" | `"anything"` | `True` |
| key configured, correct key | `"secret"` | `True` |
| key configured, wrong key | `"wrong"` | `False` |
| key configured, key=None | `None` | `False` |
| key configured, empty string | `""` | `False` |
| key configured, non-ASCII | `"\xff\xfe"` | `False` (no raise) |
| PBT P1 | any | `True` when dev_mode |
| PBT P2 | any | `True` when unconfigured |
| PBT P3 | non-matching | `False` when configured |
| PBT P4 | any | always bool, never raises |

### Integration tests — `websocket_endpoint`

| Test | Setup | Expected |
|------|-------|----------|
| No key, api_key configured | `api_key=None` | close(4001), ws_manager.connect NOT called |
| Wrong key | `api_key="wrong"` | close(4001), ws_manager.connect NOT called |
| Correct key | `api_key="secret"` | ws_manager.connect called |
| dev_mode=True, no key | `api_key=None` | ws_manager.connect called |
| api_key not configured, no key | `api_key=None` | ws_manager.connect called |
| Rejection logged | wrong key | logger.warning called with task_id |
| No key value in log | wrong key | log message does NOT contain the key |

---

## Linting / Style Constraints

- `isort --profile black` must pass
- `black --check` must pass
- No new `# noqa` suppressions
- `import logging` removed; `get_logger` used instead
- No f-strings in logger calls — use `%s` format
