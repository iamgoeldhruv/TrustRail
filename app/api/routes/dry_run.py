
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from app.core.config import settings
from app.dryrun.models import DryRunResponse
from app.dryrun.service import DryRunError, dry_run_policy
from app.otari.mcp import OtariMCPClient
from app.policy.models import Policy


router = APIRouter(
    prefix="/api/v1/policies",
    tags=["Policy Dry-run"],
)


class DryRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    policy: Policy


@router.post(
    "/dryrun",
    response_model=DryRunResponse,
)
async def dry_run(
    request: DryRunRequest,
) -> DryRunResponse:
    server_id = settings.otari_mcp_server_id

    if not server_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Otari MCP server is not configured",
        )

    try:
        async with OtariMCPClient(
            base_url=settings.otari_base_url,
            api_key=settings.otari_api_key,
            timeout=settings.otari_timeout,
        ) as client:
            return await dry_run_policy(
                policy=request.policy,
                client=client,
                server_id=server_id,
            )

    except DryRunError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
