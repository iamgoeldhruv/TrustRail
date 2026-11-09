
from unittest.mock import Mock

import pytest

from app.agent.tool_handlers import (
    AgentToolError,
    AgentToolHandlers,
)
from app.txn.states import TransactionState


@pytest.fixture
def proposal_service():
    return Mock()


@pytest.fixture
def handlers(proposal_service):
    return AgentToolHandlers(
        client=Mock(),
        server_id="github-server",
        expected_repository="iamgoeldhruv/LimeDraw",
        proposal_service=proposal_service,
    )


def test_propose_close_creates_proposal(
    handlers,
    proposal_service,
):
    transaction = Mock()
    transaction.id = "txn-test-123"
    transaction.status = TransactionState.PROPOSED

    proposal_service.create_close_proposal.return_value = transaction

    result = handlers.propose_close(
        arguments={
            "issue_number": 42,
            "reason": "Issue has been inactive for 30 days.",
        },
        run_id="trusted-run-123",
    )

    assert result == {
        "status": "PROPOSED",
        "transaction_id": "txn-test-123",
        "issue_number": 42,
        "message": "Proposal created. Awaiting authorization.",
    }

    proposal_service.create_close_proposal.assert_called_once_with(
        run_id="trusted-run-123",
        issue_number=42,
        reason="Issue has been inactive for 30 days.",
    )


def test_propose_close_rejects_model_supplied_run_id(handlers):
    with pytest.raises(AgentToolError):
        handlers.propose_close(
            arguments={
                "issue_number": 42,
                "reason": "Inactive issue.",
                "run_id": "attacker-controlled-run",
            },
            run_id="trusted-run-123",
        )


def test_propose_close_rejects_model_supplied_txn_id(handlers):
    with pytest.raises(AgentToolError):
        handlers.propose_close(
            arguments={
                "issue_number": 42,
                "reason": "Inactive issue.",
                "txn_id": "attacker-controlled-id",
            },
            run_id="trusted-run-123",
        )


@pytest.mark.parametrize(
    "arguments",
    [
        {"issue_number": 0, "reason": "Invalid issue"},
        {"issue_number": 42, "reason": ""},
        {"issue_number": 42, "reason": "   "},
        {"issue_number": True, "reason": "Invalid type"},
    ],
)
def test_propose_close_rejects_invalid_arguments(
    handlers,
    arguments,
):
    with pytest.raises(AgentToolError):
        handlers.propose_close(
            arguments=arguments,
            run_id="trusted-run-123",
        )


def test_propose_close_rejects_missing_proposal_service():
    handlers = AgentToolHandlers(
        client=Mock(),
        server_id="github-server",
        expected_repository="iamgoeldhruv/LimeDraw",
    )

    with pytest.raises(
        AgentToolError,
        match="not configured",
    ):
        handlers.propose_close(
            arguments={
                "issue_number": 42,
                "reason": "Inactive issue.",
            },
            run_id="trusted-run-123",
        )


def test_propose_close_does_not_execute_github_write(
    handlers,
    proposal_service,
):
    transaction = Mock()
    transaction.id = "txn-test-456"
    transaction.status = TransactionState.PROPOSED

    proposal_service.create_close_proposal.return_value = transaction

    handlers.propose_close(
        arguments={
            "issue_number": 42,
            "reason": "Inactive issue.",
        },
        run_id="trusted-run-123",
    )

    # ProposalService is the only dependency invoked.
    proposal_service.create_close_proposal.assert_called_once()

    # The Otari client must not be involved in proposal creation.
    handlers.client.execute.assert_not_called()
    handlers.client.discover.assert_not_called()
