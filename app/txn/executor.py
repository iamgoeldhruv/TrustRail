from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from app.approvals.store import ApprovalStore
from app.authz.engine import evaluate
from app.authz.models import Action, Fact, RunState
from app.db.connection import get_connection
from app.facts.github import extract_structured_result, parse_issue_facts
from app.otari.exceptions import OtariMCPError
from app.otari.mcp import OtariMCPClient
from app.policy.models import Policy
from app.txn.models import Transaction
from app.txn.outcome_classifier import classify_execution_outcome
from app.txn.states import TransactionState
from app.txn.store import TransactionStore


class ApprovalRequiredError(Exception):
    """Raised when an authorized action requires human approval."""


class TransactionExecutionError(Exception):
    """Raised when a transaction cannot safely be executed."""


class TransactionExecutor:
    """Orchestrate one policy-checked, approved, single-attempt write."""

    def __init__(
        self,
        *,
        store: TransactionStore,
        approval_store: ApprovalStore,
        otari_client: OtariMCPClient,
        server_id: str,
        expected_repository: str,
        db_path: str | Path | None = None,
    ) -> None:
        self.store = store
        self.approval_store = approval_store
        self.otari_client = otari_client
        self.server_id = server_id
        self.expected_repository = expected_repository
        self.db_path = db_path

    async def execute(
        self,
        transaction_id: str,
        *,
        approval_id: str | None = None,
    ) -> Transaction:
        transaction = self._require_transaction(transaction_id)
        policy = self._load_policy(transaction)
        action = self._action(transaction)

        if transaction.status is TransactionState.PROPOSED:
            transaction = self.store.update_transaction_status(
                transaction.id,
                TransactionState.VALIDATING,
            )

        discovery, facts = await self._resolve_facts(action.issue_number)
        decision = evaluate(
            policy,
            action,
            facts,
            RunState(budget_consumed_actions=self._budget_consumed_actions(transaction.run_id)),
        )
        if decision.decision.value in {"DENY", "POLICY_INVALID"}:
            return self.store.update_transaction_status(
                transaction.id,
                TransactionState.DENIED,
            )

        if decision.decision.value == "REQUIRES_APPROVAL":
            if not approval_id and not transaction.approval_id:
                self.store.update_transaction_status(
                    transaction.id,
                    TransactionState.PENDING_APPROVAL,
                )
                raise ApprovalRequiredError(f"Transaction {transaction.id} requires approval")
            approval_id = approval_id or transaction.approval_id
        elif decision.decision.value == "ALLOW":
            if transaction.status is TransactionState.VALIDATING:
                transaction = self.store.update_transaction_status(
                    transaction.id,
                    TransactionState.APPROVED,
                )

        if approval_id is not None:
            self.approval_store.verify(
                approval_id=approval_id,
                txn_id=transaction.id,
                tool=transaction.tool,
                args=transaction.args,
                policy_version=transaction.policy_version,
                facts_that_matter=facts.model_dump(),
                server_revision=discovery.server_revision,
            )
            self.store.attach_approval(transaction.id, approval_id)

        if transaction.status is TransactionState.PENDING_APPROVAL:
            transaction = self.store.update_transaction_status(
                transaction.id,
                TransactionState.APPROVED,
            )
        if transaction.status is TransactionState.APPROVED:
            transaction = self.store.update_transaction_status(
                transaction.id,
                TransactionState.PRECHECK,
            )

        latest_discovery, latest_facts = await self._resolve_facts(action.issue_number)
        if latest_discovery.server_revision != discovery.server_revision or latest_facts != facts:
            raise TransactionExecutionError(
                "Approval invalidated because facts or server revision changed"
            )

        if not self.store.claim_for_dispatch(transaction.id):
            raise TransactionExecutionError("Transaction dispatch claim failed")

        try:
            result = await self.otari_client.execute(
                server_id=self.server_id,
                tool_name=transaction.tool,
                arguments=transaction.args,
                server_revision=latest_discovery.server_revision,
                client_execution_id=uuid4(),
            )
            self.store.record_otari_request_id(
                transaction.id,
                result.otari_request_id,
            )
            target_state = classify_execution_outcome(result)
        except OtariMCPError as exc:
            self.store.record_otari_request_id(transaction.id, exc.request_id)
            target_state = classify_execution_outcome(exc)

        return self.store.update_transaction_status(
            transaction.id,
            target_state,
        )

    def _budget_consumed_actions(self, run_id: str) -> int:
        """Count actions that have consumed or reserved run capacity."""

        capacity_states = {
            TransactionState.DISPATCHING,
            TransactionState.SUCCEEDED,
            TransactionState.INDETERMINATE,
            TransactionState.RECONCILING,
        }

        transactions = self.store.list_transactions(run_id=run_id)

        return sum(transaction.status in capacity_states for transaction in transactions)

    async def _resolve_facts(
        self,
        issue_number: int,
    ) -> tuple[Any, Fact]:
        discovery = await self.otari_client.discover(self.server_id)
        if "list_issues" not in {tool.name for tool in discovery.tools}:
            raise TransactionExecutionError("Otari does not expose list_issues")

        result = await self.otari_client.execute(
            server_id=self.server_id,
            tool_name="list_issues",
            arguments={"state": "all"},
            server_revision=discovery.server_revision,
            client_execution_id=uuid4(),
        )
        if result.isError:
            raise TransactionExecutionError("Otari facts request failed")

        issue_facts = parse_issue_facts(
            extract_structured_result(
                result.structuredContent,
                result.content,
            )
        )
        if issue_facts.repository != self.expected_repository:
            raise TransactionExecutionError("Facts repository does not match")
        try:
            issue = next(item for item in issue_facts.issues if item.number == issue_number)
        except StopIteration as exc:
            raise TransactionExecutionError("Issue was not found") from exc

        return discovery, Fact(
            issue_number=issue.number,
            state=self._issue_state(issue.state),
            labels=issue.labels,
            priority=issue.priority,
            inactive_days=issue.inactive_days,
        )

    @staticmethod
    def _issue_state(value: str) -> Literal["open", "closed"]:
        if value not in {"open", "closed"}:
            raise TransactionExecutionError(f"Unsupported issue state: {value}")
        if value == "open":
            return "open"
        return "closed"

    def _require_transaction(self, transaction_id: str) -> Transaction:
        transaction = self.store.get_transaction(transaction_id)
        if transaction is None:
            raise TransactionExecutionError("Transaction does not exist")
        return transaction

    def _load_policy(self, transaction: Transaction) -> Policy:
        with get_connection(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT json
                FROM policies
                WHERE id = ? AND version = ?
                """,
                (transaction.policy_id, transaction.policy_version),
            ).fetchone()
        if row is None:
            raise TransactionExecutionError("Policy version does not exist")
        return Policy.model_validate(json.loads(row["json"]))

    @staticmethod
    def _action(transaction: Transaction) -> Action:
        issue_number = transaction.args.get("issue_number")
        if not isinstance(issue_number, int) or isinstance(issue_number, bool):
            raise TransactionExecutionError("Transaction issue_number is invalid")
        return Action(
            action="close_issue",
            issue_number=issue_number,
            reason=str(transaction.args.get("note", "TrustRail action")),
        )
