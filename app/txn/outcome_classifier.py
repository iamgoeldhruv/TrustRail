
from app.otari.exceptions import (
    OtariMCPNotStartedError,
    OtariMCPOutcomeUnknownError,
    OtariMCPServerChangedError,
)
from app.otari.mcp import MCPExecutionResponse
from app.txn.states import TransactionState


def classify_execution_outcome(
    result: MCPExecutionResponse | Exception,
) -> TransactionState:

    if isinstance(result, OtariMCPServerChangedError):
        return TransactionState.APPROVAL_INVALIDATED

    if isinstance(result, OtariMCPOutcomeUnknownError):
        return TransactionState.INDETERMINATE

    if isinstance(result, OtariMCPNotStartedError):
        return TransactionState.FAILED_SAFE

    if isinstance(result, MCPExecutionResponse):
        if result.isError:
            return TransactionState.FAILED

        return TransactionState.SUCCEEDED

    raise TypeError(
        f"Unsupported execution outcome type: {type(result).__name__}"
    )
