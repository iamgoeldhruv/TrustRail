# TrustRail

An authorization and transaction-control layer that lets AI agents act
on real systems while keeping every action policy-checked,
human-approved, auditable and recoverable.

## Tech Stack

-   Python 3.12+
-   FastAPI
-   Pydantic
-   Pydantic Settings
-   SQLite
-   MCP Python SDK
-   HTTPX
-   Pytest
-   Ruff
-   MyPy

## Current Progress

### Project Setup & Scaffolding

-   [x] Initialized Python virtual environment.
-   [x] Created project dependency configuration (`pyproject.toml`).
-   [x] Installed project dependencies.
-   [x] Created backend directory structure.
-   [x] Initialized FastAPI application.
-   [x] Implemented basic `/health` endpoint.
-   [x] Created `Makefile` for common development commands.
-   [x] Created `.env.example` for environment configuration.
-   [x] Created `.gitignore` for excluding secrets and generated files.
-   [x] Added centralized application configuration using Pydantic
    Settings.

### Otari Integration & CLI

- [x] Implemented asynchronous Otari chat-completions client using HTTPX.
- [x] Added custom exception handling for Otari API, authentication, connection and timeout errors.
- [x] Implemented HTTP client lifecycle management.
- [x] Created `trustrail ping` CLI command.
- [x] Verified successful inference through the hosted Otari gateway.
- [x] Implemented asynchronous Otari MCP discovery and execution client using HTTPX.
- [x] Added Pydantic models for MCP discovery and execution responses.
- [x] Added error handling for MCP discovery and execution failures.
- [x] Created scripts to verify MCP discovery and tool execution through the actual Otari API.
- [x] Verified successful read-only `get_status` execution through Otari using a workspace API key.
- [x] Verified MCP server configuration change detection using `server_revision`.
- [x] Verified stale revision rejection with HTTP 409 (`mcp_server_changed`).
### MCP Server Spike

- [x] Implemented a Python MCP server using Streamable HTTP.
- [x] Added `get_status` (read) and `update_status` (write) tools.
- [x] Verified tool discovery and execution using MCP Inspector.
- [x] Deployed the MCP server publicly over HTTPS on Railway.
- [x] Registered the MCP server in Otari with an explicit tool allowlist.
- [x] Integrated Otari MCP tool discovery using `GET /api/v1/mcp/servers/{server_id}/tools`.
- [x] Verified discovery of allowlisted tools and captured the returned `server_revision`.

### Policy Schema & Validation

- [x] Implemented strict Pydantic models for policy schema v1.
- [x] Added strict JSON parsing with unknown-field rejection.
- [x] Added numeric bounds validation for policy limits.
- [x] Added semantic validation for contradictory policies.
- [x] Added policy parsing and validation tests.

### Authorization Models

- [x] Defined typed Fact models for GitHub issue attributes.
- [x] Added Action model for representing agent-proposed operations.
- [x] Added Decision model with authorization outcomes and reason codes.
### Authorization Engine

- [x] Implemented deterministic policy-based authorization evaluation.
- [x] Added checks for action permissions, issue state, inactivity and priority.
- [x] Enforced fail-closed behavior for missing priority and unavailable facts.
- [x] Added action-budget enforcement and approval decisions.
- [x] Added authorization engine tests covering decision rules and edge cases.
### Transaction State Machine

- [x] Defined explicit transaction states using Python Enum.
- [x] Implemented centralized allowed-transition table using immutable sets.
- [x] Added transition validation to enforce valid state transitions.
- [x] Implemented custom `InvalidTransitionError` for illegal transitions.
- [x] Added tests covering valid transitions, invalid transitions, terminal states and transition-table completeness.
### SQLite Persistence

-   [x] Added SQLite connection management with foreign-key enforcement,
    busy-timeout handling, row-based results and automatic database-directory
    creation.
-   [x] Added ordered, atomic SQL migrations with migration history tracking.
-   [x] Added the initial policy, run, transaction, approval and event schema
    with transaction query indexes.
-   [x] Added typed transaction models and a `TransactionStore` for creating,
    retrieving, updating and listing transactions.
-   [x] Enforced transaction state transitions through the existing state
    machine before status updates.
-   [x] Added deterministic JSON serialization and UTC ISO 8601 timestamps.
-   [x] Integrated migrations into the FastAPI lifespan so the configured
    database is initialized before the application accepts requests.
-   [x] Added database migration and persistence tests using temporary SQLite
    databases.
-   [x] Implemented atomic transaction claiming for dispatch using a conditional
      database update (`PRECHECK` → `DISPATCHING`) and rows-affected validation.
-   [x] Added tests covering successful claims, repeated claims, ineligible states,
      nonexistent transactions, timestamp updates and concurrent claim attempts.
-   [x] Implemented startup recovery to move transactions left in
      `DISPATCHING` to `INDETERMINATE` after application restarts.
-   [x] Added recovery tests covering multiple transactions, unchanged states
      and idempotent execution.

## Running Locally

``` bash
source .venv/bin/activate
make run
```

Database migrations run automatically during application startup. The database
path defaults to `./data/trustrail.db` and can be overridden with
`TR_DB_PATH`:

``` bash
TR_DB_PATH=./data/dev.db make run
```

To run the test suite and development checks:

``` bash
pytest
ruff check app tests
mypy app
```

## Directory Structure

``` text
TrustRail/
│
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   └── commands/
│   │       ├── __init__.py
│   │       └── ping.py
│   ├── otari/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── exceptions.py
│   │   └── mcp.py
│   ├── policy/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── parser.py
│   │   └── validator.py
│   ├── authz/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   └── engine.py
│   ├── facts/
│   ├── db/
│   │   ├── __init__.py
│   │   ├── connection.py
│   │   └── migrations.py
│   ├── txn/
│   │   ├── __init__.py
│   │   ├── states.py
│   │   ├── exceptions.py
│   │   ├── transitions.py
│   │   ├── models.py
│   │   └── store.py
│   ├── approvals/
│   ├── ledger/
│   ├── agent/
│   ├── reconcile/
│   ├── scenarios/
│   └── fakeotari/
│
├── mcp_github/
├── mcp_spike/
│   ├── __init__.py
│   └── server.py
│
├── tests/
│   ├── db/
│   │   ├── test_connection.py
│   │   └── test_migrations.py
│   ├── otari/
│   │   └── test_mcp.py
│   ├── policy/
│   │   └── test_parser.py
│   └── authz/
│       └── test_engine.py
│   ├── txn/
│   │   └── test_transitions.py
│       └── test_store.py
├── migrations/
│   ├── 001_initial_schema.sql
│   └── 002_transaction_indexes.sql
├── scripts/
│   ├── discover_otari_mcp.py
│   └── execute_otari_mcp.py
│
├── docs/
├── Dockerfile
├── requirements.txt
├── pyproject.toml
├── Makefile
├── .env.example
├── .gitignore
└── README.md