from app.reconcile.classifier import classify_reconciliation
from app.reconcile.models import IssueActivityEvidence
from app.txn.states import TransactionState


def _evidence(marker_count: int) -> IssueActivityEvidence:
    return IssueActivityEvidence(
        repository="owner/repository",
        issue_number=1,
        issue_state="closed",
        is_closed=True,
        total_comments=1,
        txn_id="txn-1",
        marker_comment_count=1,
        marker_count=marker_count,
        matching_comment_ids=[42],
    )


def test_reconciliation_succeeds_for_one_marker_occurrence() -> None:
    assert classify_reconciliation("txn-1", _evidence(1)) is TransactionState.SUCCEEDED


def test_reconciliation_detects_duplicate_marker_occurrences() -> None:
    assert (
        classify_reconciliation("txn-1", _evidence(2))
        is TransactionState.DUPLICATE_DETECTED
    )
