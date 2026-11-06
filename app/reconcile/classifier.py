
from app.reconcile.models import (
    IssueActivityEvidence,
    ReconciliationResult,
)
from app.txn.states import TransactionState


def classify_reconciliation(
    transaction_id: str,
    evidence: IssueActivityEvidence,
) -> ReconciliationResult:
    """
    Classify an uncertain transaction using authoritative GitHub evidence.

    This function performs no network calls and does not modify the database.
    """

    if evidence.txn_id != transaction_id:
        raise ValueError(
            "GitHub evidence transaction ID does not match the transaction"
        )

    if evidence.marker_comment_count > 1:
        outcome = TransactionState.DUPLICATE_DETECTED
        reason = "Multiple GitHub comments contain the transaction marker"

    elif evidence.is_closed and evidence.marker_comment_count == 1:
        outcome = TransactionState.SUCCEEDED
        reason = "Issue is closed and exactly one transaction marker exists"

    elif not evidence.is_closed and evidence.marker_comment_count == 0:
        outcome = TransactionState.NOT_EXECUTED
        reason = "Issue is open and no transaction marker exists"

    else:
        outcome = TransactionState.UNRESOLVED
        reason = (
            "GitHub issue state and transaction marker evidence "
            "do not establish a definitive outcome"
        )

    return ReconciliationResult(
        transaction_id=transaction_id,
        outcome=outcome,
        reason=reason,
        evidence=evidence,
    )
