
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.otari.exceptions import (
    OtariAPIError,
    OtariAuthenticationError,
    OtariConnectionError,
    OtariError,
    OtariResponseError,
    OtariTimeoutError,
)
from app.policy.compiler import PolicyCompiler
from app.policy.compiler_models import AmbiguousResponse
from app.policy.models import CompiledPolicyResponse


router = APIRouter(
    prefix="/api/v1/policies",
    tags=["Policy Compilation"],
)


class PolicyCompileRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    user_request: str = Field(min_length=1, max_length=10_000)


@router.post(
    "/compile",
    response_model=CompiledPolicyResponse | AmbiguousResponse,
)
async def compile_policy(
    payload: PolicyCompileRequest,
    request: Request,
) -> CompiledPolicyResponse | AmbiguousResponse:
    compiler: PolicyCompiler | None = getattr(
        request.app.state,
        "policy_compiler",
        None,
    )

    if compiler is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Policy compiler is not initialized",
        )

    if not payload.user_request.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Policy request cannot be empty",
        )

    try:
        return await compiler.compile(
            user_request=payload.user_request,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    except (OtariConnectionError, OtariTimeoutError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Otari is temporarily unavailable",
        ) from exc

    except (
        OtariAPIError,
        OtariAuthenticationError,
        OtariResponseError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Otari could not complete the policy compilation request",
        ) from exc

    except OtariError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="An Otari error occurred during policy compilation",
        ) from exc
