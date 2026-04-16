# Requirements Document

## Introduction

Wave 6 of the NeoFin AI audit backlog addresses two layering violations found in the backend codebase.

**ARCH-001** — The router layer (`src/routers/system.py`) directly executes a raw SQL query (`SELECT 1`) to check database connectivity. This violates the architecture rule that SQL belongs exclusively in `src/db/crud.py`. The router imports `sqlalchemy.text` and `get_engine` directly, creating an illegal cross-layer dependency.

**ARCH-002** — `src/db/database.py` reads `app_settings` directly inside `get_engine()` to obtain pool configuration values. This creates tight coupling between the DB infrastructure layer and the concrete `AppSettings` singleton, violating the Dependency Inversion Principle. The function is not independently testable without patching the global singleton.

Both findings are addressed in two logical commits that restore strict top-down layering and improve testability without changing any observable endpoint behaviour.

## Glossary

- **Router**: A FastAPI router module in `src/routers/`. Responsible for HTTP request/response handling only. Must not contain SQL or business logic.
- **CRUD**: The `src/db/crud.py` module. The only permitted location for SQL execution in the project.
- **DB_Layer**: The `src/db/` package, including `database.py` and `crud.py`.
- **System_Router**: The module `src/routers/system.py` that exposes `/system/health`, `/system/healthz`, and `/system/ready` endpoints.
- **Connectivity_Checker**: The new function `check_database_connectivity() -> bool` to be added to `src/db/crud.py`.
- **DatabaseConfig**: A frozen dataclass to be added to `src/db/database.py` that encapsulates all DB pool configuration parameters.
- **AppSettings**: The global settings singleton `app_settings` from `src/models/settings.py`.
- **Engine**: The SQLAlchemy `AsyncEngine` instance managed by `src/db/database.py`.

---

## Requirements

### Requirement 1: Move DB Connectivity Check to CRUD Layer (ARCH-001)

**User Story:** As a backend engineer, I want the database connectivity check to live in `src/db/crud.py`, so that the router layer contains no SQL and the architecture layering rules are enforced.

#### Acceptance Criteria

1. THE CRUD SHALL expose a public async function `check_database_connectivity() -> bool` that executes a lightweight `SELECT 1` query to verify DB connectivity.
2. WHEN `check_database_connectivity()` is called and the database is reachable, THE Connectivity_Checker SHALL return `True`.
3. WHEN `check_database_connectivity()` is called and any exception is raised during the query, THE Connectivity_Checker SHALL catch the exception and return `False` without re-raising.
4. THE Connectivity_Checker SHALL return a value of type `bool` for all possible execution paths, including exception paths.
5. THE System_Router SHALL call `check_database_connectivity()` from `src/db/crud.py` instead of executing SQL directly.
6. WHEN `check_database_connectivity()` raises an unexpected exception that escapes its own try/except, THE System_Router SHALL catch it, log the error using `logger.error` with the `log_context` string, and return `False`.
7. THE System_Router SHALL NOT import `sqlalchemy.text` after this change is applied.
8. THE System_Router SHALL NOT import `get_engine` from `src/db/database.py` after this change is applied.
9. WHEN the `/system/health` endpoint is called, THE System_Router SHALL return the same response shape and status semantics as before this change.
10. WHEN the `/system/healthz` endpoint is called, THE System_Router SHALL return the same response shape and status semantics as before this change.
11. WHEN the `/system/ready` endpoint is called, THE System_Router SHALL return the same response shape and status semantics as before this change.

---

### Requirement 2: Introduce DatabaseConfig to Decouple Pool Settings (ARCH-002)

**User Story:** As a backend engineer, I want `get_engine()` to accept pool configuration as a parameter rather than reading `app_settings` directly, so that the DB infrastructure layer is independently testable and decoupled from the concrete settings singleton.

#### Acceptance Criteria

1. THE DB_Layer SHALL define a frozen dataclass `DatabaseConfig` in `src/db/database.py` with fields: `pool_size: int`, `max_overflow: int`, `pool_timeout: int`, `pool_recycle: int`, `pool_pre_ping: bool`.
2. THE DatabaseConfig SHALL expose a classmethod `from_settings(cls, settings) -> DatabaseConfig` that constructs a `DatabaseConfig` instance by reading the five pool fields from the provided settings object.
3. WHEN `DatabaseConfig.from_settings(settings)` is called with a settings object, THE DatabaseConfig SHALL produce an instance where each field value equals the corresponding attribute on the settings object.
4. THE DB_Layer SHALL update `get_engine()` to accept an optional parameter `config: DatabaseConfig | None = None`.
5. WHEN `get_engine()` is called with `config=None`, THE Engine SHALL use `DatabaseConfig.from_settings(app_settings)` as the effective configuration, preserving all existing default behaviour.
6. WHEN `get_engine()` is called with an explicit `DatabaseConfig` instance, THE Engine SHALL use that instance's field values for pool configuration instead of reading `app_settings` directly.
7. THE DB_Layer SHALL pass `cfg.pool_size` and `cfg.max_overflow` to `_clamp_pool_settings()` rather than reading them from `app_settings` directly inside `get_engine()`.
8. THE DB_Layer SHALL pass `cfg.pool_timeout`, `cfg.pool_recycle`, and `cfg.pool_pre_ping` to `_create_engine_with_pool()` rather than reading them from `app_settings` directly inside `get_engine()`.
9. WHEN `get_engine()` is called with no arguments by any existing caller, THE Engine SHALL initialise successfully without any change to the calling code.
10. THE DB_Layer SHALL NOT change the signatures or behaviour of `get_session()`, `get_session_maker()`, or `dispose_engine()`.
11. THE DB_Layer SHALL keep all pool clamping logic inside `_clamp_pool_settings()` and SHALL NOT duplicate it inside `get_engine()` or `DatabaseConfig`.
12. IF a `DatabaseConfig` instance is mutated after construction, THE DatabaseConfig SHALL raise a `FrozenInstanceError`, preventing accidental modification of pool settings.
