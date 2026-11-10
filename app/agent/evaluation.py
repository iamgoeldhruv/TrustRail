from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast
from uuid import uuid4

from pydantic import ValidationError

from app.authz.engine import evaluate
from app.authz.models import Action, DecisionKind, Fact, RunState
from app.db.connection import get_connection
from app.facts.github import extract_structured_result, parse_issue_facts
from app.otari.exceptions import OtariMCPError
from app.otari.mcp import OtariMCPClient
from app.policy.models import Policy
from app.policy.validator import PolicySemanticError, validate_policy
from app.txn.models import Transaction
from app.txn.states import TransactionState
from app.txn.store import TransactionStore


class ProposalEvaluationError(Exception):
    """Raised when proposal evaluation cannot be completed safely."""


class ProposalEvaluationService:
    """Evaluate proposals without executing their underlying write tool."""

    def __init__(
        self,
        *,
        store: TransactionStore,
        client: OtariMCPClient,
        server_id: str,
        expected_repository: str,
        db_path: str | Path | None = None,
    ) -> None:
        self.store = store
        self.client = client
        self.server_id = server_id
        self.expected_repository = expected_repository
        self.db_path = db_path

    async def evaluate(
        self,
        transaction_id: str,
        *,
        require_approval: bool = False,
    ) -> Transaction:
        transaction = self.store.get_transaction(transaction_id)
        if transaction is None:
            raise ProposalEvaluationError("Transaction does not exist")
        if transaction.authorization_decision is not None:
            return transaction

        policy = self._load_policy(transaction)
        try:
            action = self._action(transaction)
        except ProposalEvaluationError:
            return self.store.persist_authorization_decision(
                transaction.id,
                decision=DecisionKind.DENY.value,
                reasons=["malformed_proposal"],
                facts={"error": "proposal_action_invalid"},
                evaluated_at=datetime.now(UTC),
                target_state=TransactionState.DENIED,
            )

        if transaction.tool != "close_issue_with_note":
            return self.store.persist_authorization_decision(
                transaction.id,
                decision=DecisionKind.DENY.value,
                reasons=["unsupported_action"],
                facts={},
                evaluated_at=datetime.now(UTC),
                target_state=TransactionState.DENIED,
            )
        facts: Fact | None = None
        fact_snapshot: dict[str, Any] = {}
        server_revision: str | None = None

        if policy is not None:
            try:
                facts, fact_snapshot, server_revision = await self._resolve_facts(
                    action.issue_number,
                    transaction_id=transaction.id,
                )
            except (OtariMCPError, ValidationError, ValueError, ProposalEvaluationError):
                fact_snapshot = {"error": "ground_truth_facts_unavailable"}

        decision = evaluate(
            policy=policy,
            action=action,
            facts=facts,
            run_state=RunState(
                budget_consumed_actions=self._budget_consumed_actions(
                    transaction.run_id,
                    exclude=transaction.id,
                )
            ),
        )
        if require_approval and decision.decision is DecisionKind.ALLOW:
            decision = decision.model_copy(
                update={
                    "decision": DecisionKind.REQUIRES_APPROVAL,
                    "reasons": [
                        *decision.reasons,
                        "retry_requires_fresh_approval",
                    ],
                }
            )
        if facts is None and decision.reasons == ["facts_unavailable"]:
            decision = decision.model_copy(update={"reasons": ["ground_truth_facts_unavailable"]})

        target_state = {
            "DENY": TransactionState.DENIED,
            "POLICY_INVALID": TransactionState.DENIED,
            "REQUIRES_APPROVAL": TransactionState.PENDING_APPROVAL,
            "ALLOW": TransactionState.APPROVED,
        }[decision.decision.value]

        return self.store.persist_authorization_decision(
            transaction.id,
            decision=decision.decision.value,
            reasons=decision.reasons,
            facts=fact_snapshot,
            server_revision=server_revision,
            evaluated_at=datetime.now(UTC),
            target_state=target_state,
        )

    async def _resolve_facts(
        self,
        issue_number: int,
        *,
        transaction_id: str,
    ) -> tuple[Fact, dict[str, Any], str]:
        try:
            discovery = await self.client.discover(self.server_id)
            self.store.record_otari_request_id(
                transaction_id, getattr(discovery, "otari_request_id", None) or ""
            )
        except OtariMCPError as exc:
            self.store.record_otari_request_id(
                transaction_id,
                exc.request_id,
            )
            raise

        self.store.record_otari_request_id(
            transaction_id, getattr(discovery, "otari_request_id", None) or ""
        )

        tool = next(
            (item for item in discovery.tools if item.name == "list_issues"),
            None,
        )

        if tool is None:
            raise ProposalEvaluationError("Otari does not expose list_issues")

        try:
            result = await self.client.execute(
                server_id=self.server_id,
                tool_name="list_issues",
                arguments={"state": "all"},
                server_revision=discovery.server_revision,
                client_execution_id=uuid4(),
            )
            self.store.record_otari_request_id(
                transaction_id, getattr(result, "otari_request_id", None) or ""
            )
        except OtariMCPError as exc:
            self.store.record_otari_request_id(
                transaction_id,
                exc.request_id,
            )
            raise

        if result.isError:
            raise ProposalEvaluationError("Ground-truth facts request failed")

        issue_facts = parse_issue_facts(
            extract_structured_result(
                result.structuredContent,
                result.content,
            )
        )

        if issue_facts.repository.casefold() != self.expected_repository.casefold():
            raise ProposalEvaluationError("Facts repository does not match")

        issue = next(
            (item for item in issue_facts.issues if item.number == issue_number),
            None,
        )

        if issue is None:
            raise ProposalEvaluationError("Issue was not found")

        if issue.state not in {"open", "closed"}:
            raise ProposalEvaluationError("Issue state is invalid")

        state = cast(Literal["open", "closed"], issue.state)

        facts = Fact(
            issue_number=issue.number,
            state=state,
            labels=issue.labels,
            priority=issue.priority,
            inactive_days=issue.inactive_days,
        )

        return (
            facts,
            {
                "repository": issue_facts.repository,
                **facts.model_dump(),
            },
            discovery.server_revision,
        )

    def _load_policy(self, transaction: Transaction) -> Policy | None:
        with get_connection(self.db_path) as connection:
            row = connection.execute(
                "SELECT json FROM policies WHERE id = ? AND version = ?",
                (transaction.policy_id, transaction.policy_version),
            ).fetchone()
        if row is None:
            return None
        try:
            policy = Policy.model_validate(json.loads(row["json"]))
            validate_policy(policy)
            return policy
        except (json.JSONDecodeError, ValidationError, PolicySemanticError):
            return None

    @staticmethod
    def _action(transaction: Transaction) -> Action:
        issue_number = transaction.args.get("issue_number")
        reason = transaction.args.get("note")
        if (
            not isinstance(issue_number, int)
            or isinstance(issue_number, bool)
            or not isinstance(reason, str)
            or not reason.strip()
        ):
            raise ProposalEvaluationError("Proposal action is invalid")
        return Action(
            action="close_issue",
            issue_number=issue_number,
            reason=reason,
        )

    def _budget_consumed_actions(self, run_id: str, *, exclude: str) -> int:
        capacity_states = {
            TransactionState.DISPATCHING,
            TransactionState.SUCCEEDED,
            TransactionState.INDETERMINATE,
            TransactionState.RECONCILING,
        }
        return sum(
            transaction.status in capacity_states
            for transaction in self.store.list_transactions(run_id=run_id)
            if transaction.id != exclude
        )
