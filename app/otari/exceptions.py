
class OtariError(Exception):
    """Base exception for Otari client errors."""


class OtariAuthenticationError(OtariError):
    """Raised when Otari rejects authentication."""


class OtariAPIError(OtariError):
    """Raised when Otari returns an unsuccessful HTTP response."""

    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


class OtariConnectionError(OtariError):
    """Raised when connection to Otari fails."""


class OtariTimeoutError(OtariError):
    """Raised when an Otari request times out."""


class OtariResponseError(OtariError):
    """Raised when Otari returns an invalid response."""
