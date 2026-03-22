"""SudoMock SDK exception hierarchy.

All exceptions inherit from :class:`SudoMockError` so callers can
catch the base class for generic error handling.

Hierarchy::

    SudoMockError
    +-- AuthenticationError      (401)
    +-- InsufficientCreditsError (402)
    +-- NotFoundError            (404)
    +-- ValidationError          (422)
    +-- RateLimitError           (429)
    +-- ServerError              (500+)
"""

from __future__ import annotations

from typing import Any, Optional


class SudoMockError(Exception):
    """Base exception for all SudoMock SDK errors.

    Attributes:
        message: Human-readable error description.
        status_code: HTTP status code that triggered this error, if any.
        body: Raw response body (parsed JSON or string), if available.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        body: Optional[Any] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.body = body

    def __repr__(self) -> str:
        cls = self.__class__.__name__
        return f"{cls}(message={self.message!r}, status_code={self.status_code})"


class AuthenticationError(SudoMockError):
    """Raised when the API key is missing, invalid, or revoked (HTTP 401)."""


class InsufficientCreditsError(SudoMockError):
    """Raised when the account has no remaining credits (HTTP 402).

    Attributes:
        credits_reset_at: ISO-8601 timestamp when credits will reset, if provided.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        body: Optional[Any] = None,
        credits_reset_at: Optional[str] = None,
    ) -> None:
        super().__init__(message, status_code=status_code, body=body)
        self.credits_reset_at = credits_reset_at


class NotFoundError(SudoMockError):
    """Raised when the requested resource does not exist (HTTP 404)."""


class ValidationError(SudoMockError):
    """Raised when request parameters fail validation (HTTP 422)."""


class RateLimitError(SudoMockError):
    """Raised when the API rate limit has been exceeded (HTTP 429).

    Attributes:
        retry_after: Seconds to wait before retrying, if provided by the server.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        body: Optional[Any] = None,
        retry_after: Optional[float] = None,
    ) -> None:
        super().__init__(message, status_code=status_code, body=body)
        self.retry_after = retry_after


class ServerError(SudoMockError):
    """Raised when the API returns an internal server error (HTTP 500+)."""
