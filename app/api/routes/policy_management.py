from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings
from app.policy.models import Policy
from app.policy.service import PolicyService, PolicyServiceError

router = APIRouter(prefix="/api/v1/policies", tags=["Policy Management"])


class PolicyActivateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    policy: Policy
    nl_text: str = Field(min_length=1, max_length=10_000)


@router.post("/activate", status_code=status.HTTP_201_CREATED)
async def activate_policy(payload: PolicyActivateRequest) -> dict[str, object]:
    try:
        return PolicyService(settings.tr_db_path).activate(
            policy=payload.policy,
            nl_text=payload.nl_text,
        )
    except PolicyServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get("/active")
async def get_active_policy() -> dict[str, object]:
    try:
        active = PolicyService(settings.tr_db_path).active()
    except PolicyServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return active or {"status": "NONE", "policy": None}
