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
- [x] Added `trustrail seed` CLI command to seed the configured GitHub sandbox repository.
- [x] Reused the existing idempotent sandbox seeding implementation.
- [x] Added `trustrail issues` CLI command to retrieve issue facts through Otari MCP.
- [x] Integrated MCP tool discovery to identify the registered GitHub server's available tools.
- [x] Executed the read-only `list_issues` tool through Otari using the discovered server revision.
- [x] Added issue state and label filtering to the CLI.
- [x] Added typed issue-fact models and response validation.
- [x] Displayed repository, issue number, title, state, priority, labels and inactivity duration.
- [x] Verified the complete TrustRail → Otari → GitHub MCP → GitHub REST API flow.

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
- [x] Implemented `reopen_issue()` to reopen GitHub issues.
- [x] Implemented `delete_issue_comment()` to delete specific issue comments.
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

- [x] Complete end-to-end verification of the real GitHub transaction execution workflow.
- [ ] Complete end-to-end verification of the reconciliation workflow.
- [ ] Automatically trigger reconciliation for recovered `INDETERMINATE` transactions.
- [ ] Verify the complete lost-response scenario (`drop_after_apply` → `INDETERMINATE` → reconciliation → `SUCCEEDED`).
- [ ] Verify crash recovery and reconciliation end to end.
- [ ] Verify duplicate-marker and partial-execution scenarios.

### Demo Inactivity Overrides

The GitHub MCP server supports configurable inactivity-day overrides through `demo-ages.json` for deterministic demonstrations.

- [x] Added automatic generation of `demo-ages.json` through `scripts/seed_sandbox.py`.
- [x] Mapped actual GitHub issue numbers to their configured inactivity durations.
- [x] Preserved actual GitHub timestamps as the fallback when an issue has no configured override.

The generated JSON follows this structure:

```json
{
  "<actual_github_issue_number_1>": 45,
  "<actual_github_issue_number_2>": 60,
  "<actual_github_issue_number_3>": 12
}
```

The complete generated file contains inactivity overrides for all 10 seeded issues.
### Fault Injection & Admin Control

- [x] Implemented configurable fault modes using a dedicated `FaultMode` enum:
  - `none`: Normal GitHub write execution.
  - `fail_before_apply`: Injects a failure before any GitHub write.
  - `partial`: Creates the transaction-marked comment but fails before closing the issue.
  - `drop_after_apply`: Applies the GitHub write but deliberately drops the MCP HTTP response.
  - `delay_after_apply`: Delays the response after the GitHub write has been applied.
- [x] Implemented a thread-safe, asynchronous `FaultController` with one-shot fault consumption.
- [x] Added an authenticated `POST /admin/fault` endpoint to configure fault-injection modes.
- [x] Protected the admin endpoint using Bearer-token authentication with constant-time token comparison.
- [x] Added request-scoped response-drop handling using Python `ContextVar` to isolate concurrent MCP requests.
- [x] Implemented ASGI middleware to buffer and deliberately drop MCP HTTP responses for the `drop_after_apply` scenario.
- [x] Kept the admin endpoint separate from MCP tool discovery and execution.
- [x] Verified admin endpoint authentication and fault-mode configuration.
- [x] Verified transaction-marker creation and retrieval through GitHub issue activity.
### GitHub Sandbox Seeding

- [x] Extended `GitHubClient` with `list_labels()` to retrieve repository labels.
- [x] Added `create_label()` to create repository labels with validated names and hexadecimal colors.
- [x] Added `create_issue()` to create GitHub issues with titles, descriptions and labels.
- [x] Implemented `scripts/seed_sandbox.py` to populate the configured GitHub sandbox repository.
- [x] Defined a deterministic dataset of 10 software-engineering issues.
- [x] Created the required priority labels (`P0`, `P1`, `P2`, `P3`).
- [x] Added realistic issue titles and descriptions for all seeded issues.
- [x] Included a prompt-injection example in issue #9 to test resistance to untrusted issue content.
- [x] Left issue #10 without a priority label to test fail-closed authorization.
- [x] Added unique seed markers to identify previously created issues and prevent duplicate creation on reruns.
- [x] Generated `demo-ages.json` using actual GitHub issue numbers and their configured inactivity-day overrides.
- [x] Successfully executed the seeding script against the configured GitHub repository.
### Demo Environment Reset

- [x] Added `reopen_issue()` to `GitHubClient` to reopen previously closed GitHub issues.
- [x] Added `delete_issue_comment()` to remove specific GitHub issue comments.
- [x] Implemented `scripts/demo_reset.py` to restore the GitHub sandbox to a clean demonstration state.
- [x] Identified seeded issues using their unique `trustrail-seed` markers.
- [x] Added validation to detect missing or duplicate seeded issues before resetting.
- [x] Reopened all closed seeded issues while leaving already-open issues unchanged.
- [x] Removed only TrustRail transaction-marked comments, preserving ordinary comments and seed markers.
- [x] Restored `demo-ages.json` using actual GitHub issue numbers and configured inactivity values.
- [x] Reset the GitHub MCP server fault-injection mode to `none` through the authenticated admin endpoint.
- [x] Added post-reset verification to ensure all seeded issues are open and transaction comments have been removed.
- [x] Made the reset operation idempotent so it can be safely executed multiple times.
### Otari-Backed Issue Facts CLI

- [x] Implemented `trustrail issues` to retrieve GitHub issue facts through the Otari gateway.
- [x] Added MCP discovery before tool execution.
- [x] Restricted the CLI to the explicitly allowlisted read-only `list_issues` tool.
- [x] Passed the discovered `server_revision` during MCP execution.
- [x] Added support for filtering issues by state (`open`, `closed`, `all`) and labels.
- [x] Parsed and validated structured MCP responses into typed issue-fact models.
- [x] Added JSON text-content fallback when structured content is unavailable.
- [x] Displayed issue priority and inactivity duration alongside other issue attributes.
- [x] Ensured issue retrieval does not bypass Otari through direct GitHub REST API calls.
### Approval Management & Transaction Execution

- [x] Implemented typed approval models with `APPROVE` and `REJECT` decisions.
- [x] Implemented deterministic SHA-256 approval binding using canonical JSON.
- [x] Bound approvals to the exact tool, arguments, policy version, authorization facts and Otari server revision.
- [x] Implemented SQLite-backed `ApprovalStore` for approval creation, retrieval and verification.
- [x] Added approval verification to reject mismatched transactions, rejected decisions and modified action bindings.
- [x] Implemented the transaction executor in `app/txn/executor.py`.
- [x] Integrated deterministic policy evaluation with transaction execution.
- [x] Integrated read-only GitHub fact resolution through Otari MCP before authorization.
- [x] Added approval verification before proceeding with an authorized write.
- [x] Added fresh fact and MCP server revision checks before dispatch.
- [x] Integrated atomic `PRECHECK` → `DISPATCHING` transaction claiming.
- [x] Integrated single-attempt Otari MCP write execution without automatic retries.
- [x] Added Otari request ID persistence for transaction execution.
- [x] Integrated execution outcome classification into the transaction executor.
- [x] Added approval-store unit tests covering creation, verification, rejection and binding mismatches.
### Real GitHub Write — End-to-End Verification

- [x] Created a fresh transaction using the active `demo-close-issue-policy` (v1).
- [x] Executed a real GitHub issue-close operation through the TrustRail executor and Otari MCP.
- [x] Verified policy evaluation and the `PENDING_APPROVAL` transition.
- [x] Created an approval bound to the exact tool, arguments, policy version, authorization facts and MCP server revision.
- [x] Verified the executor's fresh-facts precheck before dispatch.
- [x] Verified atomic `PRECHECK` → `DISPATCHING` dispatch claim.
- [x] Executed the GitHub write through a single Otari MCP execution attempt.
- [x] Persisted the Otari request ID in the transaction record.
- [x] Independently verified the GitHub issue state and transaction marker through `get_issue_activity`.
- [x] Verified exactly one transaction marker was present on the GitHub issue.
- [x] Verified the transaction, approval and six ledger events were persisted in SQLite.
- [x] Verified ledger hash-chain integrity using `LedgerStore.verify_chain()`.

**Verified demonstration:**

| Attribute | Result |
|---|---|
| Repository | `iamgoeldhruv/LimeDraw` |
| Issue | #4 |
| Transaction status | `SUCCEEDED` |
| GitHub issue state | `closed` |
| Matching transaction markers | 1 |
| Approval decision | `APPROVE` |
| Ledger events | 6 |
| Ledger integrity | Valid |

**Transaction ID:**
`a6a29b66-513d-4ec6-9b60-4d07d3a98e47`

**Otari write request ID:**
`req_103e75bc664d46e3a7373615197838cb`

**Otari verification request ID:**
`req_710d926415294802a2b9271782a167ef`

**GitHub matching comment ID:**
`6710349235`

The transaction was independently verified against GitHub and its corresponding database records and audit ledger.

Note: This verifies the successful execution path. It does not establish a universal exactly-once execution guarantee.
Available commands:

```bash
# Seed the GitHub sandbox
trustrail seed

# List open issues
trustrail issues

# List all issues
trustrail issues --state all

# Filter by priority
trustrail issues --state open --label P1
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
|   │   ├── cli/
|   │   │   ├── main.py
|   │   │   └── commands/
|   │   │       ├── ping.py
|   │   │       ├── seed.py
|   │   │       └── issues.py
│   ├── facts/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   └── github.py
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
│   │   ├── store.py
│   │   ├── executor.py
│   │   └── outcome_classifier.py
│   │
│   ├── approvals/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── hashing.py
│   │   └── store.py
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
|   ├── fault_injection.py
|   ├── middleware.py
|   └── admin_models.py
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
│   ├── smoke_github.py
│   └── seed_sandbox.py
│   └── demo_reset.py
│   └── verify_github_write.py
│   ├── demo_real_write.py
│   ├── verify_transaction_ledger.py
├── docs/
├── demo-ages.json
├── Dockerfile
├── requirements.txt
├── pyproject.toml
├── Makefile
├── .env.example
└── .gitignore
```