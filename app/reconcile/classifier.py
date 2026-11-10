
from app.reconcile.models import (
    IssueActivityEvidence,
    ReconciliationOutcome,
)
from app.txn.states import TransactionState


def classify_reconciliation(
    transaction_id: str,
    evidence: IssueActivityEvidence,
) -> ReconciliationOutcome:
    """
    Classify the original write using read-only GitHub evidence.

    The marker comment identifies whether this particular transaction
    applied its write. Issue closure alone is not sufficient evidence.
    """

    if evidence.txn_id != transaction_id:
        raise ValueError(
            "Evidence transaction ID does not match requested transaction"
        )

    marker_count = (
        evidence.marker_count
        if evidence.marker_count is not None
        else evidence.marker_comment_count
    )

    # More than one marker occurrence means the write was duplicated.
    if marker_count > 1:
        return TransactionState.DUPLICATE_DETECTED

    # Exactly one marker and a closed issue means the write completed.
    if evidence.is_closed and marker_count == 1:
        return TransactionState.SUCCEEDED

    # No marker and an open issue means there is no evidence the write ran.
    if not evidence.is_closed and marker_count == 0:
        return TransactionState.NOT_EXECUTED

    # All other combinations are ambiguous.
    return TransactionState.UNRESOLVED
