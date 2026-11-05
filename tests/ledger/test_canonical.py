
import json
from datetime import UTC, datetime, timedelta, timezone
from enum import Enum

import pytest
from pydantic import BaseModel

from app.ledger.canonical import canonical_json, canonical_json_bytes


def test_dictionary_key_order_does_not_change_output():
    first = {"b": 2, "a": 1}
    second = {"a": 1, "b": 2}

    assert canonical_json(first) == canonical_json(second)


def test_output_has_no_unnecessary_whitespace():
    assert canonical_json({"name": "trustrail", "version": 1}) == (
        '{"name":"trustrail","version":1}'
    )


def test_unicode_is_preserved():
    result = canonical_json({"message": "नमस्ते"})
    assert result == '{"message":"नमस्ते"}'


def test_nested_objects_are_canonicalized():
    value = {"outer": {"z": 1, "a": 2}, "items": [{"y": 2, "x": 1}]}

    assert canonical_json(value) == (
        '{"items":[{"x":1,"y":2}],"outer":{"a":2,"z":1}}'
    )


def test_datetime_is_normalized_to_utc():
    utc_time = datetime(2026, 11, 5, 10, 30, tzinfo=UTC)
    offset_time = datetime(
        2026, 11, 5, 15, 30, tzinfo=UTC + timedelta(hours=5)
    )

    assert canonical_json({"ts": utc_time}) == canonical_json({"ts": offset_time})


def test_naive_datetime_is_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        canonical_json({"ts": datetime(2026, 11, 5, 10, 30)})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_float_is_rejected(value):
    with pytest.raises(ValueError, match="NaN or infinity"):
        canonical_json({"value": value})


def test_non_string_dictionary_key_is_rejected():
    with pytest.raises(TypeError, match="keys must be strings"):
        canonical_json({1: "invalid"})


def test_pydantic_model_is_supported():
    class Example(BaseModel):
        name: str
        count: int

    model = Example(name="trustrail", count=2)

    assert canonical_json(model) == '{"count":2,"name":"trustrail"}'


def test_enum_is_serialized_using_its_value():
    class Status(str, Enum):
        APPROVED = "APPROVED"

    assert canonical_json({"status": Status.APPROVED}) == (
        '{"status":"APPROVED"}'
    )


def test_bytes_are_utf8_encoded():
    result = canonical_json_bytes({"message": "नमस्ते"})

    assert isinstance(result, bytes)
    assert result == '{"message":"नमस्ते"}'.encode("utf-8")
    assert json.loads(result.decode("utf-8")) == {"message": "नमस्ते"}


def test_unsupported_type_is_rejected():
    with pytest.raises(TypeError, match="Unsupported canonical JSON type"):
        canonical_json({"value": object()})
def test_datetime_is_normalized_to_utc():
    utc_time = datetime(2026, 11, 5, 10, 30, tzinfo=UTC)
    offset_time = datetime(
        2026, 11, 5, 15, 30, tzinfo=timezone(timedelta(hours=5))
    )

    assert canonical_json({"ts": utc_time}) == canonical_json({"ts": offset_time})