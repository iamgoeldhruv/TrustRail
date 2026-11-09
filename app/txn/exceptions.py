
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

class ApprovalAlreadyAttachedError(Exception):
    """Raised when a different approval is already linked to a transaction."""

    def __init__(
        self,
        transaction_id: UUID | str,
        existing_approval_id: str,
        attempted_approval_id: str,
    ) -> None:
        self.transaction_id = transaction_id
        self.existing_approval_id = existing_approval_id
        self.attempted_approval_id = attempted_approval_id

        super().__init__(
            f"Transaction {transaction_id} already has approval "
            f"{existing_approval_id}; cannot attach {attempted_approval_id}"
        )