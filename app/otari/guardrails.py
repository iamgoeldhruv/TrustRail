from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class GuardrailStatus(StrEnum):
    PASSED = "PASSED"
    BLOCKED = "BLOCKED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


class OtariGuardrailResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    profile: str = Field(min_length=1)
    mode: str = Field(min_length=1)
    valid: bool | None = None
    status: str = Field(min_length=1)
    reason: str | None = None
    score: float | None = None

    @property
    def trustrail_status(self) -> GuardrailStatus:
        if self.status == "evaluated" and self.valid is True:
            return GuardrailStatus.PASSED
        if self.status == "evaluated" and self.valid is False:
            return GuardrailStatus.BLOCKED
        if self.status == "unavailable":
            return GuardrailStatus.UNAVAILABLE
        return GuardrailStatus.UNKNOWN


class GuardrailEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: GuardrailStatus
    profile: str | None = None
    mode: str | None = None
    verdict: bool | None = None
    reason: str | None = None
    http_status: int | None = None
    request_id: str | None = None
    routing_policy: str
    run_id: str
    step_id: str
    occurred_at: datetime

    def ledger_payload(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json", exclude_none=True)
        payload["status"] = self.status.value
        return payload


def parse_guardrail_header(value: str | None) -> list[OtariGuardrailResult]:
    if not value:
        return []
    try:
        raw = json.loads(value)
    except (TypeError, ValueError):
        return []
    if not isinstance(raw, list):
        return []
    results: list[OtariGuardrailResult] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        try:
            results.append(OtariGuardrailResult.model_validate(entry))
        except ValueError:
            continue
    return results


def now_utc() -> datetime:
    return datetime.now(UTC)
