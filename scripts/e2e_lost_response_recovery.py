from __future__ import annotations

import asyncio
import hashlib
import subprocess
import sys
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import httpx
from pydantic import SecretStr

from app.approvals.models import ApprovalDecision
from app.approvals.service import ApprovalService
from app.approvals.store import ApprovalStore
from app.core.config import settings
from app.db.connection import get_connection
from app.ledger.canonical import canonical_json
from app.ledger.store import LedgerStore
from app.otari.mcp import (
    MCPDiscoveryResponse,
    MCPExecutionResponse,
    OtariMCPClient,
)
from app.reconcile.engine import ReconciliationEngine
from app.reconcile.models import IssueActivityEvidence
from app.txn.executor import ApprovalRequiredError, TransactionExecutor
from app.txn.models import TransactionCreate
from app.txn.states import TransactionState
from app.txn.store import TransactionStore
from mcp_github.client import GitHubClient
from mcp_github.config import GitHubSettings
from mcp_github.fault_injection import FaultMode

POLICY_ID = "demo-close-issue-policy"
POLICY_VERSION = 1
SEED_KEY = "issue-04"
WRITE_TOOL = "close_issue_with_note"
READ_TOOL = "get_issue_activity"
SEED_MARKER = "<!-- trustrail-seed:issue-04 -->"


class CountingOtariClient(OtariMCPClient):
    """Count tool calls made through the real Otari client without changing dispatch."""

    def __init__(self, client: OtariMCPClient) -> None:
        self._wrapped_client = client
        self.calls: list[str] = []

    async def discover(self, server_id: str) -> MCPDiscoveryResponse:
        return await self._wrapped_client.discover(server_id)

    async def execute(
        self,
        *,
        server_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        server_revision: str,
        client_execution_id: UUID,
    ) -> MCPExecutionResponse:
        self.calls.append(tool_name)
        return await self._wrapped_client.execute(
            server_id=server_id,
            tool_name=tool_name,
            arguments=arguments,
            server_revision=server_revision,
            client_execution_id=client_execution_id,
        )


def _step(number: int, message: str) -> None:
    print(f"[{number}] {message}", flush=True)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _github_settings() -> GitHubSettings:
    return GitHubSettings(
        mcp_github_pat=SecretStr(settings.mcp_github_pat),
        mcp_github_repo=settings.mcp_github_repo,
        trustrail_admin_token=SecretStr(settings.mcp_admin_token),
    )


async def _set_fault_mode(mode: FaultMode) -> None:
    server_url = "https://trustrail-production-8639.up.railway.app"
    _require(bool(server_url), "MCP_GITHUB_SERVER_URL is required for fault injection")

    github_settings = _github_settings()
    endpoint = f"{server_url.rstrip('/')}/admin/fault"
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            endpoint,
            headers={
                "Authorization": (
                    "Bearer "
                    f"{github_settings.trustrail_admin_token.get_secret_value()}"
                )
            },
            json={"mode": mode.value},
        )
        response.raise_for_status()

        payload = response.json()

    _require(
        payload.get("mode") == mode.value and payload.get("updated") is True,
        f"Unexpected fault-mode response: {payload}",
    )


async def _prepare_issue() -> int:
    subprocess.run(
        [sys.executable, "-m", "scripts.seed_sandbox"],
        check=True,
    )

    github_settings = _github_settings()
    async with GitHubClient(settings=github_settings) as client:
        issues = await client.list_issues(state="all")
        matching_issues = [
            issue for issue in issues if SEED_MARKER in (issue.body or "")
        ]
        _require(
            len(matching_issues) == 1,
            f"Expected exactly one seeded {SEED_KEY} issue, found {len(matching_issues)}",
        )
        issue_number = matching_issues[0].number

        issue = await client.get_issue(issue_number)
        if issue.state == "closed":
            await client.reopen_issue(issue_number)

        comments = await client.get_issue_comments(issue_number)
        for comment in comments:
            if "<!-- trustrail:txn=" in (comment.body or ""):
                await client.delete_issue_comment(issue_number, comment.id)

        issue = await client.get_issue(issue_number)
        _require(issue.state == "open", f"Issue #{issue_number} is not open")
        remaining = await client.get_issue_comments(issue_number)
        _require(
            not any("<!-- trustrail:txn=" in (comment.body or "") for comment in remaining),
            f"Issue #{issue_number} still contains a transaction marker",
        )
        return issue_number


async def main() -> None:
    _require(
        bool(settings.otari_mcp_server_id),
        "OTARI_MCP_SERVER_ID is required",
    )
    issue_number = await _prepare_issue()
    transaction_id = uuid4().hex
    marker = f"<!-- trustrail:txn={transaction_id} -->"
    note = f"Lost-response recovery verification for transaction {transaction_id}"
    repository = settings.mcp_github_repo
    db_path = settings.tr_db_path
    server_id = settings.otari_mcp_server_id
    if not server_id:
        raise RuntimeError("OTARI_MCP_SERVER_ID is required")
    run_id = str(uuid4())

    _step(1, f"Prepared {repository} issue #{issue_number}")
    print(f"      Transaction: {transaction_id}")
    print(f"      Marker: {marker}")

    with get_connection(db_path) as connection:
        policy = connection.execute(
            """
            SELECT id FROM policies
            WHERE id = ? AND version = ? AND status = 'ACTIVE'
            """,
            (POLICY_ID, POLICY_VERSION),
        ).fetchone()
        _require(policy is not None, f"Active policy {POLICY_ID} v{POLICY_VERSION} not found")
        connection.execute(
            """
            INSERT INTO runs (id, policy_id, user_request, planner_model, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                run_id,
                POLICY_ID,
                f"Lost-response recovery for issue #{issue_number}",
                settings.tr_planner_model,
                datetime.now(UTC).isoformat(),
            ),
        )
        connection.commit()

    args = {
        "issue_number": issue_number,
        "note": note,
        "txn_id": transaction_id,
    }
    transaction_store = TransactionStore(db_path)
    approval_store = ApprovalStore(db_path)
    transaction_store.create_transaction(
        TransactionCreate(
            id=transaction_id,
            run_id=run_id,
            policy_id=POLICY_ID,
            policy_version=POLICY_VERSION,
            tool=WRITE_TOOL,
            args=args,
            args_hash=hashlib.sha256(
                canonical_json(args).encode("utf-8")
            ).hexdigest(),
        )
    )
    _step(2, "Created transaction through TransactionStore")

    async with OtariMCPClient(
        base_url=settings.otari_base_url,
        api_key=settings.otari_api_key,
        timeout=settings.otari_timeout,
    ) as raw_client:
        client = CountingOtariClient(raw_client)
        executor = TransactionExecutor(
            store=transaction_store,
            approval_store=approval_store,
            otari_client=client,
            server_id=server_id,
            expected_repository=repository,
            db_path=db_path,
        )

        try:
            await executor.execute(transaction_id)
        except ApprovalRequiredError:
            pass
        else:
            raise RuntimeError("Policy did not require approval")

        pending = transaction_store.get_transaction(transaction_id)
        _require(
            pending is not None
            and pending.status is TransactionState.PENDING_APPROVAL,
            "Transaction did not reach PENDING_APPROVAL",
        )
        approval_service = ApprovalService(transaction_store, approval_store)
        approval = approval_service.decide(
            txn_id=transaction_id,
            approver="lost-response-e2e",
            decision=ApprovalDecision.APPROVE,
        )
        _step(3, f"Policy required approval; approval recorded ({approval.id})")

        await _set_fault_mode(FaultMode.DROP_AFTER_APPLY)
        _step(4, "Enabled drop_after_apply and dispatching once")
        result = await executor.execute(transaction_id, approval_id=approval.id)
        print("djdjd",result.status)
        _require(
            result.status is TransactionState.INDETERMINATE,
            f"Expected INDETERMINATE, got {result.status.value}",
        )
        _require(
            client.calls.count(WRITE_TOOL) == 1,
            f"Expected one original write call, got {client.calls.count(WRITE_TOOL)}",
        )
        _step(5, "Write response was lost; transaction reached INDETERMINATE")

        calls_before_reconcile = len(client.calls)
        engine = ReconciliationEngine(
            store=transaction_store,
            otari_client=client,
            server_id=server_id,
            expected_repository=repository,
        )
        reconciliation = await engine.reconcile(transaction_id)
        _require(
            reconciliation.outcome is TransactionState.SUCCEEDED,
            f"Expected reconciliation SUCCEEDED, got {reconciliation.outcome.value}",
        )
        reconciliation_calls = client.calls[calls_before_reconcile:]
        _require(
            WRITE_TOOL not in reconciliation_calls,
            "Reconciliation attempted the original write tool",
        )
        _require(
            bool(reconciliation_calls)
            and all(tool == READ_TOOL for tool in reconciliation_calls),
            f"Reconciliation used non-read-only tools: {reconciliation_calls}",
        )
        _step(6, "Read-only reconciliation returned SUCCEEDED")

        independent = await client.execute(
            server_id=server_id,
            tool_name=READ_TOOL,
            arguments={"issue_number": issue_number, "txn_id": transaction_id},
            server_revision=(await client.discover(server_id)).server_revision,
            client_execution_id=uuid4(),
        )
        _require(not independent.isError, "Independent GitHub evidence request failed")
        _require(independent.structuredContent is not None, "Missing structured GitHub evidence")
        evidence = IssueActivityEvidence.model_validate(independent.structuredContent)
        _require(evidence.is_closed, "GitHub issue is not closed")
        _require(
            evidence.marker_comment_count == 1 and evidence.marker_count == 1,
            (
                "Expected exactly one marker occurrence in one comment; "
                f"comments={evidence.marker_comment_count}, occurrences={evidence.marker_count}"
            ),
        )

    persisted = transaction_store.get_transaction(transaction_id)
    _require(
        persisted is not None and persisted.status is TransactionState.SUCCEEDED,
        "Persisted transaction is not SUCCEEDED",
    )
    events = LedgerStore(db_path).get_events(transaction_id)
    event_types = [event.type for event in events]
    required_events = {
        "TRANSACTION_PROPOSED",
        "AUTHORIZATION_DECISION",
        "APPROVAL_DECISION_RECORDED",
        "RECONCILIATION_COMPLETED",
    }
    _require(required_events <= set(event_types), "Required ledger events are missing")
    status_targets = [
        event.payload.get("to_status")
        for event in events
        if event.type == "TRANSACTION_STATUS_CHANGED"
    ]
    for state in (
        TransactionState.APPROVED.value,
        TransactionState.PRECHECK.value,
        TransactionState.DISPATCHING.value,
        TransactionState.INDETERMINATE.value,
        TransactionState.RECONCILING.value,
        TransactionState.SUCCEEDED.value,
    ):
        _require(state in status_targets, f"Ledger is missing {state} transition")
    verification = LedgerStore(db_path).verify_chain(transaction_id)
    _require(verification.valid, f"Ledger verification failed: {verification.reason}")
    _step(7, "Verified persisted SUCCEEDED state, exactly one marker, and ledger chain")
    print("\nSUCCESS: lost-response recovery verified end to end.")


async def _run_with_fault_cleanup() -> None:
    try:
        await main()
    finally:
        await _set_fault_mode(FaultMode.NONE)


if __name__ == "__main__":
    try:
        asyncio.run(_run_with_fault_cleanup())
    except Exception as exc:
        print(f"\nFAILURE: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
