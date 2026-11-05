from enum import StrEnum


class ExecutionOutcome(StrEnum):
    SUCCESS = "success"
    IS_ERROR = "is_error"
    NOT_STARTED = "not_started"
    OUTCOME_UNKNOWN = "outcome_unknown"
    CONFLICT = "conflict"
