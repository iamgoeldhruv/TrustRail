# TrustRail

An authorization and transaction-control layer that lets AI agents act on real systems while keeping every action policy-checked, human-approved, auditable and recoverable.

## Tech Stack

- Python 3.12+
- FastAPI
- Pydantic
- Pydantic Settings
- SQLite
- MCP Python SDK
- HTTPX
- Pytest
- Ruff
- MyPy

## Current Progress

### Project Setup & Scaffolding

- [x] Initialized Python virtual environment and installed dependencies.
- [x] Created project structure and dependency configuration (`pyproject.toml`).
- [x] Initialized FastAPI application with `/health` endpoint.
- [x] Added Makefile, `.env.example` and `.gitignore`.
- [x] Added centralized configuration using Pydantic Settings.

### Otari Integration & CLI

- [x] Implemented asynchronous Otari chat-completions client using HTTPX.
- [x] Added custom exception handling for API, authentication, connection and timeout errors.
- [x] Implemented HTTP client lifecycle management.
- [x] Created `trustrail ping` CLI command.
- [x] Verified inference through the hosted Otari gateway.
- [x] Implemented asynchronous Otari MCP discovery and execution client.
- [x] Added Pydantic response models and error handling.
- [x] Created scripts to verify MCP discovery and tool execution.
- [x] Verified read-only `get_status` execution using a workspace API key.
- [x] Verified MCP server revision detection and stale revision rejection (HTTP 409).

### MCP Server Spike

- [x] Implemented a Python MCP server using Streamable HTTP.
- [x] Added `get_status` (read) and `update_status` (write) tools.
- [x] Verified tool discovery and execution using MCP Inspector.
- [x] Deployed the MCP server publicly over HTTPS on Railway.
- [x] Registered the server in Otari with an explicit tool allowlist.
- [x] Verified allowlisted tool discovery and captured `server_revision`.

### Policy Schema & Validation

- [x] Implemented strict Pydantic models for policy schema v1.
- [x] Added strict JSON parsing with unknown-field rejection.
- [x] Added numeric bounds and semantic validation.
- [x] Added policy parsing and validation tests.

### Authorization Models & Engine

- [x] Defined typed Fact models for GitHub issue attributes.
- [x] Added Action and Decision models.
- [x] Implemented deterministic policy-based authorization evaluation.
- [x] Added checks for action permissions, issue state, inactivity and priority.
- [x] Enforced fail-closed behavior for missing or unavailable facts.
- [x] Added action-budget enforcement and approval decisions.
- [x] Added authorization tests covering decision rules and edge cases.

### Transaction State Machine

- [x] Defined transaction states using Python Enum.
- [x] Implemented centralized immutable allowed-transition table.
- [x] Added transition validation and `InvalidTransitionError`.
- [x] Added tests for valid and invalid transitions, terminal states and transition-table completeness.

### SQLite Persistence

- [x] Added SQLite connection management with foreign-key enforcement, busy-timeout handling and automatic database-directory creation.
- [x] Added ordered, atomic SQL migrations with migration history tracking.
- [x] Created initial policy, run, transaction, approval and event schema with indexes.
- [x] Added typed transaction models and `TransactionStore`.
- [x] Enforced state-machine validation for transaction status updates.
- [x] Added deterministic JSON serialization and UTC timestamps.
- [x] Integrated migrations into the FastAPI lifespan.
- [x] Added database migration and persistence tests.
- [x] Implemented atomic dispatch claiming (`PRECHECK` → `DISPATCHING`) using conditional updates and rows-affected validation.
- [x] Added concurrent dispatch-claim tests.
- [x] Implemented startup recovery (`DISPATCHING` → `INDETERMINATE`).
- [x] Added recovery tests covering multiple transactions, unchanged states and idempotency.

### Audit Ledger

- [x] Added typed ledger event and verification models.
- [x] Implemented deterministic canonical JSON serialization.
- [x] Implemented SHA-256 event hashing with previous-hash linkage.
- [x] Added per-transaction hash-chained event storage.
- [x] Implemented ledger chain verification for sequence, hash and previous-hash integrity.
- [x] Added SQLite triggers preventing ledger event updates and deletions.
- [x] Added atomic ledger writes alongside transaction status updates.
- [x] Integrated ledger events with dispatch claiming and startup recovery.
- [x] Added tests for chain integrity, tampering, append-only enforcement and transaction-ledger atomicity.

## Running Locally

```bash
source .venv/bin/activate
make run
```

Database migrations run automatically during application startup. The database path defaults to `./data/trustrail.db` and can be overridden with `TR_DB_PATH`:

```bash
TR_DB_PATH=./data/dev.db make run
```

Run tests and development checks:

```bash
pytest
ruff check app tests
mypy app
```

## Directory Structure

```text
TrustRail/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── core/
│   │   └── config.py
│   ├── cli/
│   │   ├── main.py
│   │   └── commands/
│   │       └── ping.py
│   ├── otari/
│   │   ├── client.py
│   │   ├── exceptions.py
│   │   └── mcp.py
│   ├── policy/
│   │   ├── models.py
│   │   ├── parser.py
│   │   └── validator.py
│   ├── authz/
│   │   ├── models.py
│   │   └── engine.py
│   ├── facts/
│   ├── db/
│   │   ├── connection.py
│   │   └── migrations.py
│   ├── txn/
│   │   ├── states.py
│   │   ├── exceptions.py
│   │   ├── transitions.py
│   │   ├── models.py
│   │   └── store.py
│   ├── approvals/
│   ├── ledger/
│   │   ├── models.py
│   │   ├── canonical.py
│   │   ├── hashing.py
│   │   └── store.py
│   ├── agent/
│   ├── reconcile/
│   ├── scenarios/
│   └── fakeotari/
├── mcp_github/
├── mcp_spike/
│   └── server.py
├── tests/
│   ├── conftest.py
│   ├── db/
│   ├── otari/
│   ├── policy/
│   ├── authz/
│   ├── txn/
│   └── ledger/
├── migrations/
│   ├── 001_initial_schema.sql
│   ├── 002_transaction_indexes.sql
│   └── 003_events_append_only.sql
├── scripts/
│   ├── discover_otari_mcp.py
│   └── execute_otari_mcp.py
├── docs/
├── Dockerfile
├── requirements.txt
├── pyproject.toml
├── Makefile
├── .env.example
└── .gitignore
```
