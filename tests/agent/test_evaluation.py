import json
from datetime import UTC, datetime

import pytest

from app.agent.evaluation import ProposalEvaluationService
from app.authz.models import DecisionKind
from app.db.connection import get_connection
from app.db.migrations import run_migrations
from app.ledger.store import LedgerStore
from app.txn.models import TransactionCreate
from app.txn.states import TransactionState
from app.txn.store import TransactionStore

POLICY = {
    "version": 1,
    "repo": "owner/repo",
    "actions": {
        "close_issue": {
            "allowed": True,
            "conditions": {
                "inactive_days_gte": 30,
                "priority_not_in": ["P0", "P1"],
                "require_priority_label": True,
            },
            "requires_approval": True,
        }
    },
    "limits": {"max_actions_per_run": 10},
    "audit": {"enabled": True},
}


class FactsClient:
    async def discover(self, server_id):
        return type("Discovery", (), {
            "server_revision": "rev-1",
            "tools": [type("Tool", (), {"name": "list_issues"})()],
        })()

    async def execute(self, **kwargs):
        return type("Result", (), {
            "isError": False,
            "structuredContent": {
                "repository": "owner/repo",
                "total": 1,
                "issues": [{
                    "number": 7,
                    "title": "External data",
                    "labels": ["P2"],
                    "state": "open",
                    "inactive_days": 45,
                }],
            },
            "content": [],
        })()


@pytest.mark.asyncio
async def test_proposal_evaluation_persists_ground_truth_and_ledger(tmp_path):
    db_path = tmp_path / "test.db"
    run_migrations(db_path=db_path)
    now = datetime.now(UTC).isoformat()
    with get_connection(db_path) as connection:
        connection.execute(
            "INSERT INTO policies (id, version, nl_text, json, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("policy-1", 1, "policy", json.dumps(POLICY), "ACTIVE", now),
        )
        connection.execute(
            "INSERT INTO runs (id, policy_id, user_request, planner_model, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("run-1", "policy-1", "close issue", "planner", now),
        )
        connection.commit()

    store = TransactionStore(db_path)
    transaction = store.create_transaction(TransactionCreate(
        id="txn-1",
        run_id="run-1",
        policy_id="policy-1",
        policy_version=1,
        tool="close_issue_with_note",
        args={"issue_number": 7, "note": "inactive"},
        args_hash="hash",
    ))

    result = await ProposalEvaluationService(
        store=store,
        client=FactsClient(),
        server_id="server",
        expected_repository="owner/repo",
        db_path=db_path,
    ).evaluate(transaction.id)

    assert result.status is TransactionState.PENDING_APPROVAL
    assert result.authorization_decision == DecisionKind.REQUIRES_APPROVAL.value
    assert result.facts["priority"] == "P2"
    events = LedgerStore(db_path).get_events(transaction.id)
    assert events[-2].type == "AUTHORIZATION_DECISION"
    assert events[-2].payload["facts"]["inactive_days"] == 45
    assert LedgerStore(db_path).verify_chain(transaction.id).valid is True
