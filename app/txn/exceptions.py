
from uuid import UUID

from app.txn.states import TransactionState


class InvalidTransitionError(Exception):
    """
    Raised when a transaction attempts an illegal state transition.
    """

    def __init__(
        self,
        current_state: TransactionState,
        target_state: TransactionState,
    ) -> None:
        self.current_state = current_state
        self.target_state = target_state

        super().__init__(
            f"Invalid transaction transition: "
            f"{current_state.value} -> {target_state.value}"
        )


class TransactionNotFoundError(LookupError):
    """Raised when an operation requires a transaction that does not exist."""

    def __init__(self, transaction_id: UUID | str) -> None:
        super().__init__(f"Transaction not found: {transaction_id}")
        self.transaction_id = transaction_id
