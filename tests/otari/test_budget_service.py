import pytest

from app.otari.budget_service import OtariBudgetService
from app.otari.exceptions import OtariResponseError


class FakeClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    async def get_json(self, path, *, params=None):
        self.calls.append((path, params))
        value = self.responses[path]
        return value() if callable(value) else value


def budget_payload():
    return {
        "budgets_enforced": True,
        "remaining_usd": 2.5,
        "limits": [
            {
                "scope": "api_token",
                "provider": None,
                "resets_at": "2026-12-01T00:00:00Z",
                "limit_usd": 4,
                "used_usd": 1.5,
                "remaining_usd": 2.5,
            },
            {
                "scope": "user",
                "provider": None,
                "resets_at": None,
                "limit_usd": None,
                "used_usd": None,
                "remaining_usd": 2.5,
            },
        ],
    }


def usage_payload():
    return {
        "start_date": "2026-11-01T00:00:00Z",
        "end_date": "2026-12-01T00:00:00Z",
        "bucket": "day",
        "totals": {
            "cost": 1.5,
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
            "request_count": 2,
            "error_count": 0,
        },
        "by_model": [{"key": "deepseek", "cost": 1.5, "tokens": 30, "requests": 2}],
    }


def series_payload():
    return {
        "start_date": "2026-11-01T00:00:00Z",
        "end_date": "2026-12-01T00:00:00Z",
        "bucket": "day",
        "group_by": "model",
        "groups": [],
        "points": [
            {
                "bucket_start": "2026-11-01T00:00:00Z",
                "key": "deepseek",
                "cost": 1.5,
                "tokens": 30,
                "requests": 2,
            }
        ],
    }


@pytest.mark.asyncio
async def test_budget_preserves_multiple_limits_and_caches():
    client = FakeClient({"key/budget": budget_payload})
    service = OtariBudgetService(client)

    result = await service.budget()
    cached = await service.budget()

    assert result.remaining_usd == 2.5
    assert [limit.scope for limit in result.limits] == ["api_token", "user"]
    assert cached.last_synced_at == result.last_synced_at
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_usage_and_series_use_documented_parameters():
    client = FakeClient({"key/usage/summary": usage_payload, "key/usage/series": series_payload})
    service = OtariBudgetService(client)

    usage = await service.usage()
    series = await service.series(bucket="hour")

    assert usage.totals.total_tokens == 30
    assert usage.by_model[0].key == "deepseek"
    assert series.points[0].cost == 1.5
    assert client.calls[0] == ("key/usage/summary", {"dimensions": ["model"]})
    assert client.calls[1] == (
        "key/usage/series",
        {"group_by": "model", "bucket": "hour"},
    )


@pytest.mark.asyncio
async def test_invalid_budget_response_is_not_cached_as_zero():
    client = FakeClient(
        {"key/budget": {"budgets_enforced": True, "limits": [{"limit_usd": 4}]}}
    )
    service = OtariBudgetService(client)

    with pytest.raises(OtariResponseError):
        await service.budget()
    assert service._cache == {}
