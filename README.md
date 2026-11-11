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

### Otari planner usage and budgets

TrustRail's Usage & Budgets screen reads the planner credential (`OTARI_AGENT_API_KEY`)
through the backend-only scoped Otari endpoints:

- `GET /api/v1/key/budget`
- `GET /api/v1/key/usage/summary`
- `GET /api/v1/key/usage/series`

The browser calls TrustRail's `/api/v1/integrations/otari/*` routes and never
contacts Otari or receives an API key. Budget limits, reset times, spend,
requests, tokens, model breakdowns, and series points are rendered from live
responses; unavailable data is shown as unavailable rather than as zero. The
configured base URL must match the key's Otari region (US or EU); a regional
`421` or authentication failure indicates a base URL/key mismatch.

### Otari prompt-injection guardrail

The planner uses the existing organization-level Otari mandate for the
`prompt-injection` profile. Otari applies an organization mandate
automatically to chat-completions requests from its scoped workspace, so
TrustRail does not add a duplicate request-level guardrail. The configured
policy remains `block` with fail-closed (`on_unavailable: block`) behavior.

TrustRail reads the documented `Otari-Guardrails` response header for
successful planner calls and records `GUARDRAIL_EVALUATED` events. A documented
`403` response with `code: guardrail_violation` is recorded as
`GUARDRAIL_BLOCKED`; the planner terminates before tools or proposals can be
created. A mandatory evaluation failure is recorded as `GUARDRAIL_ERROR` and
also terminates planner inference. Authentication, rate-limit, generic
upstream, and network errors remain distinct and are never mislabeled as
prompt-injection detections.

The Run screen exposes the guardrail checkpoint, upstream request ID, profile,
mode, timestamp, and safe reason metadata when Otari supplies it. No API key,
authorization header, issue body, hidden prompt, or model reasoning is stored
in the ledger. A genuine detection can be verified only when Otari returns the
documented `guardrail_violation` response; a generic upstream error is shown
as unavailable/failed rather than as a detection.

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
- [x] Added the `FAILED_SAFE` → `PRECHECK` transition for controlled manual retries.
- [x] Added the `NOT_EXECUTED` → `PROPOSED` transition to initiate fresh authorization.
- [x] Reused the existing `APPROVED` → `PRECHECK` transition for execution after fresh retry approval.
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
- [x] Revalidated approved policy content, facts and MCP revision during PRECHECK, with atomic, ledger-recorded approval invalidation reasons.
- [x] Added concurrent dispatch-claim tests.
- [x] Implemented startup recovery for interrupted transactions (`DISPATCHING` and `RECONCILING` → `INDETERMINATE`).
- [x] Added `recover_on_start_with_ids()` to return the IDs of transactions recovered during startup.
- [x] Preserved the existing `recover_on_start()` count-returning interface.
- [x] Added recovery tests covering multiple transactions, unchanged states and idempotency.
- [x] Added transaction-level persistence of multiple Otari request IDs.
- [x] Implemented ordered, duplicate-free accumulation of request IDs per transaction.
- [x] Persisted request IDs from successful and failed Otari MCP discovery and execution calls whenever an ID is available.

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
- [x] Extended ledger event models to support both transaction-scoped and run-scoped events.
- [x] Enforced mutually exclusive event scopes: every event belongs to exactly one transaction or one run.
- [x] Added migration `005_run_scoped_events.sql` to support run-scoped events while preserving existing transaction-scoped records.
- [x] Added separate sequence constraints and hash chains for transaction-scoped and run-scoped events.
- [x] Generalized `LedgerStore` to append, retrieve and verify events using either `txn_id` or `run_id`.
- [x] Preserved the existing transaction-scoped event hash format for historical compatibility.
- [x] Preserved append-only guarantees through SQLite update and delete triggers.
- [x] Added tests for run-scoped event persistence, sequence ordering, chain verification, tampering and foreign-key enforcement.

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

- [x] Added explicitly gated `demo_allow_duplicate` support to `close_issue_with_note` for the naive executor demonstration.
- [x] Added server-side duplicate-mode protection requiring both the request flag and `TRUSTRAIL_ENABLE_NAIVE_DEMO=true`.
- [x] Preserved normal closed-issue and transaction-marker protections when demo mode is disabled or not explicitly requested.
- [x] Ensured duplicate-mode retries create a new comment without attempting to close an already-closed issue again.
- [x] Added dedicated mocked server tests covering demo-mode authorization and duplicate-execution behavior.

### Reconciliation 

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
- [x] Wired startup recovery into the FastAPI application lifespan after database migrations.
- [x] Initialized the reconciliation engine using the active Otari MCP client during application startup.
- [x] Automatically triggered reconciliation for transactions recovered during the current startup.
- [x] Used the existing read-only reconciliation engine without re-executing the original GitHub write.
- [x] Processed recovered transactions independently so one reconciliation failure does not prevent subsequent attempts.
- [x] Preserved `INDETERMINATE` state when reconciliation cannot obtain sufficient evidence.

### Naive Demo Executor (Comparison Only)

Implemented an explicitly selected, demo-only execution strategy to demonstrate the risks of blindly retrying non-idempotent GitHub operations after an uncertain execution outcome.

The naive executor provides a comparison against TrustRail's secure single-attempt execution path.

**Execution behavior**

- [x] Added an explicit executor selection (`secure` or `naive`) to `TransactionExecutor`.
- [x] Kept `secure` as the default execution mode.
- [x] Restricted naive demo execution to `close_issue_with_note`.
- [x] Implemented a maximum of three total execution attempts: one initial attempt and up to two retries.
- [x] Retry only when the previous execution outcome is `INDETERMINATE`.
- [x] Generate a distinct `client_execution_id` for each attempt.
- [x] Preserve the original approval-bound transaction arguments.
- [x] Pass `demo_allow_duplicate=true` only on subsequent naive retry attempts.
- [x] Keep each individual Otari MCP execution request single-attempt, without automatic HTTP retries.
- [x] Keep the existing secure executor's single-attempt behavior unchanged.

**Duplicate execution demonstration**

The GitHub MCP server supports an explicitly gated duplicate mode for the naive executor.

- [x] Added the `demo_allow_duplicate` argument to `close_issue_with_note`.
- [x] Added the `TRUSTRAIL_ENABLE_NAIVE_DEMO` server configuration flag, disabled by default.
- [x] Require both the request-level opt-in and server-level configuration to enable duplicate execution.
- [x] Preserve closed-issue and transaction-marker protections during normal execution.
- [x] Allow duplicate transaction-marked comments only in explicitly enabled demo mode.
- [x] Avoid attempting to close an issue again when a naive retry encounters an already-closed issue.
- [x] Preserve one GitHub comment creation request per MCP invocation.

**Auditability**

- [x] Record individual naive demo execution attempts in the transaction-scoped hash-chained ledger.
- [x] Record attempt number, maximum attempts, client execution ID, outcome, Otari request ID and duplicate-mode flag.
- [x] Preserve the existing transaction attempt counter used by the controlled retry workflow.

**Server configuration**

The duplicate-execution demonstration is disabled by default.

Enable it only in the dedicated demo GitHub MCP server environment:

```env
TRUSTRAIL_ENABLE_NAIVE_DEMO=true
```

The setting must remain disabled in normal deployments.

**Testing**

- [x] Added server tests for normal execution and duplicate-protection behavior.
- [x] Verified that a demo request is rejected when the server-level flag is disabled.
- [x] Verified that enabling the server flag alone does not bypass duplicate protections.
- [x] Verified that explicitly enabled demo mode permits duplicate comments.
- [x] Verified that an already-closed issue is not closed again during a naive retry.
- [x] Verified that each MCP invocation creates at most one comment.
- [x] Verified all tests in `tests/mcp_github/test_server_naive_demo.py` pass.

**Pending end-to-end verification**

- [ ] Demonstrate the naive executor producing duplicate comments using `drop_after_apply`.
- [ ] Verify that the secure executor produces only one comment under the same lost-response scenario.
- [ ] Compare the resulting transaction states, GitHub comments and audit ledger events.

**Pending:**


- [ ] Complete end-to-end verification of the reconciliation workflow.

- [ ] Verify the complete lost-response scenario (`drop_after_apply` → `INDETERMINATE` → reconciliation → `SUCCEEDED`).
- [ ] Verify crash recovery and reconciliation end to end.
- [ ] Verify duplicate-marker and partial-execution scenarios.

### Demo Inactivity Overrides

The GitHub MCP server supports configurable inactivity-day overrides through `demo-ages.json` for deterministic demonstrations.

- [x] Added automatic generation of `demo-ages.json` through `scripts/seed_sandbox.py`.
- [x] Mapped actual GitHub issue numbers to their configured inactivity durations.
- [x] Preserved actual GitHub timestamps as the fallback when an issue has no configured override.
#### Safe Transaction Retry

Implemented a controlled retry workflow for transactions that are known not to have completed successfully.

**Retry eligibility and behavior**

- [x] Added `POST /api/v1/transactions/{transaction_id}/retry`.
- [x] Implemented manual retry from `FAILED_SAFE` using the existing approval.
- [x] Revalidate current policy, GitHub facts and MCP server revision through the existing transaction executor before dispatch.
- [x] Implemented retry preparation from `NOT_EXECUTED` by clearing the active authorization snapshot and detaching the previous approval.
- [x] Preserved historical approval records rather than deleting or overwriting them.
- [x] Re-evaluated policy using fresh GitHub facts for `NOT_EXECUTED` retries.
- [x] Required a fresh human approval for `NOT_EXECUTED` retries, including when the ordinary policy decision is `ALLOW`.
- [x] Bound the new approval to the fresh authorization facts, policy content and MCP server revision.
- [x] Verified that execution after fresh approval follows the existing `APPROVED` → `PRECHECK` → `DISPATCHING` flow.
- [x] Added atomic retry preparation and attempt-count updates.
- [x] Recorded retry preparation and execution preparation as hash-chained ledger events.
- [x] Kept GitHub write execution inside `TransactionExecutor`, preserving its atomic dispatch claim and single-attempt execution behavior.

**Retry safety rules**

- `FAILED_SAFE`: manual retry with the existing approval and fresh PRECHECK.
- `NOT_EXECUTED`: fresh authorization, fresh human approval and fresh PRECHECK.
- `PRECHECK`: permits resuming a retry after a recoverable pre-dispatch error.
- `INDETERMINATE`: cannot be retried directly; reconciliation is required first.
- `UNRESOLVED` and `DUPLICATE_DETECTED`: cannot be retried directly.
- `SUCCEEDED` and definitive `FAILED`: are not retryable.


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
- [x] Implemented `ApprovalService` to create hash-bound approval decisions.
- [x] Added `POST /api/v1/transactions/{transaction_id}/approve`.
- [x] Added `POST /api/v1/transactions/{transaction_id}/reject`.
- [x] Enforced strict request validation and rejected client-supplied binding hashes.
- [x] Persisted approval decisions, transaction state changes and ledger events atomically.
- [x] Added service tests for approval and rejection workflows and invalid transaction states.
- [x] Added API tests covering successful decisions, missing transactions, conflicts and invalid requests.
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

### Lost-response recovery — End-to-End Verification

`scripts/e2e_lost_response_recovery.py` verifies recovery from a response that
is lost after GitHub has applied the write. It prepares the seeded `issue-04`
sandbox issue, creates and policy-authorizes a `close_issue_with_note`
transaction, records an approval through `ApprovalService`, and enables the
GitHub MCP server's authenticated `drop_after_apply` fault mode. The real
executor makes one write call; the injected server applies the comment and
issue close, then drops the response. The transaction therefore progresses
through:

```text
APPROVED → DISPATCHING → INDETERMINATE → RECONCILING → SUCCEEDED
```

Reconciliation uses Otari discovery and only the read-only
`get_issue_activity` tool. The script independently checks that the issue is
closed and that the transaction marker occurs in exactly one comment and
exactly once overall. It also checks that the original write tool was called
once, reconciliation never called it, the expected ledger events exist, and
the transaction hash chain verifies.

Prerequisites:

- The sandbox repository is configured through `MCP_GITHUB_REPO` and has the
  `TRUSTRAIL_ADMIN_TOKEN` and `MCP_GITHUB_PAT` credentials.
- Otari is configured with `OTARI_BASE_URL`, `OTARI_API_KEY`, and
  `OTARI_MCP_SERVER_ID`.
- `MCP_GITHUB_SERVER_URL` points to the GitHub MCP server that exposes
  `/admin/fault`; the server must accept the configured admin token.
- The deployed container must start `mcp_github.server` (the repository
  Dockerfile is configured accordingly); deploying `mcp_spike.server` does not
  provide the GitHub write tools or `/admin/fault`.
- The database contains the active `demo-close-issue-policy` v1. The script
  calls the existing sandbox seeding helper and safely resets the selected
  seeded issue before verification.

Run it from the repository root:

```bash
python -m scripts.e2e_lost_response_recovery
```

The script resets the MCP fault mode to `none` in a `finally` block. It does
not retry the uncertain write or delete the resulting evidence after
the verification. **Verification status:** an execution was attempted on
2026-11-10. Sandbox seeding and reset, transaction creation, policy
evaluation, approval, and the GitHub write completed, but the transaction
returned `SUCCEEDED` instead of `INDETERMINATE` because the deployed container
was running `mcp_spike.server`, not `mcp_github.server`. The Dockerfile has been
corrected; the external MCP deployment must be rebuilt and redeployed before a
successful lost-response recovery can be claimed. A successful run prints the
transaction ID, marker, each verification step, and a final success summary.
Any failed
assertion exits non-zero.
### Run-Scoped Read-Tool Audit Events

Implemented lightweight audit logging for read-only tools invoked during an agent run.

The `AgentToolDispatcher` is responsible for recording read-tool execution events using the trusted `run_id` supplied by the orchestrator.

Only the following tools generate `READ_TOOL_CALL` events:

- `list_issues`
- `get_issue`

The `propose_close` tool is intentionally excluded because it creates a proposed transaction rather than performing a read operation.

#### Event contents

Each read-tool event records:

- Tool name.
- Validated tool arguments.
- Execution outcome (`SUCCEEDED` or `FAILED`).
- Safe error metadata when execution fails.
- Run identifier.
- Event sequence and hash-chain metadata.

Only validated arguments and minimal execution metadata are persisted. Secrets, authentication tokens and sensitive MCP response data are not included.

#### Execution behavior

- [x] Added read-tool classification in `AgentToolDispatcher`.
- [x] Added run-scoped `READ_TOOL_CALL` event creation.
- [x] Logged successful read-tool executions.
- [x] Logged failed read-tool executions.
- [x] Used the trusted orchestrator-provided `run_id`, rather than accepting a run identifier from model-generated arguments.
- [x] Kept `propose_close` outside read-tool audit logging.
- [x] Prevented successful read results from being returned as normal success when audit persistence fails.
- [x] Avoided automatic retries of external read operations after audit persistence failures.

#### Production integration

The FastAPI application initializes the shared `LedgerStore` during its lifespan.

The same instance is injected into `AgentToolDispatcher`, ensuring read-tool events use the application's configured SQLite database.

The production dependency flow is:

`FastAPI lifespan → LedgerStore → AgentToolDispatcher → AgentToolHandlers`

The `AgentOrchestrator` supplies the trusted run identifier when dispatching model-requested tool calls.

#### Testing

- [x] Added dispatcher unit tests for read-tool audit behavior.
- [x] Added SQLite-backed dispatcher integration tests using the actual `LedgerStore`.
- [x] Verified successful `list_issues` and `get_issue` event persistence.
- [x] Verified multiple read events receive sequential sequence numbers within a run.
- [x] Verified run-scoped events persist across database reopening.
- [x] Verified run-scoped hash-chain integrity.
- [x] Verified independent event chains for separate runs.
- [x] Verified failed read operations generate audit events.
- [x] Verified `propose_close` does not generate `READ_TOOL_CALL` events.
- [x] Verified audit persistence failures do not expose read results as normal successful responses.
- [x] Verified no automatic external read retry occurs after audit persistence failure.
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

### Natural-Language Policy Compiler

- [x] Added a compiler system prompt requiring JSON-only output and the fixed `PolicyDraft` schema.

- [x] Defined the supported compiler response shapes: a policy draft or an `ambiguous` response containing clarification questions.

- [x] Added strict compiler-response parsing and Pydantic schema validation; unexpected fields and malformed responses are rejected rather than repaired.

- [x] Added policy-draft completeness validation so missing security-relevant values are not silently guessed.

- [x] Added deterministic policy construction in Python, supplying system-controlled fields such as repository, schema version, action limits and audit configuration.

- [x] Integrated the compiler with the asynchronous Otari chat-completions client.

- [x] Added a real Otari integration script at `scripts/test_policy_compiler.py`; it exercises clear, ambiguous and adversarial policy requests without performing GitHub writes.

- [x] Verified all three integration scenarios using `deepseek/deepseek-v4-pro-0813`: clear policy extraction, clarification for an underspecified request, and rejection of an attempted schema override while retaining the legitimate policy instructions.
- [x] Added deterministic plain-English policy summary generation using Python, based exclusively on the final validated `Policy`.
- [x] Integrated policy summary generation into `PolicyCompiler`.
- [x] Added a structured compiler response containing both the validated policy and its generated summary.
- [x] Extended real Otari integration tests to verify summary accuracy for clear and adversarial policy requests.
- [x] Verified all three compiler scenarios (clear, ambiguous and adversarial), with summary validation passing for successful compilations.
#### Production API Integration

- [x] Added `POST /api/v1/policies/compile` through `app/api/routes/policy_compilation.py`.
- [x] Added strict request validation using Pydantic with `extra="forbid"`.
- [x] Integrated `PolicyCompiler` into the FastAPI application lifespan.
- [x] Configured the production compiler to use `settings.tr_compiler_model`.
- [x] Reused the shared asynchronous `OtariClient` rather than creating a separate gateway integration.
- [x] Made policy compilation independent of GitHub MCP server configuration.
- [x] Added structured handling for successful compilation and ambiguous requests.
- [x] Added HTTP error mapping for Otari connection, timeout, authentication, API and response errors.
- [x] Prevented API callers from overriding the configured model or routing policy.
- [x] Verified successful policy compilation through the production API.
- [x] Verified ambiguous-request handling and rejection of unexpected request fields.

Policy compilation only produces a validated policy and summary. It does not automatically activate the policy, authorize an action or execute GitHub operations.
The transaction was independently verified against GitHub and its corresponding database records and audit ledger.

Note: This verifies the successful execution path. It does not establish a universal exactly-once execution guarantee.

### Agent planner workflow

The planner in `app/agent/orchestrator.py` sends the configured
`TR_PLANNER_MODEL` a system prompt, the user's request, and exactly three
model-facing tools:

- `list_issues()` (no arguments)
- `get_issue(issue_number: positive integer)`
- `propose_close(issue_number: positive integer, reason: 1-1000 characters)`

`AgentToolDispatcher` maintains this static allowlist, validates strict Pydantic
arguments, and routes calls to `AgentToolHandlers`. The model never sees
`close_issue_with_note`; `propose_close` only creates a `PROPOSED` transaction.
The orchestrator supplies the trusted `run_id` separately, appends OpenAI-style
assistant tool-call and matching `tool` messages, and then continues the
conversation. GitHub issue content is treated as untrusted data.

Each run is bounded by `TR_AGENT_MAX_ITERATIONS`,
`TR_AGENT_MAX_TOOL_CALLS`, and `TR_AGENT_MAX_COMPLETION_TOKENS`. The
`TR_AGENT_TOKEN_BUDGET` is enforced using provider-reported usage fields
(`total_tokens` when available), accumulated across requests. If usage metadata
is absent or malformed, the per-request completion cap and loop limits still
apply; TrustRail does not invent token counts. Provider errors are surfaced,
while tool validation and execution failures are returned to the model as
structured errors. Results identify the run, counts, provider usage, and
termination reason.

The dispatcher and planner loop are covered by `tests/agent/`; tool-call
response validation is covered by `tests/otari/`. Existing approval, policy,
transaction, and ledger paths remain the only route to an actual GitHub write.

### Proposal evaluation

After a proposal is created, `ProposalEvaluationService` independently loads the transaction's policy and retrieves the issue through the read-only `list_issues` MCP tool. It passes only validated ground-truth facts to the existing deterministic authorization engine; model-provided claims are never authorization evidence.

The resulting `ALLOW`, `REQUIRES_APPROVAL`, `DENY`, or `POLICY_INVALID` decision is persisted with its reasons, complete facts snapshot, policy version, discovered Otari MCP `server_revision`, and evaluation timestamp.

For `REQUIRES_APPROVAL` decisions, the transaction transitions to `PENDING_APPROVAL`. The persisted facts snapshot includes the verified repository and relevant issue attributes, while `server_revision` records the exact MCP server configuration revision used for the ground-truth facts request.

Decision persistence is atomic with the transaction status transition and an `AUTHORIZATION_DECISION` ledger event. The event records the action arguments, run identifier, policy version, complete facts snapshot, discovered server revision, decision, and machine-readable reasons. These records remain part of the existing hash-chained audit ledger.

Evaluation is idempotent: an already evaluated transaction retains its original authorization decision and evidence rather than being evaluated and persisted again.

No human approval record is created during proposal evaluation. Approval creation and verification remain separate workflows. Proposal evaluation never invokes `close_issue_with_note` or performs a GitHub write.
**Implementation and verification**

- [x] Implemented `ProposalEvaluationService` for independent proposal evaluation.
- [x] Retrieved authoritative GitHub issue facts through Otari's read-only `list_issues` MCP tool.
- [x] Captured the discovered `server_revision` used for the facts request.
- [x] Persisted the complete facts snapshot, including repository and issue attributes.
- [x] Persisted `server_revision` alongside the authorization decision.
- [x] Transitioned `REQUIRES_APPROVAL` decisions to `PENDING_APPROVAL`.
- [x] Persisted authorization decisions, facts and server revision atomically with the transaction state transition and ledger event.
- [x] Included the facts snapshot and server revision in the `AUTHORIZATION_DECISION` event.
- [x] Preserved original authorization evidence on repeated evaluation.
- [x] Added tests for ground-truth persistence, ledger integrity and evaluation idempotency.
- [x] Verified both proposal evaluation tests pass.
Available commands:
```bash
# Compile a policy, run the planner, and evaluate proposals
trustrail run \
  --policy "Only close GitHub issues inactive for at least 30 days and with no P0 or P1 label." \
  --request "Find stale issues in the configured repository and propose closing eligible ones."
```

### Policy Dry-run

- [x] Added typed dry-run response models in `app/dryrun/models.py`.
- [x] Implemented the dry-run service in `app/dryrun/service.py`.
- [x] Integrated dynamic Otari MCP tool discovery before fetching issue facts.
- [x] Restricted dry-run execution to the read-only `list_issues` tool.
- [x] Retrieved all repository issues using `state="all"` through Otari MCP.
- [x] Added validation of returned issue facts and repository matching.
- [x] Reused the existing deterministic authorization engine to evaluate each issue.
- [x] Added per-issue decisions and reasons to the dry-run response.
- [x] Added aggregate counts for allowed, approval-required, denied and policy-invalid decisions.
- [x] Kept dry-run independent of transaction execution, approval creation and ledger writes.
- [x] Exposed the functionality through `POST /api/v1/policies/dryrun`.
- [x] Added unit tests covering successful evaluation, read-only tool usage, repository mismatch, Otari errors and malformed facts.
- [x] Verified the endpoint against the live GitHub sandbox through the hosted Otari MCP gateway.
```bash
# Seed the GitHub sandbox
trustrail seed

# List open issues
trustrail issues

# List all issues
trustrail issues --state all

# Filter by priority
trustrail issues --state open --label P1
```

### Complete agent workflow

`trustrail run` compiles the natural-language policy through
`TR_COMPILER_MODEL`, validates the strict schema, persists a run context, and
invokes the planner through `OTARI_AGENT_API_KEY` and `TR_PLANNER_MODEL`. The
planner can only call `list_issues`, `get_issue`, and `propose_close`.
Read calls are recorded in the run-scoped hash-chained ledger. Each proposal
is persisted without executing a write, then authoritative GitHub facts are
retrieved through Otari and evaluated by the deterministic authorization
engine. Decisions, reasons, facts, transaction states, model routing, and
summary counts are printed.

The command requires the configured Otari, GitHub, model, and MCP variables,
including `OTARI_BASE_URL`, `OTARI_API_KEY`, `OTARI_AGENT_API_KEY`,
`OTARI_MCP_SERVER_ID`, `TR_COMPILER_MODEL`, `TR_PLANNER_MODEL`, and
`MCP_GITHUB_REPO`. `TR_DB_PATH` defaults to `./data/trustrail.db`.
Compilation ambiguity, invalid policies, unavailable facts, planner/tool
errors, and ledger failures stop or fail closed with a non-zero exit status.
No GitHub write or approval is performed; proposals requiring approval remain
`PENDING_APPROVAL`.

Representative output:

```text
[20:14:05] [TrustRail] [INFO] Starting agent run.
[20:14:06] [TrustRail] [INFO] Policy compiled and validated successfully.
[20:14:06] [TrustRail] [INFO] Run context persisted. Run ID: <run-id>
[20:14:07] [TrustRail] [INFO] Planner iteration 1 completed.
[20:14:07] [TrustRail] [INFO] Dispatching tool call 1: list_issues.
[20:14:08] [TrustRail] [INFO] Tool call 1 completed: list_issues.
[20:14:09] [TrustRail] [INFO] Planner completed; loading persisted proposals.
Run
  ID                 : <run-id>
  Completion         : completed
Compiled policy
  Status             : validated
Proposal decisions
    Decision         : REQUIRES_APPROVAL
    Status           : PENDING_APPROVAL
Summary
  Proposals         : 1
  Requires approval : 1
  Execution         : no GitHub writes were executed
```

Progress logs are printed immediately with timestamps and cover configuration
and database setup, policy compilation and validation, run persistence,
planner iterations, every allowed tool dispatch and completion, proposal
evaluation, proposal loading, and final ledger persistence. Errors use the
same format with an `ERROR` level. Logs contain IDs, models, tool names, and
statuses, but never API keys or raw credentials.

The workflow is covered by the existing unit suite and
`tests/cli/test_run_command.py`. Run `pytest`, `ruff check app tests`, and
`mypy app`; current repository-wide results include pre-existing Ruff/MyPy
findings and a pre-existing transition test failure, which are reported
without weakening those checks.

## Running Locally
### Otari Model Routing Policies

Configured two named routing policies in the Otari dashboard to separate planner and policy-compilation workloads while using a single Otari gateway.

#### Planner routing — `trustrail-planner`

- [x] Created the `trustrail-planner` routing policy in the Otari dashboard.
- [x] Configured DeepSeek V4 Flash as the cost-efficient default model.
- [x] Configured DeepSeek V4 Pro 0813 as the stronger `on_failure` fallback.
- [x] Verified that TrustRail loads the routing policy name through `TR_PLANNER_MODEL`.
- [x] Integrated the routing policy with `AgentOrchestrator`.

#### Compiler routing — `trustrail-compiler`

- [x] Created the `trustrail-compiler` routing policy in the Otari dashboard.
- [x] Configured Qwen3-30B-A3B-Instruct-2507 through Nebius as the default model.
- [x] Configured a DeepSeek V4 Pro 0813 fallback.
- [x] Verified compiler inference through the Otari gateway using the routing policy name.
- [x] Integrated the routing policy with `PolicyCompiler`.
- [x] Verified policy compilation through the production FastAPI endpoint.

#### Application configuration

The application uses Otari routing policy names rather than individual provider/model identifiers:

```env
TR_PLANNER_MODEL=trustrail-planner
TR_COMPILER_MODEL=trustrail-compiler
```

The underlying model and provider selection is managed by Otari. TrustRail does not need provider-specific model selection logic.

Both routing policies use the same Otari chat-completions gateway, demonstrating multi-model and multi-provider routing through a unified integration.

Routing policy names must not contain `:` or `/`.
### Dedicated Planner API Key & Budget

Configured a dedicated Otari API key for agent planner inference to isolate planner usage from policy compilation.

**Credential configuration**

| Environment variable | Responsibility |
|---|---|
| `OTARI_API_KEY` | Policy compiler and existing Otari MCP operations |
| `OTARI_AGENT_API_KEY` | Agent planner chat-completion requests |

**Planner configuration**

- Created the Otari virtual API key `agent-run`.
- Configured a $4 monthly per-key spending limit.
- The key-level limit applies within the existing $20 hackathon-provided Otari allocation; it does not create additional credits.
- Kept `TR_PLANNER_MODEL=trustrail-planner`.
- Planner inference uses `OTARI_AGENT_API_KEY`.
- Policy compilation continues using `OTARI_API_KEY` and `TR_COMPILER_MODEL=trustrail-compiler`.
- Updated `OtariClient` to support an optional API-key override while preserving the existing default credential behavior.
- Injected separate Otari chat clients into `AgentOrchestrator` and `PolicyCompiler`.
- Kept the existing Otari MCP client configuration unchanged.

**Verification**

- [x] Added `OTARI_AGENT_API_KEY` to application settings.
- [x] Updated `.env.example`.
- [x] Added optional API-key injection to `OtariClient`.
- [x] Wired a dedicated planner client into `AgentOrchestrator`.
- [x] Preserved the existing compiler client configuration.
- [x] Ruff checks passed.
- [x] MyPy checks passed.
- [x] Pytest suite passed.


**Architecture:**

- Planner: DeepSeek V4 Flash → DeepSeek V4 Pro 0813 fallback.
- Compiler: Qwen3-30B-A3B-Instruct-2507 (Nebius) → DeepSeek V4 Pro 0813 fallback.
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
|   |   │       └── dryrun.py
|   |   │       └── policy_compilation.py
├   |   |       |── retry.py
│   ├── cli/
│   │   ├── main.py
│   │   └── commands/
│   │       ├── ping.py
│   │       ├── seed.py
│   │       └── issues.py
|   ├── dryrun/
|   │   ├── __init__.py
|   │   ├── models.py
|   │   └── service.py
│   ├── facts/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   └── github.py
│   ├── otari/
│   │   ├── client.py
│   │   ├── exceptions.py
│   │   ├── mcp.py
│   │   └── response_validation.py
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── dispatcher.py
│   │   ├── models.py
│   │   ├── orchestrator.py
│   │   ├── evaluation.py
│   │   ├── proposal_service.py
│   │   ├── tool_handlers.py
│   │   └── tools.py
│   ├── policy/
│   │   ├── models.py
│   │   ├── parser.py
│   │   └── validator.py
│   │   └── compiler_builder.py
│   │   └── compiler_models.py
│   │   └── compiler_parser.py
│   │   └── compiler_validation.py
│   │   └── compiler.py
│   │   └── prompts.py
│   │   └── summary.py
│   │   └── validator.py
│   ├── authz/
│   │   ├── models.py
│   │   └── engine.py
│   ├── facts/
│   │   ├── github.py
│   │   └── models.py
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
│   │   └── service.py
│   ├── ledger/
│   │   ├── models.py
│   │   ├── canonical.py
│   │   ├── hashing.py
│   │   └── store.py
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
│   ├── agent/
│   │   ├── test_dispatcher.py
│   │   ├── test_evaluation.py
│   │   ├── test_orchestrator.py
│   │   ├── test_proposal_service.py
│   │   ├── test_propose_close_handler.py
│   │   ├── test_tool_handlers.py
│   │   └── test_tools.py
│   ├── db/
│   ├── otari/
│   ├── policy/
│   ├── authz/
│   ├── txn/
│   └── ledger/
|   └── dryrun/
├── migrations/
│   ├── 001_initial_schema.sql
│   ├── 002_transaction_indexes.sql
│   ├── 003_events_append_only.sql
│   ├── 004_authorization_decisions.sql
│   └── 005_run_scoped_events.sql
├── scripts/
│   ├── discover_otari_mcp.py
│   ├── execute_otari_mcp.py
│   ├── smoke_github.py
│   └── seed_sandbox.py
│   └── demo_reset.py
│   └── verify_github_write.py
│   ├── demo_real_write.py
│   ├── verify_transaction_ledger.py
│   ├── test_policy_compiler.py
├── docs/
├── demo-ages.json
├── Dockerfile
├── requirements.txt
├── pyproject.toml
├── Makefile
├── .env.example
└── .gitignore
```