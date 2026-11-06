from app.txn.states import TransactionState


ALLOWED_TRANSITIONS: dict[TransactionState, frozenset[TransactionState]] = {
    TransactionState.PROPOSED: frozenset(
        {
            TransactionState.VALIDATING,
        }
    ),
    TransactionState.VALIDATING: frozenset(
        {
            TransactionState.DENIED,
            TransactionState.PENDING_APPROVAL,
        }
    ),
    TransactionState.DENIED: frozenset(),
    TransactionState.PENDING_APPROVAL: frozenset(
        {
            TransactionState.APPROVED,
            TransactionState.REJECTED,
        }
    ),
    TransactionState.REJECTED: frozenset(),
    TransactionState.APPROVED: frozenset(
        {
            TransactionState.PRECHECK,
        }
    ),
    TransactionState.PRECHECK: frozenset(
        {
            TransactionState.APPROVAL_INVALIDATED,
            TransactionState.DISPATCHING,
        }
    ),
    TransactionState.APPROVAL_INVALIDATED: frozenset(),
    TransactionState.DISPATCHING: frozenset(
        {
            TransactionState.SUCCEEDED,
            TransactionState.FAILED,
            TransactionState.FAILED_SAFE,
            TransactionState.INDETERMINATE,
            TransactionState.APPROVAL_INVALIDATED,
        }
    ),
    TransactionState.SUCCEEDED: frozenset(),
    TransactionState.FAILED: frozenset(),
    TransactionState.FAILED_SAFE: frozenset(
        {
            TransactionState.PRECHECK,
        }
    ),
    TransactionState.INDETERMINATE: frozenset(
        {
            TransactionState.RECONCILING,
        }
    ),
    TransactionState.RECONCILING: frozenset(
        {
            TransactionState.SUCCEEDED,
            TransactionState.NOT_EXECUTED,
            TransactionState.UNRESOLVED,
            TransactionState.DUPLICATE_DETECTED,
        }
    ),
    TransactionState.NOT_EXECUTED: frozenset(),
    TransactionState.UNRESOLVED: frozenset(),
    TransactionState.DUPLICATE_DETECTED: frozenset(),
}

from app.txn.exceptions import InvalidTransitionError


def transition(
    current_state: TransactionState,
    target_state: TransactionState,
) -> TransactionState:

    allowed_states = ALLOWED_TRANSITIONS[current_state]

    if target_state not in allowed_states:
        raise InvalidTransitionError(
            current_state=current_state,
            target_state=target_state,
        )

    return target_state
