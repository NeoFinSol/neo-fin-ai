# Implementation Plan

## Commit 1 — ARCH-001: Move DB connectivity check to CRUD layer

- [x] 1. Add `check_database_connectivity()` to `src/db/crud.py`
  - [x] 1.1 Add `text` to the existing `sqlalchemy` import line in `crud.py`
  - [x] 1.2 Implement `async def check_database_connectivity() -> bool` with a broad `except Exception` that returns `False` on any error

- [x] 2. Update `src/routers/system.py` to use the new CRUD function
  - [x] 2.1 Remove `from sqlalchemy import text` import
  - [x] 2.2 Remove `from src.db.database import get_engine` import
  - [x] 2.3 Add `from src.db.crud import check_database_connectivity` import
  - [x] 2.4 Replace the body of `_database_is_available()` to call `check_database_connectivity()` and keep error logging in the router

- [ ] 3. Write tests for ARCH-001 in `tests/test_wave6_layering_cleanup.py`
  - [x] 3.1 PBT: `test_check_db_connectivity_always_returns_bool` — property that for any mocked exception the function returns a `bool` and never raises
  - [x] 3.2 Example: `test_router_does_not_import_sqlalchemy_text` — assert `text` is not in `system` module imports
  - [x] 3.3 Example: `test_router_does_not_import_get_engine` — assert `get_engine` is not in `system` module imports
  - [x] 3.4 Example: `test_health_endpoint_db_up` — mock `check_database_connectivity` → `True`, assert `{"db": "ok"}`
  - [x] 3.5 Example: `test_health_endpoint_db_down` — mock → `False`, assert `{"db": "down"}` and overall `"status": "down"`
  - [x] 3.6 Example: `test_ready_endpoint_db_down_returns_503` — mock → `False`, assert HTTP 503
  - [x] 3.7 Example: `test_database_is_available_logs_on_exception` — mock raises, assert `logger.error` called with `log_context`

## Commit 2 — ARCH-002: Introduce `DatabaseConfig` dataclass

- [x] 4. Add `DatabaseConfig` dataclass to `src/db/database.py`
  - [x] 4.1 Add `from dataclasses import dataclass` import
  - [x] 4.2 Define `@dataclass(frozen=True) class DatabaseConfig` with fields: `pool_size`, `max_overflow`, `pool_timeout`, `pool_recycle`, `pool_pre_ping`
  - [x] 4.3 Implement `DatabaseConfig.from_settings(cls, settings) -> DatabaseConfig` classmethod

- [x] 5. Update `get_engine()` in `src/db/database.py`
  - [x] 5.1 Change signature to `def get_engine(config: DatabaseConfig | None = None) -> AsyncEngine`
  - [x] 5.2 Add `cfg = config or DatabaseConfig.from_settings(app_settings)` as the first step after the early-return guard
  - [x] 5.3 Replace all direct `app_settings.db_*` reads inside `get_engine()` with `cfg.*` field accesses
  - [x] 5.4 Verify `_clamp_pool_settings` is called with `cfg.pool_size` and `cfg.max_overflow`
  - [x] 5.5 Verify `_create_engine_with_pool` is called with `cfg.pool_timeout`, `cfg.pool_recycle`, `cfg.pool_pre_ping`

- [ ] 6. Write tests for ARCH-002 in `tests/test_wave6_layering_cleanup.py`
  - [x] 6.1 PBT: `test_database_config_from_settings_fields_match` — property that `from_settings` always produces a `DatabaseConfig` with all fields matching the input settings object
  - [x] 6.2 Example: `test_get_engine_no_args_backward_compat` — call `get_engine()` with no args, assert it returns an `AsyncEngine` without error
  - [x] 6.3 Example: `test_get_engine_with_explicit_config` — pass a custom `DatabaseConfig`, assert pool values are used (via mock on `_create_engine_with_pool`)
  - [x] 6.4 Example: `test_database_config_is_frozen` — attempt to set a field after construction, assert `FrozenInstanceError`
  - [x] 6.5 Example: `test_get_session_maker_unchanged` — call `get_session_maker()`, assert it returns an `async_sessionmaker` instance
