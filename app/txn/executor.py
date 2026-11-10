from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import ValidationError

from app.approvals.hashing import policy_content_hash
from app.approvals.store import ApprovalStore
from app.authz.engine import evaluate
from app.authz.models import Action, Fact, RunState
from app.db.connection import get_connection
from app.facts.github import extract_structured_result, parse_issue_facts
from app.otari.exceptions import OtariMCPError
from app.otari.mcp import OtariMCPClient
from app.policy.models import Policy
from app.policy.validator import PolicySemanticError, validate_policy
from app.txn.invalidation import ApprovalInvalidationReason
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
        executor: Literal["secure", "naive"] = "secure",
    ) -> Transaction:
        transaction = self._require_transaction(transaction_id)
        action = self._action(transaction)
        if executor not in {"secure", "naive"}:
            raise TransactionExecutionError("Unsupported executor mode")

        if transaction.status is TransactionState.PROPOSED:
            policy = self._load_policy(transaction)
            transaction = self.store.update_transaction_status(
                transaction.id,
                TransactionState.VALIDATING,
            )
            discovery, facts = await self._resolve_facts(
                action.issue_number, transaction_id=transaction.id
            )
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
                transaction = self.store.persist_authorization_decision(
                    transaction.id,
                    decision=decision.decision.value,
                    reasons=decision.reasons,
                    facts={"repository": self.expected_repository, **facts.model_dump()},
                    server_revision=discovery.server_revision,
                    evaluated_at=datetime.now(UTC),
                    target_state=TransactionState.PENDING_APPROVAL,
                )
                if not approval_id:
                    raise ApprovalRequiredError(f"Transaction {transaction.id} requires approval")
            elif decision.decision.value == "ALLOW":
                transaction = self.store.update_transaction_status(
                    transaction.id,
                    TransactionState.APPROVED,
                )

        requires_approval = transaction.authorization_decision == "REQUIRES_APPROVAL"
        approval_policy_hash: str | None = None
        approval_record_id: str | None = None
        if requires_approval:
            approval_id = approval_id or transaction.approval_id
            if not approval_id:
                raise ApprovalRequiredError(f"Transaction {transaction.id} requires approval")
            original_facts = self._original_facts(transaction)
            if not transaction.server_revision:
                raise TransactionExecutionError("Original server revision is missing")
            approval_record = self.approval_store.get(approval_id)
            if approval_record is None:
                raise TransactionExecutionError("Approval cannot be verified")
            if approval_record.policy_hash is None:
                raise TransactionExecutionError("Approval cannot be verified")
            approval_policy_hash = approval_record.policy_hash
            approval_record_id = approval_record.id
            _=self.approval_store.verify(
                approval_id=approval_id,
                txn_id=transaction.id,
                tool=transaction.tool,
                args=transaction.args,
                policy_version=transaction.policy_version,
                facts_that_matter=original_facts.model_dump(),
                server_revision=transaction.server_revision,
                policy_hash=approval_policy_hash,
            )
            if transaction.approval_id is None:
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

        dispatch_revision: str
        if requires_approval:
            try:
                current_policy = self._load_policy(transaction)
            except TransactionExecutionError:
                return self.store.invalidate_approval(
                    transaction.id,
                    ApprovalInvalidationReason.NOW_DENIED.value,
                )
            latest_discovery, latest_facts = await self._resolve_facts(
                action.issue_number,
                transaction_id=transaction.id,
            )
            current_decision = evaluate(
                current_policy,
                action,
                latest_facts,
                RunState(budget_consumed_actions=self._budget_consumed_actions(transaction.run_id)),
            )

            if current_decision.decision.value in {"DENY", "POLICY_INVALID"}:
                return self.store.invalidate_approval(
                    transaction.id,
                    ApprovalInvalidationReason.NOW_DENIED.value,
                )

            original_facts = self._original_facts(transaction)
            current_policy_hash = policy_content_hash(current_policy)
            reason = None
            if latest_discovery.server_revision != transaction.server_revision:
                reason = ApprovalInvalidationReason.REVISION_CHANGED
            elif latest_facts != original_facts:
                reason = ApprovalInvalidationReason.FACTS_CHANGED
            elif current_policy_hash != approval_policy_hash:
                reason = ApprovalInvalidationReason.POLICY_CHANGED
            if reason is not None:
                return self.store.invalidate_approval(transaction.id, reason.value)

            assert approval_record_id is not None
            assert approval_policy_hash is not None
            self.approval_store.verify(
                approval_id=approval_record_id,
                txn_id=transaction.id,
                tool=transaction.tool,
                args=transaction.args,
                policy_version=transaction.policy_version,
                facts_that_matter=latest_facts.model_dump(),
                server_revision=latest_discovery.server_revision,
                policy_hash=current_policy_hash,
            )
            dispatch_revision = latest_discovery.server_revision
        else:
            latest_discovery, _ = await self._resolve_facts(
                action.issue_number,
                transaction_id=transaction.id,
            )
            dispatch_revision = latest_discovery.server_revision

        if transaction.args.get("txn_id") != transaction.id:
            raise TransactionExecutionError(
                "Transaction arguments must contain the matching txn_id"
            )
        if "demo_allow_duplicate" in transaction.args:
            raise TransactionExecutionError(
                "demo_allow_duplicate is reserved for the naive demo executor"
            )

        if executor == "naive" and transaction.tool != "close_issue_with_note":
            raise TransactionExecutionError(
                "Naive demo executor only supports close_issue_with_note"
            )

        
        if not self.store.claim_for_dispatch(transaction.id):
            raise TransactionExecutionError("Transaction dispatch claim failed")

        if executor == "naive":
            return await self._execute_naive_demo(
                transaction,
                dispatch_revision=dispatch_revision,
            )

        # Existing secure single-attempt execution.
        try:
            dispatch_arguments = dict(transaction.args)
            result = await self.otari_client.execute(
                server_id=self.server_id,
                tool_name=transaction.tool,
                arguments=dispatch_arguments,
                server_revision=dispatch_revision,
                client_execution_id=uuid4(),
            )
            self.store.record_otari_request_id(
                transaction.id,
                result.otari_request_id,
            )
            target_state = classify_execution_outcome(result)

        except OtariMCPError as exc:
            self.store.record_otari_request_id(
                transaction.id,
                exc.request_id,
            )
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

    async def _execute_naive_demo(
        self,
        transaction: Transaction,
        *,
        dispatch_revision: str,
    ) -> Transaction:
        """Demo-only executor that blindly retries indeterminate outcomes."""
        max_attempts = 3
        target_state = TransactionState.INDETERMINATE

        for attempt in range(1, max_attempts + 1):
            client_execution_id = uuid4()

            dispatch_arguments = dict(transaction.args)

            # The first execution follows normal server-side protections.
            # Subsequent attempts explicitly activate the demo-only bypass.
            demo_allow_duplicate = attempt > 1

            if demo_allow_duplicate:
                dispatch_arguments["demo_allow_duplicate"] = True

            try:
                result = await self.otari_client.execute(
                    server_id=self.server_id,
                    tool_name=transaction.tool,
                    arguments=dispatch_arguments,
                    server_revision=dispatch_revision,
                    client_execution_id=client_execution_id,
                )

                request_id = result.otari_request_id
                target_state = classify_execution_outcome(result)

            except OtariMCPError as exc:
                request_id = exc.request_id
                target_state = classify_execution_outcome(exc)

            self.store.record_naive_demo_attempt(
                transaction.id,
                attempt=attempt,
                max_attempts=max_attempts,
                client_execution_id=client_execution_id,
                outcome=target_state.value,
                otari_request_id=request_id,
                demo_allow_duplicate=demo_allow_duplicate,
            )

            if target_state is not TransactionState.INDETERMINATE:
                break

        return self.store.update_transaction_status(
            transaction.id,
            target_state,
        )

    async def _resolve_facts(
    self,
    issue_number: int,
    *,
    transaction_id: str,
) -> tuple[Any, Fact]:
        try:
            discovery = await self.otari_client.discover(self.server_id)
            self.store.record_otari_request_id(
                transaction_id,
                discovery.otari_request_id,
            )
        except OtariMCPError as exc:
            self.store.record_otari_request_id(
                transaction_id,
                exc.request_id,
            )
            raise

        self.store.record_otari_request_id(
            transaction_id,
            discovery.otari_request_id,
        )

        if "list_issues" not in {tool.name for tool in discovery.tools}:
            raise TransactionExecutionError("Otari does not expose list_issues")

        try:
            result = await self.otari_client.execute(
                server_id=self.server_id,
                tool_name="list_issues",
                arguments={"state": "all"},
                server_revision=discovery.server_revision,
                client_execution_id=uuid4(),
            )
        except OtariMCPError as exc:
            self.store.record_otari_request_id(
                transaction_id,
                exc.request_id,
            )
            raise

        self.store.record_otari_request_id(
            transaction_id,
            result.otari_request_id,
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
            issue = next(
                item
                for item in issue_facts.issues
                if item.number == issue_number
            )
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
        try:
            policy = Policy.model_validate(json.loads(row["json"]))
            validate_policy(policy)
            return policy
        except (json.JSONDecodeError, ValidationError, PolicySemanticError) as exc:
            raise TransactionExecutionError("Policy is invalid") from exc

    @staticmethod
    def _original_facts(transaction: Transaction) -> Fact:
        if not isinstance(transaction.facts, dict):
            raise TransactionExecutionError("Original facts are missing")
        try:
            return Fact.model_validate(
                {
                    key: transaction.facts[key]
                    for key in (
                        "issue_number",
                        "state",
                        "labels",
                        "priority",
                        "inactive_days",
                    )
                }
            )
        except (KeyError, ValidationError, ValueError) as exc:
            raise TransactionExecutionError("Original facts are invalid") from exc

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
