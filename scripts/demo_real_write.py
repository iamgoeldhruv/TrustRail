from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime
from uuid import uuid4

from app.approvals.hashing import approval_binding_hash
from app.approvals.models import ApprovalCreate, ApprovalDecision
from app.approvals.store import ApprovalStore
from app.core.config import settings
from app.db.connection import get_connection
from app.ledger.canonical import canonical_json
from app.otari.mcp import OtariMCPClient
from app.txn.executor import (
    ApprovalRequiredError,
    TransactionExecutor,
)
from app.txn.models import TransactionCreate
from app.txn.store import TransactionStore


POLICY_ID = "demo-close-issue-policy"
POLICY_VERSION = 1
ISSUE_NUMBER = 4
REPOSITORY = settings.mcp_github_repo

NOTE = "Closing this inactive issue after TrustRail policy evaluation and human approval."


async def main() -> None:
    if not settings.otari_mcp_server_id:
        raise RuntimeError("OTARI_MCP_SERVER_ID is missing from .env")

    db_path = settings.tr_db_path
    server_id = settings.otari_mcp_server_id

    txn_id = str(uuid4())
    run_id = str(uuid4())

    args = {
        "issue_number": ISSUE_NUMBER,
        "note": NOTE,
        "txn_id": txn_id,
    }

    print("=" * 65)
    print("TRUSTRAIL FRESH REAL-WRITE DEMO")
    print("=" * 65)
    print(f"Repository:    {REPOSITORY}")
    print(f"Issue:         #{ISSUE_NUMBER}")
    print(f"Transaction:   {txn_id}")
    print(f"Policy:        {POLICY_ID} v{POLICY_VERSION}")
    print()

    # 1. Confirm the policy exists and create a run.
    with get_connection(db_path) as connection:
        policy = connection.execute(
            """
            SELECT id FROM policies
            WHERE id = ? AND version = ? AND status = 'ACTIVE'
            """,
            (POLICY_ID, POLICY_VERSION),
        ).fetchone()

        if policy is None:
            raise RuntimeError("Expected active demo policy was not found")

        connection.execute(
            """
            INSERT INTO runs (
                id, policy_id, user_request, planner_model, created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                run_id,
                POLICY_ID,
                f"Close inactive GitHub issue #{ISSUE_NUMBER}",
                settings.tr_planner_model,
                datetime.now(UTC).isoformat(),
            ),
        )
        connection.commit()

    # 2. Create a fresh transaction.
    args_hash = hashlib.sha256(canonical_json(args).encode("utf-8")).hexdigest()

    transaction_store = TransactionStore(db_path)
    approval_store = ApprovalStore(db_path)

    transaction = transaction_store.create_transaction(
        TransactionCreate(
            id=txn_id,
            run_id=run_id,
            policy_id=POLICY_ID,
            policy_version=POLICY_VERSION,
            tool="close_issue_with_note",
            args=args,
            args_hash=args_hash,
        )
    )

    print(f"[1/5] Transaction created: {transaction.id}")
    print(f"      Initial state: {transaction.status.value}")

    # 3. Let the real executor evaluate policy and request approval.
    async with OtariMCPClient(
        base_url=settings.otari_base_url,
        api_key=settings.otari_api_key,
        timeout=settings.otari_timeout,
    ) as otari_client:
        executor = TransactionExecutor(
            store=transaction_store,
            approval_store=approval_store,
            otari_client=otari_client,
            server_id=server_id,
            expected_repository=REPOSITORY,
            db_path=db_path,
        )

        try:
            await executor.execute(txn_id)
            raise RuntimeError("Expected approval requirement, but execution returned")
        except ApprovalRequiredError:
            print("[2/5] Policy evaluated: human approval required")

        pending = transaction_store.get_transaction(txn_id)
        if pending is None or pending.status.value != "PENDING_APPROVAL":
            raise RuntimeError("Transaction did not enter PENDING_APPROVAL")

        # 4. Bind approval to the exact action, facts and server revision.
        discovery, facts = await executor._resolve_facts(ISSUE_NUMBER)

        if facts.state != "open":
            raise RuntimeError(f"Issue #{ISSUE_NUMBER} is not open: {facts.state}")

        binding_hash = approval_binding_hash(
            tool=pending.tool,
            args=pending.args,
            policy_version=pending.policy_version,
            facts_that_matter=facts.model_dump(),
            server_revision=discovery.server_revision,
        )

        approval = approval_store.create(
            ApprovalCreate(
                txn_id=txn_id,
                approver="manual-demo-operator",
                decision=ApprovalDecision.APPROVE,
                binding_hash=binding_hash,
                decided_at=datetime.now(UTC),
            )
        )

        print("[3/5] Approval created and bound to current facts")
        print(f"      Approval ID: {approval.id}")
        print(f"      Server revision: {discovery.server_revision}")

        # 5. Execute exactly once through the real executor.
        print("[4/5] Dispatching the approved transaction...")

        result = await executor.execute(
            txn_id,
            approval_id=approval.id,
        )

        print()
        print("=" * 65)
        print("EXECUTION RESULT")
        print("=" * 65)
        print(f"Transaction ID: {result.id}")
        print(f"Final status:   {result.status.value}")
        print(f"Otari IDs:      {result.otari_request_ids}")
        print(f"Approval ID:    {result.approval_id}")

        print()
        print("[5/5] Write attempt finished.")
        print("Do not retry this transaction if its outcome is uncertain.")


if __name__ == "__main__":
    asyncio.run(main())
