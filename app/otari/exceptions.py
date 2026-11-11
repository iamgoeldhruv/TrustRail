
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class OtariError(Exception):
    """Base exception for Otari client errors."""


class OtariAuthenticationError(OtariError):
    """Raised when Otari rejects authentication."""


class OtariAPIError(OtariError):
    """Raised when Otari returns an unsuccessful HTTP response."""

    def __init__(
        self,
        message: str,
        status_code: int,
        *,
        code: str | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.request_id = request_id


class OtariConnectionError(OtariError):
    """Raised when connection to Otari fails."""


class OtariTimeoutError(OtariError):
    """Raised when an Otari request times out."""


class OtariResponseError(OtariError):
    """Raised when Otari returns an invalid response."""


class OtariGuardrailError(OtariAPIError):
    """Raised when Otari's mandatory guardrail prevents planner inference."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        code: str | None = None,
        request_id: str | None = None,
        profile: str = "prompt-injection",
        mode: str = "block",
        reason: str | None = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=status_code,
            code=code,
            request_id=request_id,
        )
        self.profile = profile
        self.mode = mode
        self.reason = reason


class OtariGuardrailBlockedError(OtariGuardrailError):
    """Raised for the documented 403 guardrail_violation response."""


class OtariGuardrailUnavailableError(OtariGuardrailError):
    """Raised when mandatory guardrail evaluation fails closed."""


class OtariMCPError(OtariError):
    """
    Base exception for caller-orchestrated MCP errors.

    Preserves both request IDs:
    - body_request_id: request_id from the JSON error body
    - header_request_id: Otari-Request-ID from HTTP headers

    request_id remains available for compatibility with older callers.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        code: str | None = None,
        execution_state: str | None = None,
        request_id: str | None = None,
        *,
        body_request_id: str | None = None,
        header_request_id: str | None = None,
        retry_after: str | None = None,
    ) -> None:
        super().__init__(message)

        self.status_code = status_code
        self.code = code
        self.execution_state = execution_state

        # Backward compatibility: old callers pass request_id.
        self.body_request_id = body_request_id or request_id
        self.header_request_id = header_request_id

        self.retry_after = retry_after

    @property
    def request_id(self) -> str | None:
        """Legacy accessor; prefer the explicit ID attributes."""
        return self.body_request_id or self.header_request_id


class OtariMCPNotStartedError(OtariMCPError):
    """
    Otari explicitly confirms that the MCP tool was not dispatched.

    This does not mean TrustRail should automatically retry.
    """

    pass


class OtariMCPOutcomeUnknownError(OtariMCPError):
    """
    MCP dispatch began, but no definitive result was returned.

    The external operation may already have mutated state.
    Never automatically retry this operation.
    """

    pass


class OtariMCPServerChangedError(OtariMCPNotStartedError):
    """The stored MCP server configuration revision has changed."""


class OtariMCPResponseError(OtariMCPError):
    """Otari returned a malformed or unexpected MCP response."""

class OtariExecutionState(StrEnum):
    """Execution certainty reported by Otari."""

    NOT_STARTED = "not_started"
    OUTCOME_UNKNOWN = "outcome_unknown"


class OtariMCPErrorCode(StrEnum):
    """Stable MCP error codes documented by Otari."""

    INVALID_REQUEST = "invalid_request"
    AUTHENTICATION_FAILED = "authentication_failed"
    MISDIRECTED_REQUEST = "misdirected_request"
    PAYMENT_REQUIRED = "payment_required"
    FORBIDDEN = "forbidden"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"

    MCP_SERVER_NOT_FOUND = "mcp_server_not_found"
    MCP_SERVER_CHANGED = "mcp_server_changed"
    MCP_TOOL_NOT_ALLOWED = "mcp_tool_not_allowed"
    UNSAFE_MCP_URL = "unsafe_mcp_url"

    MCP_RESOLUTION_FAILED = "mcp_resolution_failed"
    MCP_CREDENTIALS_UNAVAILABLE = "mcp_credentials_unavailable"

    MCP_DISCOVERY_LIMIT_EXCEEDED = "mcp_discovery_limit_exceeded"
    MCP_DISCOVERY_CAPACITY_UNAVAILABLE = (
        "mcp_discovery_capacity_unavailable"
    )

    MCP_CAPACITY_UNAVAILABLE = "mcp_capacity_unavailable"
    SERVICE_UNAVAILABLE = "service_unavailable"
    MCP_CONNECTION_FAILED = "mcp_connection_failed"

    MCP_OUTCOME_UNKNOWN = "mcp_outcome_unknown"
    MCP_RESULT_TOO_LARGE = "mcp_result_too_large"


class OtariMCPErrorBody(BaseModel):
    """
    Shared error response returned by Otari MCP endpoints.

    Used by both:
    - GET /api/v1/mcp/servers/{server_id}/tools
    - POST /api/v1/mcp/execute
    """

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    detail: str = Field(min_length=1)
    code: OtariMCPErrorCode
    execution_state: OtariExecutionState
    request_id: str = Field(min_length=1)
