from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.otari.client import OtariClient
from app.otari.exceptions import OtariResponseError


class OtariLimit(BaseModel):
    model_config = ConfigDict(extra="ignore")

    scope: str
    provider: str | None = None
    resets_at: datetime | None = None
    limit_usd: float | None = Field(default=None, ge=0)
    used_usd: float | None = Field(default=None, ge=0)
    remaining_usd: float | None = Field(default=None, ge=0)
    limit_tokens: int | None = Field(default=None, ge=0)
    used_tokens: int | None = Field(default=None, ge=0)
    remaining_tokens: int | None = Field(default=None, ge=0)
    limit_requests: int | None = Field(default=None, ge=0)
    used_requests: int | None = Field(default=None, ge=0)
    remaining_requests: int | None = Field(default=None, ge=0)


class PlannerBudget(BaseModel):
    provider: str = "otari"
    credential_role: str = "planner"
    key_label: str = "agent-run"
    budgets_enforced: bool
    remaining_usd: float | None = Field(default=None, ge=0)
    limits: list[OtariLimit]
    last_synced_at: datetime
    source: str = "live_otari_api"


class UsageTotals(BaseModel):
    model_config = ConfigDict(extra="ignore")

    cost: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    request_count: int
    error_count: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


class UsageGroup(BaseModel):
    model_config = ConfigDict(extra="ignore")

    key: str | None = None
    label: str | None = None
    cost: float
    tokens: int
    requests: int
    is_other: bool = False


class PlannerUsage(BaseModel):
    provider: str = "otari"
    credential_role: str = "planner"
    totals: UsageTotals
    by_model: list[UsageGroup] = []
    start_date: datetime
    end_date: datetime
    last_synced_at: datetime
    source: str = "live_otari_api"


class UsagePoint(BaseModel):
    model_config = ConfigDict(extra="ignore")

    bucket_start: datetime
    cost: float
    tokens: int
    requests: int
    input_tokens: int = 0
    output_tokens: int = 0


class PlannerUsageSeries(BaseModel):
    provider: str = "otari"
    credential_role: str = "planner"
    start_date: datetime
    end_date: datetime
    bucket: str
    group_by: str
    points: list[UsagePoint]
    last_synced_at: datetime
    source: str = "live_otari_api"


class OtariBudgetService:
    """Read-only, cached access to the planner API key's scoped Otari data."""

    def __init__(self, client: OtariClient, cache_ttl_seconds: float = 45.0) -> None:
        self.client = client
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache: dict[str, tuple[float, BaseModel]] = {}
        self._locks = {key: asyncio.Lock() for key in ("budget", "usage", "series")}

    async def _cached(
        self,
        key: str,
        loader: Any,
        *,
        refresh: bool,
    ) -> BaseModel:
        now = datetime.now(UTC).timestamp()
        cached = self._cache.get(key)
        if not refresh and cached and now - cached[0] < self.cache_ttl_seconds:
            return cached[1]
        async with self._locks[key.split(":", 1)[0]]:
            now = datetime.now(UTC).timestamp()
            cached = self._cache.get(key)
            if not refresh and cached and now - cached[0] < self.cache_ttl_seconds:
                return cached[1]
            value = await loader()
            self._cache[key] = (now, value)
            return value

    async def budget(self, *, refresh: bool = False) -> PlannerBudget:
        async def load() -> PlannerBudget:
            data = await self.client.get_json("key/budget")
            try:
                return PlannerBudget(
                    **data,
                    last_synced_at=datetime.now(UTC),
                )
            except ValidationError as exc:
                raise OtariResponseError("Otari returned an invalid budget response.") from exc

        return cast(PlannerBudget, await self._cached("budget", load, refresh=refresh))

    async def usage(self, *, refresh: bool = False) -> PlannerUsage:
        async def load() -> PlannerUsage:
            data = await self.client.get_json(
                "key/usage/summary",
                params={"dimensions": ["model"]},
            )
            try:
                return PlannerUsage(**data, last_synced_at=datetime.now(UTC))
            except ValidationError as exc:
                raise OtariResponseError("Otari returned an invalid usage response.") from exc

        return cast(PlannerUsage, await self._cached("usage", load, refresh=refresh))

    async def series(
        self,
        *,
        bucket: str = "day",
        refresh: bool = False,
    ) -> PlannerUsageSeries:
        if bucket not in {"day", "hour"}:
            raise ValueError("bucket must be 'day' or 'hour'")

        async def load() -> PlannerUsageSeries:
            data = await self.client.get_json(
                "key/usage/series",
                params={"group_by": "model", "bucket": bucket},
            )
            try:
                return PlannerUsageSeries(
                    **data,
                    last_synced_at=datetime.now(UTC),
                )
            except ValidationError as exc:
                raise OtariResponseError(
                    "Otari returned an invalid usage series response."
                ) from exc

        return cast(
            PlannerUsageSeries,
            await self._cached(f"series:{bucket}", load, refresh=refresh),
        )
