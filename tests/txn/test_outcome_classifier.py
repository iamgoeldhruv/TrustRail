
import pytest

from app.otari.exceptions import (
    OtariMCPNotStartedError,
    OtariMCPOutcomeUnknownError,
    OtariMCPServerChangedError,
)
from app.otari.mcp import MCPExecutionResponse
from app.txn.outcome_classifier import classify_execution_outcome
from app.txn.states import TransactionState


@pytest.mark.parametrize(
    ("result", "expected_state"),
    [
        pytest.param(
            MCPExecutionResponse(
                content=[{"type": "text", "text": "Execution successful"}],
                isError=False,
            ),
            TransactionState.SUCCEEDED,
            id="successful-execution",
        ),
        pytest.param(
            MCPExecutionResponse(
                content=[{"type": "text", "text": "Tool execution failed"}],
                isError=True,
            ),
            TransactionState.FAILED,
            id="definitive-tool-error",
        ),
        pytest.param(
            OtariMCPNotStartedError(
                message="Execution did not start",
                status_code=503,
                code="service_unavailable",
                execution_state="not_started",
            ),
            TransactionState.FAILED_SAFE,
            id="not-started",
        ),
        pytest.param(
            OtariMCPOutcomeUnknownError(
                message="Execution outcome is unknown",
                status_code=504,
                code="mcp_outcome_unknown",
                execution_state="outcome_unknown",
            ),
            TransactionState.INDETERMINATE,
            id="outcome-unknown",
        ),
        pytest.param(
            OtariMCPServerChangedError(
                message="MCP server revision changed",
                status_code=409,
                code="mcp_server_changed",
                execution_state="not_started",
            ),
            TransactionState.APPROVAL_INVALIDATED,
            id="server-revision-changed",
        ),
    ],
)
def test_classify_execution_outcome(
    result: MCPExecutionResponse | Exception,
    expected_state: TransactionState,
) -> None:
    assert classify_execution_outcome(result) == expected_state


def test_unsupported_outcome_type_raises_type_error() -> None:
    with pytest.raises(TypeError, match="Unsupported execution outcome type"):
        classify_execution_outcome("unexpected-result")  # type: ignore[arg-type]
