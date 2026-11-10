from enum import StrEnum


class ApprovalInvalidationReason(StrEnum):
    REVISION_CHANGED = "REVISION_CHANGED"
    FACTS_CHANGED = "FACTS_CHANGED"
    POLICY_CHANGED = "POLICY_CHANGED"
    NOW_DENIED = "NOW_DENIED"
