"""Low-level HTTP transport for the SudoMock SDK.

Provides :class:`SyncTransport` and :class:`AsyncTransport` that wrap
``httpx.Client`` / ``httpx.AsyncClient`` with:

* ``x-api-key`` authentication header
* Automatic error → exception mapping
* Retry with exponential backoff for 429 / 5xx via *tenacity*
* Configurable timeouts (default vs. render)
"""

from __future__ import annotations

import importlib.metadata
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from .exceptions import (
    AuthenticationError,
    InsufficientCreditsError,
    NotFoundError,
    RateLimitError,
    ServerError,
    SudoMockError,
    ValidationError,
)

try:
    _SDK_VERSION = importlib.metadata.version("sudomock")
except importlib.metadata.PackageNotFoundError:
    _SDK_VERSION = "0.0.0-dev"

_USER_AGENT = f"sudomock-python/{_SDK_VERSION}"

DEFAULT_BASE_URL = "https://api.sudomock.com"
DEFAULT_TIMEOUT = 30.0
DEFAULT_RENDER_TIMEOUT = 120.0
DEFAULT_MAX_RETRIES = 3


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------


def _is_retryable(exc: BaseException) -> bool:
    """Return True if the exception is worth retrying."""
    if isinstance(exc, (ServerError, RateLimitError)):
        return True
    return bool(isinstance(exc, httpx.TransportError))


def _raise_for_status(response: httpx.Response) -> None:
    """Map HTTP error responses to typed SDK exceptions."""
    if response.is_success:
        return

    status = response.status_code

    # Try to parse JSON body for error details
    body: Any = None
    detail = f"HTTP {status}"
    try:
        body = response.json()
        detail = body.get("detail", detail) if isinstance(body, dict) else detail
    except Exception:
        body = response.text or None

    if status == 401:
        raise AuthenticationError(detail, status_code=status, body=body)

    if status == 402:
        credits_reset_at = None
        if isinstance(body, dict):
            credits_reset_at = body.get("credits_reset_at")
        raise InsufficientCreditsError(
            detail, status_code=status, body=body, credits_reset_at=credits_reset_at
        )

    if status == 404:
        raise NotFoundError(detail, status_code=status, body=body)

    if status == 422:
        raise ValidationError(detail, status_code=status, body=body)

    if status == 429:
        retry_after: float | None = None
        if isinstance(body, dict):
            error_obj = body.get("error")
            if isinstance(error_obj, dict):
                retry_after = error_obj.get("retry_after")
        raise RateLimitError(detail, status_code=status, body=body, retry_after=retry_after)

    if status >= 500:
        raise ServerError(detail, status_code=status, body=body)

    # Catch-all for unexpected 4xx codes
    raise SudoMockError(detail, status_code=status, body=body)


# ---------------------------------------------------------------------------
# Synchronous transport
# ---------------------------------------------------------------------------


class SyncTransport:
    """Synchronous HTTP transport backed by ``httpx.Client``."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        render_timeout: float = DEFAULT_RENDER_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._render_timeout = render_timeout
        self._max_retries = max_retries

        self._client = httpx.Client(
            base_url=self._base_url,
            headers={
                "x-api-key": self._api_key,
                "user-agent": _USER_AGENT,
                "accept": "application/json",
            },
            timeout=httpx.Timeout(self._timeout),
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        """Send an HTTP request with automatic retry on transient errors.

        Non-retryable errors (401, 402, 404, 422) are raised immediately.
        """
        effective_timeout = timeout or self._timeout

        @retry(
            retry=retry_if_exception(_is_retryable),
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(multiplier=0.5, min=0.25, max=8),
            reraise=True,
        )
        def _do() -> httpx.Response:
            # Filter out None values from params
            clean_params = {k: v for k, v in params.items() if v is not None} if params else None
            resp = self._client.request(
                method,
                path,
                params=clean_params,
                json=json,
                timeout=effective_timeout,
            )
            _raise_for_status(resp)
            return resp

        return _do()

    def close(self) -> None:
        self._client.close()


# ---------------------------------------------------------------------------
# Asynchronous transport
# ---------------------------------------------------------------------------


class AsyncTransport:
    """Asynchronous HTTP transport backed by ``httpx.AsyncClient``."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        render_timeout: float = DEFAULT_RENDER_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._render_timeout = render_timeout
        self._max_retries = max_retries

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "x-api-key": self._api_key,
                "user-agent": _USER_AGENT,
                "accept": "application/json",
            },
            timeout=httpx.Timeout(self._timeout),
        )

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        """Send an async HTTP request with automatic retry on transient errors."""
        effective_timeout = timeout or self._timeout

        @retry(
            retry=retry_if_exception(_is_retryable),
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(multiplier=0.5, min=0.25, max=8),
            reraise=True,
        )
        async def _do() -> httpx.Response:
            clean_params = {k: v for k, v in params.items() if v is not None} if params else None
            resp = await self._client.request(
                method,
                path,
                params=clean_params,
                json=json,
                timeout=effective_timeout,
            )
            _raise_for_status(resp)
            return resp

        return await _do()

    async def close(self) -> None:
        await self._client.aclose()
