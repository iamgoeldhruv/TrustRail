import asyncio
from dataclasses import dataclass
from enum import Enum
from contextvars import ContextVar, Token

_drop_response_requested: ContextVar[bool] = ContextVar(
    "drop_response_requested",
    default=False,
)


def mark_response_for_drop() -> None:
    """Mark the current MCP HTTP request's response for dropping."""
    _drop_response_requested.set(True)


def response_drop_requested() -> bool:
    return _drop_response_requested.get()


def set_response_drop_flag(value: bool = False) -> Token[bool]:
    return _drop_response_requested.set(value)


def reset_response_drop_flag(token: Token[bool]) -> None:
    _drop_response_requested.reset(token)

class FaultMode(str, Enum):
    NONE = "none"
    DROP_AFTER_APPLY = "drop_after_apply"
    FAIL_BEFORE_APPLY = "fail_before_apply"
    PARTIAL = "partial"
    DELAY_AFTER_APPLY = "delay_after_apply"


@dataclass
class FaultConfiguration:
    mode: FaultMode = FaultMode.NONE


class FaultController:
    def __init__(self) -> None:
        self._configuration = FaultConfiguration()
        self._lock = asyncio.Lock()

    async def set_mode(self, mode: FaultMode) -> None:
        async with self._lock:
            self._configuration.mode = mode

    async def consume_mode(self) -> FaultMode:
        async with self._lock:
            mode = self._configuration.mode
            self._configuration.mode = FaultMode.NONE
            return mode

    async def get_mode(self) -> FaultMode:
        async with self._lock:
            return self._configuration.mode


fault_controller = FaultController()