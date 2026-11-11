from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.otari.budget_service import (
    OtariBudgetService,
    PlannerBudget,
    PlannerUsage,
    PlannerUsageSeries,
)
from app.otari.exceptions import (
    OtariAPIError,
    OtariAuthenticationError,
    OtariConnectionError,
    OtariResponseError,
    OtariTimeoutError,
)

router = APIRouter(prefix="/api/v1/integrations/otari", tags=["Otari"])


@router.get("/tools")
async def get_tools(request: Request) -> dict:
    client = getattr(request.app.state, "planner_client", None)
    if client is None:
        raise HTTPException(status_code=503, detail="Otari planner is not configured")
    try:
        data = await client.tools()
    except Exception as exc:
        raise _upstream_error(exc) from exc
    raw_tools = data.get("tools", data.get("data", []))
    tools = []
    for item in raw_tools if isinstance(raw_tools, list) else []:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("id") or item.get("type")
        if name in {"otari_web_search", "otari_web_fetch"}:
            tools.append({
                "name": name,
                "available": item.get("available"),
                "unavailable_reason": (
                    item.get("unavailable_reason") or item.get("reason")
                ),
            })
    return {"tools": tools, "planner_model": request.app.state.settings.tr_planner_model}


def _service(request: Request) -> OtariBudgetService:
    service = getattr(request.app.state, "otari_budget_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Otari budget service is not configured",
        )
    return service


def _upstream_error(exc: Exception) -> HTTPException:
    if isinstance(exc, OtariAuthenticationError):
        return HTTPException(status_code=502, detail="Otari authentication failed")
    if isinstance(exc, OtariAPIError):
        if exc.status_code == 403:
            return HTTPException(status_code=502, detail="Otari denied budget access")
        if exc.status_code == 429:
            return HTTPException(status_code=503, detail="Otari rate limit reached")
        return HTTPException(status_code=502, detail="Otari returned an upstream error")
    if isinstance(exc, (OtariConnectionError, OtariTimeoutError)):
        return HTTPException(status_code=503, detail="Otari is temporarily unavailable")
    if isinstance(exc, OtariResponseError):
        return HTTPException(status_code=502, detail="Otari returned invalid data")
    return HTTPException(status_code=502, detail="Otari integration failed")


@router.get("/budget", response_model=PlannerBudget)
async def get_budget(request: Request, refresh: bool = Query(default=False)) -> PlannerBudget:
    try:
        return await _service(request).budget(refresh=refresh)
    except (
        OtariAuthenticationError,
        OtariAPIError,
        OtariConnectionError,
        OtariResponseError,
        OtariTimeoutError,
    ) as exc:
        raise _upstream_error(exc) from exc


@router.get("/usage", response_model=PlannerUsage)
async def get_usage(request: Request, refresh: bool = Query(default=False)) -> PlannerUsage:
    try:
        return await _service(request).usage(refresh=refresh)
    except (
        OtariAuthenticationError,
        OtariAPIError,
        OtariConnectionError,
        OtariResponseError,
        OtariTimeoutError,
    ) as exc:
        raise _upstream_error(exc) from exc


@router.get("/usage/series", response_model=PlannerUsageSeries)
async def get_usage_series(
    request: Request,
    bucket: str = Query(default="day"),
    refresh: bool = Query(default=False),
) -> PlannerUsageSeries:
    try:
        return await _service(request).series(bucket=bucket, refresh=refresh)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (
        OtariAuthenticationError,
        OtariAPIError,
        OtariConnectionError,
        OtariResponseError,
        OtariTimeoutError,
    ) as exc:
        raise _upstream_error(exc) from exc
