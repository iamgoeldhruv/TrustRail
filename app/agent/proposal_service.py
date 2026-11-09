
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from app.agent.models import ProposeCloseArgs
from app.db.connection import get_connection
from app.ledger.canonical import canonical_json
from app.policy.models import Policy
from app.policy.validator import PolicySemanticError, validate_policy
from app.txn.models import Transaction, TransactionCreate
from app.txn.states import TransactionState
from app.txn.store import TransactionStore

WRITE_TOOL = "close_issue_with_note"


class ProposalServiceError(Exception):
    """Raised when a proposal cannot be safely created."""


class ProposalService:
    """Create proposal-only transactions for agent-requested actions."""

    def __init__(
        self,
        *,
        store: TransactionStore,
        expected_repository: str,
        db_path: str | Path | None = None,
    ) -> None:
        if not expected_repository.strip():
            raise ValueError("expected_repository cannot be empty")

        self.store = store
        self.expected_repository = expected_repository
        self.db_path = db_path

    def create_close_proposal(
        self,
        *,
        run_id: str,
        issue_number: int,
        reason: str,
    ) -> Transaction:
        """Persist a proposed close action without executing a write."""

        if not run_id.strip():
            raise ProposalServiceError("run_id cannot be empty")

        # Strictly validate model-supplied arguments.
        try:
            parsed = ProposeCloseArgs.model_validate(
                {
                    "issue_number": issue_number,
                    "reason": reason,
                }
            )
        except ValidationError as exc:
            raise ProposalServiceError(
                "Invalid arguments for propose_close."
            ) from exc

        normalized_reason = parsed.reason.strip()

        if not normalized_reason:
            raise ProposalServiceError("Proposal reason cannot be empty.")

        # Load the policy associated with this trusted run.
        policy_id, policy_version, policy = self._load_run_policy(run_id)

        # The policy must target the configured repository.
        if (
            policy.repo.casefold()
            != self.expected_repository.casefold()
        ):
            raise ProposalServiceError(
                "Run policy repository does not match TrustRail configuration."
            )

        # Reject malformed or semantically contradictory policies.
        try:
            validate_policy(policy)
        except (PolicySemanticError, ValidationError) as exc:
            raise ProposalServiceError(
                "The run's policy is invalid."
            ) from exc

        # Generate the transaction ID before constructing write arguments.
        transaction_id = str(uuid4())

        # These are the exact arguments eventually sent to the GitHub MCP tool.
        # The LLM cannot supply or override txn_id.
        write_arguments = {
            "issue_number": parsed.issue_number,
            "note": normalized_reason,
            "txn_id": transaction_id,
        }

        args_hash = hashlib.sha256(
            canonical_json(write_arguments).encode("utf-8")
        ).hexdigest()

        transaction = TransactionCreate(
            id=transaction_id,
            run_id=run_id,
            policy_id=policy_id,
            policy_version=policy_version,
            tool=WRITE_TOOL,
            args=write_arguments,
            args_hash=args_hash,
            status=TransactionState.PROPOSED,
        )

        # Persist only. Never call TransactionExecutor here.
        return self.store.create_transaction(transaction)

    def _load_run_policy(
        self,
        run_id: str,
    ) -> tuple[str, int, Policy]:
        with get_connection(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT
                    r.policy_id,
                    p.version,
                    p.json
                FROM runs AS r
                JOIN policies AS p
                    ON p.id = r.policy_id
                WHERE r.id = ?
                  AND p.status = 'ACTIVE'
                ORDER BY p.version DESC
                LIMIT 1
                """,
                (run_id,),
            ).fetchone()

        if row is None:
            raise ProposalServiceError(
                "Run does not exist or has no active policy."
            )

        try:
            policy = Policy.model_validate(json.loads(row["json"]))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise ProposalServiceError(
                "Stored policy data is invalid."
            ) from exc

        if policy.version != row["version"]:
            raise ProposalServiceError(
                "Stored policy version does not match its database record."
            )

        return row["policy_id"], row["version"], policy
