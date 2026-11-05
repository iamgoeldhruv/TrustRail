
import pytest

from app.txn import TransactionState, transition


@pytest.mark.parametrize(
    ("current_state", "target_state"),
    [
        (
            TransactionState.PROPOSED,
            TransactionState.VALIDATING,
        ),
        (
            TransactionState.VALIDATING,
            TransactionState.DENIED,
        ),
        (
            TransactionState.VALIDATING,
            TransactionState.PENDING_APPROVAL,
        ),
        (
            TransactionState.PENDING_APPROVAL,
            TransactionState.APPROVED,
        ),
        (
            TransactionState.PENDING_APPROVAL,
            TransactionState.REJECTED,
        ),
        (
            TransactionState.APPROVED,
            TransactionState.PRECHECK,
        ),
        (
            TransactionState.PRECHECK,
            TransactionState.DISPATCHING,
        ),
        (
            TransactionState.PRECHECK,
            TransactionState.APPROVAL_INVALIDATED,
        ),
        (
            TransactionState.DISPATCHING,
            TransactionState.SUCCEEDED,
        ),
        (
            TransactionState.DISPATCHING,
            TransactionState.FAILED,
        ),
        (
            TransactionState.DISPATCHING,
            TransactionState.FAILED_SAFE,
        ),
        (
            TransactionState.DISPATCHING,
            TransactionState.INDETERMINATE,
        ),
        (
            TransactionState.FAILED_SAFE,
            TransactionState.PRECHECK,
        ),
        (
            TransactionState.INDETERMINATE,
            TransactionState.RECONCILING,
        ),
        (
            TransactionState.RECONCILING,
            TransactionState.SUCCEEDED,
        ),
        (
            TransactionState.RECONCILING,
            TransactionState.NOT_EXECUTED,
        ),
        (
            TransactionState.RECONCILING,
            TransactionState.UNRESOLVED,
        ),
        (
            TransactionState.RECONCILING,
            TransactionState.DUPLICATE_DETECTED,
        ),
    ],
)
def test_valid_transition(
    current_state: TransactionState,
    target_state: TransactionState,
) -> None:
    result = transition(current_state, target_state)

    assert result == target_state

from app.txn import InvalidTransitionError


@pytest.mark.parametrize(
    ("current_state", "target_state"),
    [
        (
            TransactionState.PROPOSED,
            TransactionState.SUCCEEDED,
        ),
        (
            TransactionState.PROPOSED,
            TransactionState.APPROVED,
        ),
        (
            TransactionState.VALIDATING,
            TransactionState.DISPATCHING,
        ),
        (
            TransactionState.PENDING_APPROVAL,
            TransactionState.DISPATCHING,
        ),
        (
            TransactionState.APPROVED,
            TransactionState.DISPATCHING,
        ),
        (
            TransactionState.DISPATCHING,
            TransactionState.PROPOSED,
        ),
        (
            TransactionState.SUCCEEDED,
            TransactionState.DISPATCHING,
        ),
        (
            TransactionState.INDETERMINATE,
            TransactionState.SUCCEEDED,
        ),
        (
            TransactionState.RECONCILING,
            TransactionState.DISPATCHING,
        ),
    ],
)
def test_invalid_transition(
    current_state: TransactionState,
    target_state: TransactionState,
) -> None:
    with pytest.raises(InvalidTransitionError):
        transition(current_state, target_state)

from app.txn import ALLOWED_TRANSITIONS


@pytest.mark.parametrize(
    "state",
    [
        TransactionState.DENIED,
        TransactionState.REJECTED,
        TransactionState.APPROVAL_INVALIDATED,
        TransactionState.SUCCEEDED,
        TransactionState.FAILED,
        TransactionState.NOT_EXECUTED,
        TransactionState.UNRESOLVED,
        TransactionState.DUPLICATE_DETECTED,
    ],
)
def test_terminal_states_have_no_outgoing_transitions(
    state: TransactionState,
) -> None:
    assert ALLOWED_TRANSITIONS[state] == frozenset()

def test_transition_table_covers_all_states() -> None:
    assert set(ALLOWED_TRANSITIONS.keys()) == set(
        TransactionState
    )
