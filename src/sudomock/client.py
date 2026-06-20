"""Synchronous SudoMock API client.

Usage::

    from sudomock import SudoMock

    client = SudoMock(api_key="sm_xxx")  # or set SUDOMOCK_API_KEY env var
    mockups = client.mockups.list(limit=20)
    render = client.renders.create(
        mockup_uuid="...",
        smart_objects=[{"uuid": "...", "asset": {"url": "https://..."}}],
    )
    print(render.url)
    client.close()
"""

from __future__ import annotations

import os
import time
from typing import Any, Optional, Union

from ._http import (
    DEFAULT_BASE_URL,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RENDER_TIMEOUT,
    DEFAULT_TIMEOUT,
    SyncTransport,
)
from .exceptions import SudoMockError
from .models import (
    AccountInfo,
    AIRender,
    Job,
    JobAccepted,
    Mockup,
    MockupList,
    Render,
    WebhookDeliveryList,
    WebhookEndpoint,
    WebhookEndpointList,
    WebhookSecret,
)

# Module-level alias so webhook resources (which define a ``list`` method that
# would shadow the builtin ``list`` at class scope) can still annotate
# ``list[str]`` for parameters without the method name colliding.
_StrList = list[str]


class _MockupsResource:
    """Mockup template operations (list, get, delete)."""

    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def list(
        self,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        search: Optional[str] = None,
    ) -> MockupList:
        """List mockup templates with optional pagination.

        Args:
            limit: Maximum number of results (default server-side: 20).
            offset: Pagination offset.
            search: Filter mockups by name.

        Returns:
            :class:`MockupList` with ``mockups``, ``total``, ``limit``, ``offset``.
        """
        resp = self._transport.request(
            "GET",
            "/api/v1/mockups",
            params={"limit": limit, "offset": offset, "search": search},
        )
        data = resp.json()["data"]
        return MockupList.model_validate(data)

    def get(self, uuid: str) -> Mockup:
        """Get a single mockup by UUID.

        Args:
            uuid: Mockup identifier.

        Returns:
            :class:`Mockup` with full details including smart objects.

        Raises:
            NotFoundError: If the mockup does not exist.
        """
        resp = self._transport.request("GET", f"/api/v1/mockups/{uuid}")
        data = resp.json()["data"]
        return Mockup.model_validate(data)

    def delete(self, uuid: str) -> None:
        """Delete a mockup by UUID.

        Args:
            uuid: Mockup identifier.

        Raises:
            NotFoundError: If the mockup does not exist.
        """
        self._transport.request("DELETE", f"/api/v1/mockups/{uuid}")


class _RendersResource:
    """Render operations."""

    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def create(
        self,
        *,
        mockup_uuid: str,
        smart_objects: list[dict[str, Any]],
        export_options: Optional[dict[str, Any]] = None,
        export_label: Optional[str] = None,
        is_async: bool = False,
    ) -> Union[Render, JobAccepted]:
        """Create a new render from a mockup template.

        Args:
            mockup_uuid: UUID of the mockup to render.
            smart_objects: List of smart object configurations, each containing
                ``uuid`` and ``asset`` (with ``url``, optional ``fit``, ``rotate``,
                ``position``, ``size``).
            export_options: Optional export settings (``image_format``, ``image_size``,
                ``quality``).
            export_label: Optional label for the export filename.
            is_async: If ``True``, submit the render to the server-side async
                queue and return immediately with a :class:`JobAccepted`
                (HTTP 202). Poll for the result with :meth:`SudoMock.jobs.get`
                or :meth:`SudoMock.jobs.wait`. Defaults to ``False`` (blocking).

        Returns:
            :class:`Render` (synchronous) with ``print_files`` and a convenience
            ``.url`` property, or :class:`JobAccepted` (when ``is_async=True``)
            carrying ``render_uuid`` and ``status_url``.

        Raises:
            InsufficientCreditsError: If the account has no remaining credits.
            ValidationError: If the request parameters are invalid.
        """
        body: dict[str, Any] = {
            "mockup_uuid": mockup_uuid,
            "smart_objects": smart_objects,
        }
        if export_options is not None:
            body["export_options"] = export_options
        if export_label is not None:
            body["export_label"] = export_label
        if is_async:
            body["is_async"] = True

        resp = self._transport.request(
            "POST",
            "/api/v1/renders",
            json=body,
            timeout=self._transport._render_timeout,
        )
        data = resp.json()["data"]
        if is_async or resp.status_code == 202:
            return JobAccepted.model_validate(data)
        return Render.model_validate(data)

    def create_video(
        self,
        *,
        mockup_uuid: str,
        smart_objects: list[dict[str, Any]],
        duration_seconds: int,
        audio: bool = False,
        advanced_model: Optional[str] = None,
        export_options: Optional[dict[str, Any]] = None,
        export_label: Optional[str] = None,
    ) -> JobAccepted:
        """Create an AI video render (always async, returns HTTP 202).

        The first video render on a free plan is granted once for the lifetime
        of the account. Credit cost is computed from the chosen model, the
        ``duration_seconds`` and whether ``audio`` is enabled.

        Args:
            mockup_uuid: UUID of the mockup to animate.
            smart_objects: Smart object configurations (same shape as
                :meth:`create`).
            duration_seconds: Clip length. Must be one of the chosen model's
                allowed durations, otherwise the API returns ``422``.
            audio: Whether to generate audio (default off).
            advanced_model: Optional model override; otherwise auto-selected
                by your plan tier.
            export_options: Optional export settings.
            export_label: Optional label for the export filename.

        Returns:
            :class:`JobAccepted` with ``render_uuid`` and ``status_url``. Poll
            with :meth:`SudoMock.jobs.get` / :meth:`SudoMock.jobs.wait`.

        Raises:
            InsufficientCreditsError: If credits are exhausted / free video
                already used.
            ValidationError: If ``duration_seconds`` is not allowed for the model.
        """
        video: dict[str, Any] = {
            "duration_seconds": duration_seconds,
            "audio": audio,
        }
        if advanced_model is not None:
            video["advanced_model"] = advanced_model

        body: dict[str, Any] = {
            "mockup_uuid": mockup_uuid,
            "smart_objects": smart_objects,
            "video": video,
        }
        if export_options is not None:
            body["export_options"] = export_options
        if export_label is not None:
            body["export_label"] = export_label

        resp = self._transport.request(
            "POST",
            "/api/v1/renders/video",
            json=body,
            timeout=self._transport._render_timeout,
        )
        data = resp.json()["data"]
        return JobAccepted.model_validate(data)


class _JobsResource:
    """Async job polling (for ``is_async`` renders, uploads, and video)."""

    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def get(self, render_uuid: str) -> Job:
        """Fetch the current status of an async job.

        Args:
            render_uuid: The ``render_uuid`` returned by an async submission.

        Returns:
            :class:`Job` with ``state`` (``queued`` / ``running`` /
            ``succeeded`` / ``failed``) and, once terminal, ``result_url``.

        Raises:
            NotFoundError: If the job does not exist or is not owned by you.
        """
        resp = self._transport.request("GET", f"/api/v1/jobs/{render_uuid}")
        data = resp.json()["data"]
        return Job.model_validate(data)

    def wait(
        self,
        render_uuid: str,
        *,
        poll_interval: float = 2.0,
        timeout: float = 300.0,
    ) -> Job:
        """Poll :meth:`get` until the job reaches a terminal state.

        Args:
            render_uuid: The ``render_uuid`` returned by an async submission.
            poll_interval: Seconds to wait between polls (default 2.0).
            timeout: Maximum total seconds to wait before raising (default 300).

        Returns:
            The terminal :class:`Job` (``succeeded`` or ``failed``). Inspect
            :attr:`Job.failed` / :attr:`Job.error` to handle failures.

        Raises:
            TimeoutError: If the job does not finish within ``timeout``.
            NotFoundError: If the job does not exist or is not owned by you.
        """
        deadline = time.monotonic() + timeout
        while True:
            job = self.get(render_uuid)
            if job.is_terminal:
                return job
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Job {render_uuid} did not finish within {timeout}s "
                    f"(last state: {job.state!r})"
                )
            time.sleep(poll_interval)


class _PsdResource:
    """PSD upload operations."""

    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def upload(
        self,
        *,
        url: str,
        name: Optional[str] = None,
        is_async: bool = False,
    ) -> Union[Mockup, JobAccepted]:
        """Upload a PSD by URL and parse it into a mockup template.

        PSD uploads are **free** (zero credits).

        Args:
            url: Public URL of the ``.psd`` file to ingest.
            name: Optional name for the resulting mockup.
            is_async: If ``True``, submit to the async queue and return a
                :class:`JobAccepted` (HTTP 202) immediately; poll with
                :meth:`SudoMock.jobs.get`. Defaults to ``False`` (blocking).

        Returns:
            :class:`Mockup` (synchronous) or :class:`JobAccepted` (async).

        Raises:
            ValidationError: If the URL is missing or not a valid PSD.
        """
        body: dict[str, Any] = {"url": url}
        if name is not None:
            body["name"] = name
        if is_async:
            body["is_async"] = True

        resp = self._transport.request(
            "POST",
            "/api/v1/psd/upload",
            json=body,
            timeout=self._transport._render_timeout,
        )
        data = resp.json()["data"]
        if is_async or resp.status_code == 202:
            return JobAccepted.model_validate(data)
        return Mockup.model_validate(data)


class _WebhookEndpointsResource:
    """Manage outbound webhook endpoints (HMAC-signed deliveries).

    Authenticated with your ``x-api-key`` (the API exposes an api-key
    alternative to the dashboard's bearer auth so SDK/MCP clients can manage
    webhooks). Use :func:`sudomock.verify_webhook_signature` to validate
    inbound deliveries.
    """

    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def list(self) -> WebhookEndpointList:
        """List your registered webhook endpoints."""
        resp = self._transport.request("GET", "/api/v1/webhook-endpoints")
        data = resp.json()["data"]
        return WebhookEndpointList.model_validate(data)

    def create(
        self,
        *,
        url: str,
        events: _StrList,
        enabled: bool = True,
    ) -> WebhookEndpoint:
        """Register a new webhook endpoint.

        Args:
            url: HTTPS URL that will receive POSTed events.
            events: Event types to subscribe to (e.g. ``["render.succeeded"]``).
            enabled: Whether the endpoint is active (default ``True``).

        Returns:
            The created :class:`WebhookEndpoint` (includes the signing
            ``secret`` on creation).
        """
        body: dict[str, Any] = {"url": url, "events": events, "enabled": enabled}
        resp = self._transport.request("POST", "/api/v1/webhook-endpoints", json=body)
        data = resp.json()["data"]
        return WebhookEndpoint.model_validate(data)

    def get(self, uuid: str) -> WebhookEndpoint:
        """Get a single webhook endpoint by UUID."""
        resp = self._transport.request("GET", f"/api/v1/webhook-endpoints/{uuid}")
        data = resp.json()["data"]
        return WebhookEndpoint.model_validate(data)

    def update(
        self,
        uuid: str,
        *,
        url: Optional[str] = None,
        events: Optional[_StrList] = None,
        enabled: Optional[bool] = None,
    ) -> WebhookEndpoint:
        """Update a webhook endpoint's URL, events, or enabled state."""
        body: dict[str, Any] = {}
        if url is not None:
            body["url"] = url
        if events is not None:
            body["events"] = events
        if enabled is not None:
            body["enabled"] = enabled
        resp = self._transport.request(
            "PATCH", f"/api/v1/webhook-endpoints/{uuid}", json=body
        )
        data = resp.json()["data"]
        return WebhookEndpoint.model_validate(data)

    def delete(self, uuid: str) -> None:
        """Delete a webhook endpoint."""
        self._transport.request("DELETE", f"/api/v1/webhook-endpoints/{uuid}")

    def rotate_secret(self, uuid: str) -> WebhookSecret:
        """Rotate the signing secret for an endpoint.

        Returns:
            :class:`WebhookSecret` with the new ``secret``.
        """
        resp = self._transport.request(
            "POST", f"/api/v1/webhook-endpoints/{uuid}/rotate-secret"
        )
        data = resp.json()["data"]
        return WebhookSecret.model_validate(data)

    def test(self, uuid: str) -> None:
        """Send a synthetic test delivery to an endpoint."""
        self._transport.request("POST", f"/api/v1/webhook-endpoints/{uuid}/test")

    def deliveries(self, uuid: str) -> WebhookDeliveryList:
        """List recent delivery attempts for an endpoint."""
        resp = self._transport.request(
            "GET", f"/api/v1/webhook-endpoints/{uuid}/deliveries"
        )
        data = resp.json()["data"]
        return WebhookDeliveryList.model_validate(data)

    def replay_delivery(self, uuid: str, delivery_id: str) -> None:
        """Re-attempt a previously failed delivery.

        Args:
            uuid: The webhook endpoint UUID.
            delivery_id: The delivery to replay.
        """
        self._transport.request(
            "POST",
            f"/api/v1/webhook-endpoints/{uuid}/deliveries/{delivery_id}/replay",
        )


class _AIResource:
    """SudoAI operations (AI-powered mockup rendering)."""

    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def render(
        self,
        *,
        source_url: str,
        artwork_url: Optional[str] = None,
        product_type: Optional[str] = None,
        segment_index: Optional[int] = None,
        print_area_x: Optional[int] = None,
        print_area_y: Optional[int] = None,
        color: Optional[str] = None,
        adjustments: Optional[dict[str, Any]] = None,
        placement: Optional[dict[str, Any]] = None,
        export_options: Optional[dict[str, Any]] = None,
    ) -> AIRender:
        """Create an AI-powered render without a PSD template.

        Args:
            source_url: URL of the source product photo.
            artwork_url: URL of the artwork/design to apply.
            product_type: Hint for surface detection (e.g. ``"t-shirt"``).
            segment_index: Pre-selected segment index (0-based).
            print_area_x: X coordinate for manual print area selection.
            print_area_y: Y coordinate for manual print area selection.
            color: Hex color overlay (e.g. ``"#FF0000"``).
            adjustments: Artwork adjustment settings.
            placement: Placement configuration (position, coverage, fit, etc.).
            export_options: Export settings (format, size, quality).

        Returns:
            :class:`AIRender` with ``print_files`` and a convenience ``.url`` property.
        """
        body: dict[str, Any] = {"source_url": source_url}
        if artwork_url is not None:
            body["artwork_url"] = artwork_url
        if product_type is not None:
            body["product_type"] = product_type
        if segment_index is not None:
            body["segment_index"] = segment_index
        if print_area_x is not None:
            body["print_area_x"] = print_area_x
        if print_area_y is not None:
            body["print_area_y"] = print_area_y
        if color is not None:
            body["color"] = color
        if adjustments is not None:
            body["adjustments"] = adjustments
        if placement is not None:
            body["placement"] = placement
        if export_options is not None:
            body["export_options"] = export_options

        resp = self._transport.request(
            "POST",
            "/api/v1/sudoai/render",
            json=body,
            timeout=self._transport._render_timeout,
        )
        data = resp.json()["data"]
        return AIRender.model_validate(data)


class _AccountResource:
    """Account information operations."""

    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def get(self) -> AccountInfo:
        """Get current account information.

        Returns:
            :class:`AccountInfo` with ``account``, ``subscription``,
            ``usage``, and ``api_key`` details.
        """
        resp = self._transport.request("GET", "/api/v1/me")
        data = resp.json()["data"]
        return AccountInfo.model_validate(data)


class SudoMock:
    """Synchronous client for the SudoMock API.

    Args:
        api_key: Your SudoMock API key (``sm_...``). Falls back to the
            ``SUDOMOCK_API_KEY`` environment variable.
        base_url: API base URL (default: ``https://api.sudomock.com``).
        timeout: Default request timeout in seconds (default: 30).
        render_timeout: Timeout for render requests in seconds (default: 120).
        max_retries: Maximum retry attempts for transient errors (default: 3).

    Usage::

        client = SudoMock(api_key="sm_xxx")
        mockups = client.mockups.list()
        client.close()

        # Or as a context manager:
        with SudoMock(api_key="sm_xxx") as client:
            mockups = client.mockups.list()
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        render_timeout: float = DEFAULT_RENDER_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        resolved_key = api_key or os.environ.get("SUDOMOCK_API_KEY")
        if not resolved_key:
            raise SudoMockError(
                "API key is required. Pass api_key= or set the "
                "SUDOMOCK_API_KEY environment variable."
            )

        self._api_key = resolved_key
        self._base_url = base_url
        self._timeout = timeout
        self._render_timeout = render_timeout
        self._max_retries = max_retries

        self._transport = SyncTransport(
            api_key=resolved_key,
            base_url=base_url,
            timeout=timeout,
            render_timeout=render_timeout,
            max_retries=max_retries,
        )

        # Resource namespaces
        self.mockups = _MockupsResource(self._transport)
        self.renders = _RendersResource(self._transport)
        self.jobs = _JobsResource(self._transport)
        self.psd = _PsdResource(self._transport)
        self.ai = _AIResource(self._transport)
        self.account = _AccountResource(self._transport)
        self.webhook_endpoints = _WebhookEndpointsResource(self._transport)

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._transport.close()

    def __enter__(self) -> SudoMock:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"SudoMock(base_url={self._base_url!r})"
