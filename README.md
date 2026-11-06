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
- MCP Python SDK (Streamable HTTP)
- HTTPX (Async GitHub REST API client)
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
- [x] Implemented asynchronous Otari MCP discovery (`Discover(serverID)`) and execution (`Execute(req)`) client.
- [x] Added Pydantic response models and typed MCP error handling.
- [x] Implemented parsing of Otari's shared error response, including `code`, `execution_state` and `request_id`.
- [x] Added typed exception classification for `not_started`, `outcome_unknown` and stale server revisions.
- [x] Captured and preserved the `Otari-Request-ID` response header separately from the request ID in the error body.
- [x] Preserved `Retry-After` metadata when provided.
- [x] Ensured MCP execution makes exactly one HTTP attempt without automatic retries.
- [x] Added unit tests covering error classification, request-ID handling, malformed responses and single-attempt execution.
- [x] Created scripts to verify MCP discovery and tool execution.
- [x] Verified read-only `get_status` execution using a workspace API key.
- [x] Verified MCP server revision detection and stale revision rejection (HTTP 409).
- [x] Added a counting HTTPX transport to verify execution request attempts.
- [x] Configured a 60-second default timeout for the Otari MCP client.
- [x] Ensured the execution client does not use automatic HTTP retries.

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

### Execution Outcome Classification

- [x] Implemented a centralized execution outcome classifier in `app/txn/outcome_classifier.py`.
- [x] Added classification of successful MCP execution responses (`isError: false`) as `SUCCEEDED`.
- [x] Added classification of definitive MCP tool errors (`isError: true`) as `FAILED`.
- [x] Added classification of Otari `not_started` errors as `FAILED_SAFE`.
- [x] Added classification of Otari `outcome_unknown` errors as `INDETERMINATE`.
- [x] Added classification of stale MCP server revision errors (`mcp_server_changed`) as `APPROVAL_INVALIDATED`.
- [x] Added validation for unsupported outcome types.
- [x] Added parameterized unit tests covering all five execution outcome categories and unsupported inputs.
- [x] Verified all outcome classifier tests pass.
### GitHub REST API & MCP Integration

- [x] Created an independent GitHub MCP server package using Python and the MCP SDK.
- [x] Implemented GitHub configuration using Pydantic Settings.
- [x] Configured GitHub Personal Access Token (PAT) through environment variables using `SecretStr`.
- [x] Implemented an asynchronous GitHub REST API client using HTTPX.
- [x] Added GitHub API authentication, version headers and error handling.
- [x] Implemented paginated GitHub API requests.
- [x] Added GitHub response models for issues, labels, users and comments.
- [x] Implemented `list_issues` MCP tool to retrieve repository issues, filter pull requests and calculate inactivity duration.
- [x] Added configurable `demo-ages.json` overrides for deterministic inactivity values during demonstrations, with actual GitHub timestamps as fallback.
- [x] Implemented `get_issue` MCP tool to retrieve complete issue details.
- [x] Implemented `get_issue_activity` MCP tool to inspect issue state, comments and TrustRail transaction markers.
- [x] Implemented `close_issue_with_note` MCP tool to post transaction-marked comments and close GitHub issues.
- [x] Added transaction markers (`trustrail:txn=<txn_id>`) to support execution reconciliation.
- [x] Restricted GitHub operations to the repository configured on the MCP server.
- [x] Exposed GitHub tools through Streamable HTTP.
- [x] Verified GitHub REST API authentication and read operations against the actual repository.
- [x] Manually verified all four MCP tools using MCP Inspector.
- [x] Implemented `get_issue_activity` to inspect issue state, comments and transaction marker occurrences for reconciliation.
### Reconciliation (Initial Implementation)

- [x] Added typed reconciliation evidence and result models.
- [x] Implemented reconciliation outcome classification based on GitHub issue state and transaction-marker counts.
- [x] Added validation to ensure reconciliation evidence matches the requested transaction, repository and issue.
- [x] Implemented the reconciliation engine in `app/reconcile/engine.py`.
- [x] Integrated the engine with `TransactionStore` for atomic reconciliation claims and state transitions.
- [x] Added read-only GitHub activity probing through Otari's MCP execution API.
- [x] Prioritized MCP `structuredContent` when parsing tool responses, with JSON text fallback.
- [x] Preserved Otari Request IDs during reconciliation.
- [x] Added handling for reconciliation probe failures and restoration of uncertain transaction states.
- [x] Implemented the reconciliation API endpoint.

**Pending:**
- [ ] Complete integration with the transaction execution/dispatch workflow.
- [ ] Automatically trigger reconciliation for recovered `INDETERMINATE` transactions.
- [ ] Verify the complete lost-response scenario (`drop_after_apply` → `INDETERMINATE` → reconciliation → `SUCCEEDED`).
- [ ] Verify crash recovery and reconciliation end to end.
- [ ] Verify duplicate-marker and partial-execution scenarios.
### Demo Inactivity Overrides

The GitHub MCP server supports configurable inactivity-day overrides
through `demo-ages.json` for deterministic demonstrations.

Example:

```json
{
  "1": 45,
  "2": 60,
  "3": 12
}
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

The local Fake Otari server can be run independently for manual integration testing:

```bash
python -m app.fakeotari.app
```

It listens on `http://localhost:8001` by default and exposes the same `/api/v1` chat-completion and MCP endpoints used by the production clients.

## Directory Structure

```text
TrustRail/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── core/
│   │   └── config.py
|   ├── api/
|   │   │   ├── __init__.py
|   │   │   └── routes/
|   │   │       ├── __init__.py
|   │   │       └── reconciliation.py
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
│   |   └── outcome_classifier.py
│   ├── approvals/
│   ├── ledger/
│   │   ├── models.py
│   │   ├── canonical.py
│   │   ├── hashing.py
│   │   └── store.py
│   ├── agent/
│   ├── reconcile/
│   │   ├── models.py
│   │   ├── classifier.py
│   │   └── engine.py
│   ├── scenarios/
│   └── fakeotari/
├── mcp_github/
│   ├── __init__.py
│   ├── config.py
│   ├── errors.py
│   ├── models.py
│   ├── client.py
│   └── server.py
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
│   ├── execute_otari_mcp.py
│   └── smoke_github.py
├── docs/
├── demo-ages.json
├── Dockerfile
├── requirements.txt
├── pyproject.toml
├── Makefile
├── .env.example
└── .gitignore
```