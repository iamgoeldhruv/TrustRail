from datetime import UTC, datetime
from unittest.mock import Mock

from app.api.routes.runs import _workflow_projection
from app.ledger.models import LedgerEvent, LedgerVerificationResult


def _ledger_event(payload: dict) -> LedgerEvent:
    return LedgerEvent(
        id="event-1",
        run_id="run-1",
        seq=1,
        type="GUARDRAIL_EVALUATED",
        payload=payload,
        ts=datetime.now(UTC),
        prev_hash="0" * 64,
        hash="1" * 64,
    )


def test_workflow_projection_flattens_guardrail_payload():
    ledger = Mock()
    ledger.verify_chain.return_value = LedgerVerificationResult(
        valid=True,
        run_id="run-1",
        events_checked=1,
    )
    projection = _workflow_projection(
        run={
            "run_id": "run-1",
            "status": "COMPLETED",
            "user_request": "test",
            "planner_model": "planner",
            "created_at": "2026-01-01T00:00:00Z",
            "policy_id": "policy-1",
        },
        transactions=[],
        events=[
            _ledger_event(
                {
                    "status": "PASSED",
                    "profile": "prompt-injection",
                    "mode": "block",
                }
            )
        ],
        ledger=ledger,
    )

    guardrail = projection["stages"][2]
    assert guardrail["status"] == "PASSED"
    assert guardrail["details"]["latest"]["profile"] == "prompt-injection"


def test_workflow_projection_handles_legacy_guardrail_payload_without_status():
    ledger = Mock()
    ledger.verify_chain.return_value = LedgerVerificationResult(
        valid=True,
        run_id="run-1",
        events_checked=1,
    )
    projection = _workflow_projection(
        run={
            "run_id": "run-1",
            "status": "FAILED",
            "user_request": "test",
            "planner_model": "planner",
            "created_at": "2026-01-01T00:00:00Z",
            "policy_id": "policy-1",
        },
        transactions=[],
        events=[_ledger_event({"profile": "prompt-injection"})],
        ledger=ledger,
    )

    guardrail = projection["stages"][2]
    assert guardrail["status"] == "UNKNOWN"
    assert guardrail["details"]["latest"]["status"] == "UNKNOWN"
