# Design Document

## Overview

Wave 6 Layering Cleanup resolves two architecture violations in the NeoFin AI backend:

- **ARCH-001**: Raw SQL in the router layer → move to `src/db/crud.py`
- **ARCH-002**: `get_engine()` reads `app_settings` directly → introduce `DatabaseConfig` dataclass

Both changes are purely structural refactors. No endpoint behaviour, no DB schema, no API contract changes.

---

## Architecture

### Current (violating) state

```
src/routers/system.py
  └── imports: sqlalchemy.text, get_engine   ← ARCH-001 violation
  └── executes: SELECT 1 inline

src/db/database.py :: get_engine()
  └── reads: app_settings.db_pool_size       ← ARCH-002 violation
  └── reads: app_settings.db_max_overflow
  └── reads: app_settings.db_pool_timeout
  └── reads: app_settings.db_pool_recycle
  └── reads: app_settings.db_pool_pre_ping
```

### Target (compliant) state

```
src/routers/system.py
  └── imports: check_database_connectivity from src.db.crud
  └── no SQL, no engine imports

src/db/crud.py
  └── check_database_connectivity() -> bool   ← new function

src/db/database.py
  └── DatabaseConfig (frozen dataclass)       ← new type
  └── get_engine(config: DatabaseConfig | None = None)
```

---

## Components

### Commit 1 — ARCH-001: `src/db/crud.py` + `src/routers/system.py`

#### `src/db/crud.py` — new function

```python
async def check_database_connectivity() -> bool:
    """Execute a lightweight SELECT 1 to verify DB connectivity."""
    try:
        session_maker = get_session_maker()
        async with session_maker() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
```

Required import addition to `crud.py`:
```python
from sqlalchemy import text  # add to existing sqlalchemy imports
```

#### `src/routers/system.py` — updated helper

```python
async def _database_is_available(log_context: str) -> bool:
    try:
        return await check_database_connectivity()
    except Exception as e:
        logger.error("%s: %s", log_context, e)
        return False
```

Import changes in `system.py`:
- Remove: `from sqlalchemy import text`
- Remove: `from src.db.database import get_engine`
- Add: `from src.db.crud import check_database_connectivity`

**Invariants preserved:**
- `/system/health`, `/system/healthz`, `/system/ready` response shapes are unchanged
- Error logging stays in the router (it owns the `log_context` string)
- `_database_is_available` always returns `bool`, never raises

---

### Commit 2 — ARCH-002: `src/db/database.py`

#### New `DatabaseConfig` dataclass

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class DatabaseConfig:
    pool_size: int
    max_overflow: int
    pool_timeout: int
    pool_recycle: int
    pool_pre_ping: bool

    @classmethod
    def from_settings(cls, settings) -> "DatabaseConfig":
        return cls(
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_recycle=settings.db_pool_recycle,
            pool_pre_ping=settings.db_pool_pre_ping,
        )
```

#### Updated `get_engine()` signature

```python
def get_engine(config: DatabaseConfig | None = None) -> AsyncEngine:
    global _engine, AsyncSessionLocal

    if _engine is not None:
        return _engine

    db_url = _resolve_database_url()
    cfg = config or DatabaseConfig.from_settings(app_settings)

    pool_size, max_overflow = _clamp_pool_settings(cfg.pool_size, cfg.max_overflow)
    logger.info(
        "Database pool configured: pool_size=%d, max_overflow=%d, "
        "timeout=%ds, recycle=%ds",
        pool_size,
        max_overflow,
        cfg.pool_timeout,
        cfg.pool_recycle,
    )

    _engine = _create_engine_with_pool(
        db_url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=cfg.pool_timeout,
        pool_recycle=cfg.pool_recycle,
        pool_pre_ping=cfg.pool_pre_ping,
    )
    AsyncSessionLocal = _make_session_maker(_engine)
    return _engine
```

**Invariants preserved:**
- All existing callers of `get_engine()` with no arguments continue to work unchanged
- `_clamp_pool_settings()` is still the sole location for pool bounds logic
- `get_session()`, `get_session_maker()`, `dispose_engine()` signatures and behaviour unchanged

---

## Data Models

No schema changes. `DatabaseConfig` is a runtime-only configuration carrier — it is never persisted.

---

## Error Handling

### ARCH-001
- `check_database_connectivity()` has a broad `except Exception` that swallows all errors and returns `False`. This is intentional: the function's contract is to return a `bool` health signal, not to propagate DB errors.
- The router's `_database_is_available()` retains its own `except Exception` as a defensive outer guard in case `check_database_connectivity()` itself has a bug that causes it to raise (e.g., import error during testing). This preserves the existing logging behaviour.

### ARCH-002
- No new error handling needed. `DatabaseConfig.from_settings()` will raise `AttributeError` if the settings object is missing a required field — this is the correct fail-fast behaviour at startup.

---

## Testing Strategy

### Commit 1 — ARCH-001

**Property-based test** (`tests/test_wave6_layering_cleanup.py`):

```
Property: check_database_connectivity() always returns bool
  For any exception raised by the session (mocked), the function
  must return False (a bool), never raise, never return None.
  Strategy: @given(st.sampled_from([Exception, RuntimeError,
             OSError, ValueError, asyncio.TimeoutError]))
```

**Example tests:**
- `test_router_does_not_import_sqlalchemy_text` — inspect `system` module's `__dict__` / source
- `test_router_does_not_import_get_engine` — same
- `test_health_endpoint_db_up` — TestClient, mock `check_database_connectivity` → True
- `test_health_endpoint_db_down` — mock → False, assert `"db": "down"`
- `test_ready_endpoint_db_down_returns_503` — mock → False, assert 503
- `test_database_is_available_logs_on_exception` — mock raises, assert `logger.error` called

### Commit 2 — ARCH-002

**Property-based test** (`tests/test_wave6_layering_cleanup.py`):

```
Property: DatabaseConfig.from_settings(s) fields match settings
  For any object with integer pool fields and bool pool_pre_ping,
  from_settings must produce a DatabaseConfig where every field
  equals the corresponding attribute.
  Strategy: @given(st.builds(MockSettings,
             db_pool_size=st.integers(),
             db_max_overflow=st.integers(),
             db_pool_timeout=st.integers(),
             db_pool_recycle=st.integers(),
             db_pool_pre_ping=st.booleans()))
```

**Example tests:**
- `test_get_engine_no_args_uses_app_settings` — call `get_engine()` with no args, verify pool values match `app_settings`
- `test_get_engine_with_explicit_config` — pass a `DatabaseConfig`, verify those values are used
- `test_database_config_is_frozen` — attempt mutation, assert `FrozenInstanceError`
- `test_clamp_pool_settings_still_called` — verify `_clamp_pool_settings` is invoked with `cfg` values

---

## Correctness Properties

### Property 1 — ARCH-001: `check_database_connectivity()` always returns `bool`

**Type**: Invariant

For all possible exception types raised by the underlying session, `check_database_connectivity()` must return a value that is an instance of `bool` and must never raise an exception itself.

```python
@given(st.sampled_from([Exception("db error"), RuntimeError("conn refused"),
                         OSError("timeout"), ValueError("bad url")]))
@pytest.mark.anyio
async def test_check_db_connectivity_always_returns_bool(exc):
    with patch("src.db.crud.get_session_maker") as mock_sm:
        mock_sm.return_value.return_value.__aenter__.side_effect = exc
        result = await check_database_connectivity()
        assert isinstance(result, bool)
```

### Property 2 — ARCH-002: `DatabaseConfig.from_settings()` fields match source

**Type**: Invariant / Round-trip

For any settings-like object with the five pool attributes, `DatabaseConfig.from_settings(s)` must produce a `DatabaseConfig` where every field equals the corresponding attribute on `s`.

```python
@given(
    pool_size=st.integers(),
    max_overflow=st.integers(),
    pool_timeout=st.integers(),
    pool_recycle=st.integers(),
    pool_pre_ping=st.booleans(),
)
def test_database_config_from_settings_fields_match(
    pool_size, max_overflow, pool_timeout, pool_recycle, pool_pre_ping
):
    class MockSettings:
        db_pool_size = pool_size
        db_max_overflow = max_overflow
        db_pool_timeout = pool_timeout
        db_pool_recycle = pool_recycle
        db_pool_pre_ping = pool_pre_ping

    cfg = DatabaseConfig.from_settings(MockSettings())
    assert cfg.pool_size == pool_size
    assert cfg.max_overflow == max_overflow
    assert cfg.pool_timeout == pool_timeout
    assert cfg.pool_recycle == pool_recycle
    assert cfg.pool_pre_ping == pool_pre_ping
```
