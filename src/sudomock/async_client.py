"""Asynchronous SudoMock API client.

.. note::

    This client is ``asyncio`` I/O (``async``/``await`` *transport*) -- it is
    **not** the same thing as the server-side async render *queue*. Either
    client (sync :class:`~sudomock.SudoMock` or async :class:`AsyncSudoMock`)
    can submit a server-async job via ``renders.create(..., is_async=True)``
    and poll it with ``jobs.get`` / ``jobs.wait``. ``is_async`` controls
    server queueing; ``AsyncSudoMock`` controls how *your* process does HTTP.

Usage::

    from sudomock import AsyncSudoMock

    async with AsyncSudoMock(api_key="sm_xxx") as client:
        mockups = await client.mockups.list(limit=20)
        render = await client.renders.create(
            mockup_uuid="...",
            smart_objects=[{"uuid": "...", "asset": {"url": "https://..."}}],
        )
        print(render.url)

        # Server-async job, awaited with asyncio I/O:
        job_ack = await client.renders.create(
            mockup_uuid="...", smart_objects=[...], is_async=True,
        )
        job = await client.jobs.wait(job_ack.render_uuid)
        print(job.result_url)
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Optional, Union

from ._http import (
    DEFAULT_BASE_URL,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RENDER_TIMEOUT,
    DEFAULT_TIMEOUT,
    AsyncTransport,
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


class _AsyncMockupsResource:
    """Async mockup template operations."""

    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def list(
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
        resp = await self._transport.request(
            "GET",
            "/api/v1/mockups",
            params={"limit": limit, "offset": offset, "search": search},
        )
        data = resp.json()["data"]
        return MockupList.model_validate(data)

    async def get(self, uuid: str) -> Mockup:
        """Get a single mockup by UUID.

        Args:
            uuid: Mockup identifier.

        Returns:
            :class:`Mockup` with full details including smart objects.

        Raises:
            NotFoundError: If the mockup does not exist.
        """
        resp = await self._transport.request("GET", f"/api/v1/mockups/{uuid}")
        data = resp.json()["data"]
        return Mockup.model_validate(data)

    async def delete(self, uuid: str) -> None:
        """Delete a mockup by UUID.

        Args:
            uuid: Mockup identifier.

        Raises:
            NotFoundError: If the mockup does not exist.
        """
        await self._transport.request("DELETE", f"/api/v1/mockups/{uuid}")


class _AsyncRendersResource:
    """Async render operations."""

    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def create(
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
            smart_objects: List of smart object configurations.
            export_options: Optional export settings.
            export_label: Optional label for the export filename.
            is_async: If ``True``, submit to the server-side async queue and
                return a :class:`JobAccepted` (HTTP 202); poll with
                :meth:`jobs.get` / :meth:`jobs.wait`. Defaults to ``False``.

        Returns:
            :class:`Render` (synchronous) or :class:`JobAccepted` (async).

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

        resp = await self._transport.request(
            "POST",
            "/api/v1/renders",
            json=body,
            timeout=self._transport._render_timeout,
        )
        data = resp.json()["data"]
        if is_async or resp.status_code == 202:
            return JobAccepted.model_validate(data)
        return Render.model_validate(data)

    async def create_video(
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
        of the account. See :meth:`sudomock.client.SudoMock.renders.create_video`
        for full parameter docs.

        Returns:
            :class:`JobAccepted` with ``render_uuid``; poll with
            :meth:`jobs.get` / :meth:`jobs.wait`.

        Raises:
            InsufficientCreditsError: If credits are exhausted / free video used.
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

        resp = await self._transport.request(
            "POST",
            "/api/v1/renders/video",
            json=body,
            timeout=self._transport._render_timeout,
        )
        data = resp.json()["data"]
        return JobAccepted.model_validate(data)


class _AsyncJobsResource:
    """Async job polling (for ``is_async`` renders, uploads, and video)."""

    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def get(self, render_uuid: str) -> Job:
        """Fetch the current status of an async job.

        Raises:
            NotFoundError: If the job does not exist or is not owned by you.
        """
        resp = await self._transport.request("GET", f"/api/v1/jobs/{render_uuid}")
        data = resp.json()["data"]
        return Job.model_validate(data)

    async def wait(
        self,
        render_uuid: str,
        *,
        poll_interval: float = 2.0,
        timeout: float = 300.0,
    ) -> Job:
        """Poll :meth:`get` until the job reaches a terminal state.

        Args:
            render_uuid: The ``render_uuid`` returned by an async submission.
            poll_interval: Seconds between polls (default 2.0).
            timeout: Maximum total seconds to wait (default 300).

        Returns:
            The terminal :class:`Job` (``succeeded`` or ``failed``).

        Raises:
            TimeoutError: If the job does not finish within ``timeout``.
            NotFoundError: If the job does not exist or is not owned by you.
        """
        deadline = time.monotonic() + timeout
        while True:
            job = await self.get(render_uuid)
            if job.is_terminal:
                return job
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Job {render_uuid} did not finish within {timeout}s "
                    f"(last state: {job.state!r})"
                )
            await asyncio.sleep(poll_interval)


class _AsyncPsdResource:
    """Async PSD upload operations."""

    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def upload(
        self,
        *,
        url: str,
        name: Optional[str] = None,
        is_async: bool = False,
    ) -> Union[Mockup, JobAccepted]:
        """Upload a PSD by URL and parse it into a mockup template (free).

        Args:
            url: Public URL of the ``.psd`` file.
            name: Optional name for the resulting mockup.
            is_async: If ``True``, return a :class:`JobAccepted` (202) and poll
                with :meth:`jobs.get`. Defaults to ``False`` (blocking).

        Returns:
            :class:`Mockup` (synchronous) or :class:`JobAccepted` (async).
        """
        body: dict[str, Any] = {"url": url}
        if name is not None:
            body["name"] = name
        if is_async:
            body["is_async"] = True

        resp = await self._transport.request(
            "POST",
            "/api/v1/psd/upload",
            json=body,
            timeout=self._transport._render_timeout,
        )
        data = resp.json()["data"]
        if is_async or resp.status_code == 202:
            return JobAccepted.model_validate(data)
        return Mockup.model_validate(data)


class _AsyncWebhookEndpointsResource:
    """Manage outbound webhook endpoints (HMAC-signed deliveries).

    Authenticated with your ``x-api-key``. Use
    :func:`sudomock.verify_webhook_signature` to validate inbound deliveries.
    """

    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def list(self) -> WebhookEndpointList:
        """List your registered webhook endpoints."""
        resp = await self._transport.request("GET", "/api/v1/webhook-endpoints")
        data = resp.json()["data"]
        return WebhookEndpointList.model_validate(data)

    async def create(
        self,
        *,
        url: str,
        events: _StrList,
        enabled: bool = True,
    ) -> WebhookEndpoint:
        """Register a new webhook endpoint."""
        body: dict[str, Any] = {"url": url, "events": events, "enabled": enabled}
        resp = await self._transport.request(
            "POST", "/api/v1/webhook-endpoints", json=body
        )
        data = resp.json()["data"]
        return WebhookEndpoint.model_validate(data)

    async def get(self, uuid: str) -> WebhookEndpoint:
        """Get a single webhook endpoint by UUID."""
        resp = await self._transport.request(
            "GET", f"/api/v1/webhook-endpoints/{uuid}"
        )
        data = resp.json()["data"]
        return WebhookEndpoint.model_validate(data)

    async def update(
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
        resp = await self._transport.request(
            "PATCH", f"/api/v1/webhook-endpoints/{uuid}", json=body
        )
        data = resp.json()["data"]
        return WebhookEndpoint.model_validate(data)

    async def delete(self, uuid: str) -> None:
        """Delete a webhook endpoint."""
        await self._transport.request("DELETE", f"/api/v1/webhook-endpoints/{uuid}")

    async def rotate_secret(self, uuid: str) -> WebhookSecret:
        """Rotate the signing secret for an endpoint."""
        resp = await self._transport.request(
            "POST", f"/api/v1/webhook-endpoints/{uuid}/rotate-secret"
        )
        data = resp.json()["data"]
        return WebhookSecret.model_validate(data)

    async def test(self, uuid: str) -> None:
        """Send a synthetic test delivery to an endpoint."""
        await self._transport.request(
            "POST", f"/api/v1/webhook-endpoints/{uuid}/test"
        )

    async def deliveries(self, uuid: str) -> WebhookDeliveryList:
        """List recent delivery attempts for an endpoint."""
        resp = await self._transport.request(
            "GET", f"/api/v1/webhook-endpoints/{uuid}/deliveries"
        )
        data = resp.json()["data"]
        return WebhookDeliveryList.model_validate(data)

    async def replay_delivery(self, uuid: str, delivery_id: str) -> None:
        """Re-attempt a previously failed delivery."""
        await self._transport.request(
            "POST",
            f"/api/v1/webhook-endpoints/{uuid}/deliveries/{delivery_id}/replay",
        )


class _AsyncAIResource:
    """Async SudoAI operations."""

    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def render(
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
            product_type: Hint for surface detection.
            segment_index: Pre-selected segment index (0-based).
            print_area_x: X coordinate for manual print area selection.
            print_area_y: Y coordinate for manual print area selection.
            color: Hex color overlay.
            adjustments: Artwork adjustment settings.
            placement: Placement configuration.
            export_options: Export settings.

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

        resp = await self._transport.request(
            "POST",
            "/api/v1/sudoai/render",
            json=body,
            timeout=self._transport._render_timeout,
        )
        data = resp.json()["data"]
        return AIRender.model_validate(data)


class _AsyncAccountResource:
    """Async account information operations."""

    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def get(self) -> AccountInfo:
        """Get current account information.

        Returns:
            :class:`AccountInfo` with ``account``, ``subscription``,
            ``usage``, and ``api_key`` details.
        """
        resp = await self._transport.request("GET", "/api/v1/me")
        data = resp.json()["data"]
        return AccountInfo.model_validate(data)


class AsyncSudoMock:
    """Asynchronous client for the SudoMock API.

    Args:
        api_key: Your SudoMock API key (``sm_...``). Falls back to the
            ``SUDOMOCK_API_KEY`` environment variable.
        base_url: API base URL (default: ``https://api.sudomock.com``).
        timeout: Default request timeout in seconds (default: 30).
        render_timeout: Timeout for render requests in seconds (default: 120).
        max_retries: Maximum retry attempts for transient errors (default: 3).

    Usage::

        async with AsyncSudoMock(api_key="sm_xxx") as client:
            mockups = await client.mockups.list()
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

        self._transport = AsyncTransport(
            api_key=resolved_key,
            base_url=base_url,
            timeout=timeout,
            render_timeout=render_timeout,
            max_retries=max_retries,
        )

        # Resource namespaces
        self.mockups = _AsyncMockupsResource(self._transport)
        self.renders = _AsyncRendersResource(self._transport)
        self.jobs = _AsyncJobsResource(self._transport)
        self.psd = _AsyncPsdResource(self._transport)
        self.ai = _AsyncAIResource(self._transport)
        self.account = _AsyncAccountResource(self._transport)
        self.webhook_endpoints = _AsyncWebhookEndpointsResource(self._transport)

    async def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        await self._transport.close()

    async def __aenter__(self) -> AsyncSudoMock:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    def __repr__(self) -> str:
        return f"AsyncSudoMock(base_url={self._base_url!r})"
