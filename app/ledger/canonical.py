
from __future__ import annotations

import json
import math
from collections.abc import Mapping
from datetime import UTC, date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel


def _normalize(value: Any) -> Any:
   

    if isinstance(value, BaseModel):
        return _normalize(value.model_dump(mode="python"))

    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Canonical timestamps must be timezone-aware")

        return value.astimezone(UTC).isoformat(timespec="microseconds").replace(
            "+00:00", "Z"
        )

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, Enum):
        return _normalize(value.value)

    if isinstance(value, UUID):
        return str(value)

    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}

        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(
                    f"Canonical JSON object keys must be strings, got {type(key).__name__}"
                )

            normalized[key] = _normalize(item)

        return normalized

    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]

    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Canonical JSON does not support NaN or infinity")

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    raise TypeError(f"Unsupported canonical JSON type: {type(value).__name__}")


def canonical_json(value: Any) -> str:
   

    normalized = _normalize(value)

    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_json_bytes(value: Any) -> bytes:
   

    return canonical_json(value).encode("utf-8")
