from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OtariToolCall(BaseModel):
    """Safe projection of gateway-executed web-tool activity."""

    model_config = ConfigDict(extra="allow")

    tool_name: str = Field(min_length=1)
    query: str | None = None
    url: str | None = None
    status: str | None = None
    error: str | None = None
    sources: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResearchEvidence(BaseModel):
    """Bounded evidence metadata passed from research to planning."""

    model_config = ConfigDict(extra="forbid")

    status: str = "NOT_REQUIRED"
    search_queries: list[str] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    fetched_urls: list[str] = Field(default_factory=list)
    claims: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    tool_calls: list[OtariToolCall] = Field(default_factory=list)
    otari_request_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def parse_otari_tool_calls(response: dict[str, Any]) -> list[OtariToolCall]:
    """Parse documented top-level ``otari_tool_calls`` without trusting its shape."""

    raw_calls = response.get("otari_tool_calls")
    if not isinstance(raw_calls, list):
        return []

    parsed: list[OtariToolCall] = []
    for raw in raw_calls:
        if not isinstance(raw, dict):
            continue
        tool_name = _text(raw.get("tool_name") or raw.get("name") or raw.get("type"))
        if tool_name is None:
            continue
        query = _text(raw.get("query"))
        url = _text(raw.get("url"))
        status = _text(raw.get("status"))
        error_value = raw.get("error")
        if isinstance(error_value, str):
            error = _text(error_value)
        elif isinstance(error_value, dict):
            tag = _text(error_value.get("tag"))
            error = tag or "tool_failed"
        else:
            error = None
        sources = raw.get("sources")
        safe_sources = (
            [item for item in sources if isinstance(item, dict)]
            if isinstance(sources, list)
            else []
        )
        metadata = {
            key: value
            for key, value in raw.items()
            if key not in {
                "tool_name", "name", "type", "query", "url", "status",
                "error", "sources",
            }
        }
        parsed.append(
            OtariToolCall(
                tool_name=tool_name,
                query=query,
                url=url,
                status=status,
                error=error,
                sources=safe_sources,
                metadata=metadata,
            )
        )
    return parsed


def research_tools(*, search_max_uses: int, fetch_max_uses: int) -> list[dict[str, Any]]:
    return [
        {"type": "otari_web_search", "max_uses": search_max_uses},
        {"type": "otari_web_fetch"},
    ]
