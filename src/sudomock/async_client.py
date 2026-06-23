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
        job = await client.jobs.wait(job_ack.job_id)
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
    JobList,
    Mockup,
    MockupList,
    PlanList,
    Render,
    TwoDMockup,
    TwoDMockupList,
    VideoOptions,
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
        name: Optional[str] = None,
        created_after: Optional[str] = None,
        created_before: Optional[str] = None,
        sort: Optional[str] = None,
        order: Optional[str] = None,
    ) -> MockupList:
        """List mockup templates with optional pagination and filters.

        Args:
            limit: Maximum number of results (default server-side: 20, max 100).
            offset: Pagination offset.
            name: Case-insensitive substring filter on the mockup name.
            created_after: ISO8601 lower bound on ``created_at``.
            created_before: ISO8601 upper bound on ``created_at``.
            sort: Sort field, one of ``name`` | ``created_at`` | ``updated_at``
                (default ``created_at``).
            order: Sort direction, ``asc`` | ``desc`` (default ``desc``).

        Returns:
            :class:`MockupList` with ``mockups``, ``total``, ``limit``, ``offset``.
        """
        resp = await self._transport.request(
            "GET",
            "/api/v1/mockups",
            params={
                "limit": limit,
                "offset": offset,
                "name": name,
                "created_after": created_after,
                "created_before": created_before,
                "sort": sort,
                "order": order,
            },
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

    async def update(self, uuid: str, *, name: str) -> Mockup:
        """Rename a mockup.

        Args:
            uuid: Mockup identifier.
            name: New mockup name (1..255 characters).

        Returns:
            The updated :class:`Mockup`.

        Raises:
            NotFoundError: If the mockup does not exist.
        """
        resp = await self._transport.request(
            "PATCH", f"/api/v1/mockups/{uuid}", json={"name": name}
        )
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
        if is_async or resp.status_code == 202:
            # Async submit (202) returns a BARE body {job_id, kind, status,
            # status_url} — no {success, data} envelope. The sync path still wraps.
            return JobAccepted.model_validate(resp.json())
        return Render.model_validate(resp.json()["data"])

    async def create_video(
        self,
        *,
        mockup_uuid: Optional[str] = None,
        smart_objects: Optional[list[dict[str, Any]]] = None,
        image_url: Optional[str] = None,
        duration_seconds: int,
        audio: bool = False,
        motion: Optional[str] = None,
        advanced_model: Optional[str] = None,
        export_options: Optional[dict[str, Any]] = None,
        webhook: Optional[dict[str, Any]] = None,
    ) -> JobAccepted:
        """Create an AI video render (always async, returns HTTP 202).

        Two **mutually exclusive** input modes: render mode (``mockup_uuid`` +
        ``smart_objects``) or raw-image mode (``image_url``). See
        :meth:`sudomock.client.SudoMock.renders.create_video` for full
        parameter docs.

        Returns:
            :class:`JobAccepted` with ``job_id``; poll with
            :meth:`jobs.get` / :meth:`jobs.wait`.

        Raises:
            ValueError: If neither ``image_url`` nor ``mockup_uuid`` is given.
            InsufficientCreditsError: If credits are exhausted / free video used.
            ValidationError: If ``duration_seconds`` is not allowed for the model.
        """
        if image_url is None and mockup_uuid is None:
            raise ValueError(
                "create_video requires either image_url (raw-image mode) or "
                "mockup_uuid (render mode)."
            )

        # Validate + serialize the animation options through the typed model so
        # the public VideoOptions surface is the single source of truth. Unset
        # optionals (motion / advanced_model) are dropped, matching the API's
        # "omit = use default" contract.
        video = VideoOptions(
            duration_seconds=duration_seconds,
            audio=audio,
            motion=motion,
            advanced_model=advanced_model,
        ).model_dump(exclude_none=True)

        body: dict[str, Any] = {"video": video}
        if mockup_uuid is not None:
            body["mockup_uuid"] = mockup_uuid
        if smart_objects is not None:
            body["smart_objects"] = smart_objects
        if image_url is not None:
            body["image_url"] = image_url
        if export_options is not None:
            body["export_options"] = export_options
        if webhook is not None:
            body["webhook"] = webhook

        resp = await self._transport.request(
            "POST",
            "/api/v1/renders/video",
            json=body,
            timeout=self._transport._render_timeout,
        )
        # Video submit returns a BARE 202 body {job_id, kind, status,
        # status_url, ...} — no {success, data} envelope.
        return JobAccepted.model_validate(resp.json())


class _AsyncJobsResource:
    """Async job polling (for ``is_async`` renders, uploads, and video)."""

    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def list(
        self,
        *,
        kind: Optional[str] = None,
        mockup_uuid: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> JobList:
        """List your async jobs, newest first (keyset-paginated).

        Args:
            kind: Filter by job kind, one of ``video`` | ``render`` | ``upload``.
            mockup_uuid: Filter by source mockup (raw-image videos excluded).
            limit: Page size, 1..50 (default server-side: 20).
            cursor: Opaque keyset cursor from a previous page's ``next_cursor``.

        Returns:
            :class:`JobList` with ``jobs`` and ``next_cursor`` (``None`` when
            the final page is reached).
        """
        resp = await self._transport.request(
            "GET",
            "/api/v1/jobs",
            params={
                "kind": kind,
                "mockup_uuid": mockup_uuid,
                "limit": limit,
                "cursor": cursor,
            },
        )
        # The list endpoint returns a BARE body {jobs: [...], next_cursor} —
        # no {success, data} envelope.
        return JobList.model_validate(resp.json())

    async def get(self, job_id: str) -> Job:
        """Fetch the current status of an async job.

        Raises:
            NotFoundError: If the job does not exist or is not owned by you.
        """
        resp = await self._transport.request("GET", f"/api/v1/jobs/{job_id}")
        # The job-poll endpoint returns a BARE body {job_id, status, ...} —
        # no {success, data} envelope.
        return Job.model_validate(resp.json())

    async def wait(
        self,
        job_id: str,
        *,
        poll_interval: float = 2.0,
        timeout: float = 300.0,
    ) -> Job:
        """Poll :meth:`get` until the job reaches a terminal state.

        Args:
            job_id: The ``job_id`` returned by an async submission.
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
            job = await self.get(job_id)
            if job.is_terminal:
                return job
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Job {job_id} did not finish within {timeout}s "
                    f"(last status: {job.status!r})"
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
        # BE field names are psd_file_url / psd_name (the SDK keeps the friendly
        # url= / name= kwargs and maps them here).
        body: dict[str, Any] = {"psd_file_url": url}
        if name is not None:
            body["psd_name"] = name
        if is_async:
            body["is_async"] = True

        resp = await self._transport.request(
            "POST",
            "/api/v1/psd/upload",
            json=body,
            timeout=self._transport._render_timeout,
        )
        if is_async or resp.status_code == 202:
            # Async submit (202) returns a BARE body {job_id, kind, status,
            # status_url} — no {success, data} envelope. The sync path still wraps.
            return JobAccepted.model_validate(resp.json())
        return Mockup.model_validate(resp.json()["data"])


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
        # The API returns a BARE JSON array of endpoints — no {success, data}
        # envelope. Wrap it into the convenience list model.
        return WebhookEndpointList(webhook_endpoints=resp.json())

    async def create(
        self,
        *,
        url: str,
        events: _StrList,
        description: Optional[str] = None,
    ) -> WebhookEndpoint:
        """Register a new webhook endpoint.

        Args:
            url: HTTPS URL that will receive POSTed events.
            events: Event types to subscribe to; an empty list subscribes to ALL.
            description: Optional human-readable label (≤255 chars).
        """
        # API field is `event_types` (empty list = subscribe to all events).
        # NOTE: the create endpoint has no `enabled` field (it is update-only).
        body: dict[str, Any] = {"url": url, "event_types": events}
        if description is not None:
            body["description"] = description
        resp = await self._transport.request(
            "POST", "/api/v1/webhook-endpoints", json=body
        )
        # BARE endpoint object (no {success, data} envelope).
        return WebhookEndpoint.model_validate(resp.json())

    async def events(
        self,
        *,
        status: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> WebhookDeliveryList:
        """List recent deliveries across ALL of your endpoints (Events feed).

        Args:
            status: Optional delivery-status filter.
            event_type: Optional event-type filter.
            limit: Page size, 1..200 (default server-side: 100).
        """
        resp = await self._transport.request(
            "GET",
            "/api/v1/webhook-endpoints/events",
            params={"status": status, "event_type": event_type, "limit": limit},
        )
        # BARE JSON array of delivery rows (no {success, data} envelope).
        return WebhookDeliveryList(deliveries=resp.json())

    async def get(self, uuid: str) -> WebhookEndpoint:
        """Get a single webhook endpoint by UUID."""
        resp = await self._transport.request(
            "GET", f"/api/v1/webhook-endpoints/{uuid}"
        )
        # BARE endpoint object (no {success, data} envelope).
        return WebhookEndpoint.model_validate(resp.json())

    async def update(
        self,
        uuid: str,
        *,
        url: Optional[str] = None,
        events: Optional[_StrList] = None,
        description: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> WebhookEndpoint:
        """Update a webhook endpoint's URL, events, description, or enabled state."""
        body: dict[str, Any] = {}
        if url is not None:
            body["url"] = url
        if events is not None:
            body["event_types"] = events  # API field name
        if description is not None:
            body["description"] = description
        if enabled is not None:
            body["enabled"] = enabled
        resp = await self._transport.request(
            "PATCH", f"/api/v1/webhook-endpoints/{uuid}", json=body
        )
        # BARE endpoint object (no {success, data} envelope).
        return WebhookEndpoint.model_validate(resp.json())

    async def delete(self, uuid: str) -> None:
        """Delete a webhook endpoint."""
        await self._transport.request("DELETE", f"/api/v1/webhook-endpoints/{uuid}")

    async def rotate_secret(self, uuid: str) -> WebhookSecret:
        """Rotate the signing secret for an endpoint."""
        resp = await self._transport.request(
            "POST", f"/api/v1/webhook-endpoints/{uuid}/rotate-secret"
        )
        # BARE endpoint object carrying the unmasked `secret` (no {success, data}
        # envelope); WebhookSecret picks the secret, extra fields are accepted.
        return WebhookSecret.model_validate(resp.json())

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
        # The API returns a BARE JSON array of delivery rows — no {success, data}
        # envelope. Wrap it into the convenience list model.
        return WebhookDeliveryList(deliveries=resp.json())

    async def replay_delivery(self, uuid: str, delivery_id: str) -> None:
        """Re-attempt a previously failed delivery."""
        await self._transport.request(
            "POST",
            f"/api/v1/webhook-endpoints/{uuid}/deliveries/{delivery_id}/replay",
        )

    async def replay_failed(self, uuid: str) -> None:
        """Re-attempt ALL failed/dead deliveries for an endpoint."""
        await self._transport.request(
            "POST",
            f"/api/v1/webhook-endpoints/{uuid}/deliveries/replay-failed",
        )


class _AsyncAIResource:
    """Async SudoAI 2D-mockup operations (render, list, get, delete)."""

    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def render(
        self,
        *,
        mockup_uuid: str,
        print_areas: list[dict[str, Any]],
        export_options: Optional[dict[str, Any]] = None,
    ) -> AIRender:
        """Render artwork onto an existing 2D mockup (costs 5 credits).

        Args:
            mockup_uuid: UUID of a previously-created 2D mockup (see
                :meth:`list` / :meth:`get`).
            print_areas: One or more print-area configs. Each is a dict with a
                required ``uuid`` plus ``artwork_url`` and/or ``color`` (hex),
                and optional ``adjustments`` / ``placement``.
            export_options: Export settings (``image_format``, ``image_size``,
                ``quality``, ``dpi``).

        Returns:
            :class:`AIRender` with ``print_files`` and a convenience ``.url``
            property.

        Raises:
            InsufficientCreditsError: If fewer than 5 credits remain.
            NotFoundError: If ``mockup_uuid`` does not exist.
            ValidationError: If ``print_areas`` is empty or malformed.
        """
        body: dict[str, Any] = {
            "mockup_uuid": mockup_uuid,
            "print_areas": print_areas,
        }
        if export_options is not None:
            body["export_options"] = export_options

        resp = await self._transport.request(
            "POST",
            "/api/v1/sudoai/2d-mockup/render",
            json=body,
            timeout=self._transport._render_timeout,
        )
        data = resp.json()["data"]
        return AIRender.model_validate(data)

    async def list(
        self,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> TwoDMockupList:
        """List your SudoAI 2D mockups (free; zero credits)."""
        resp = await self._transport.request(
            "GET",
            "/api/v1/sudoai/2d-mockups",
            params={"limit": limit, "offset": offset},
        )
        payload = resp.json()
        return TwoDMockupList(
            mockups=payload["data"],
            total=payload["total"],
            limit=payload["limit"],
            offset=payload["offset"],
        )

    async def get(self, mockup_id: str) -> TwoDMockup:
        """Get a single 2D mockup by id (free; zero credits).

        Raises:
            NotFoundError: If the 2D mockup does not exist.
        """
        resp = await self._transport.request(
            "GET", f"/api/v1/sudoai/2d-mockup/{mockup_id}"
        )
        return TwoDMockup.model_validate(resp.json()["data"])

    async def delete(self, mockup_id: str) -> None:
        """Delete a 2D mockup (and its masks/quads/storage; free).

        Raises:
            NotFoundError: If the 2D mockup does not exist.
        """
        await self._transport.request(
            "DELETE", f"/api/v1/sudoai/2d-mockup/{mockup_id}"
        )


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


class _AsyncPackagesResource:
    """Async public plan / pricing lookup (no authentication required)."""

    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def plans(self) -> PlanList:
        """List all active subscription plans."""
        resp = await self._transport.request("GET", "/api/v1/packages/plans")
        return PlanList.model_validate(resp.json())

    async def pricing(self) -> PlanList:
        """List public pricing (same shape as :meth:`plans`)."""
        resp = await self._transport.request("GET", "/api/v1/packages/pricing")
        return PlanList.model_validate(resp.json())


class AsyncSudoMock:
    """Asynchronous client for the SudoMock API.

    Args:
        api_key: Your SudoMock API key (``sm_...``). Falls back to the
            ``SUDOMOCK_API_KEY`` environment variable.
        base_url: API base URL (default: ``https://api.sudomock.com``).
        timeout: Default request timeout in seconds (default: 30).
        render_timeout: Timeout for render requests in seconds (default: 120).
        max_retries: Maximum *total* request attempts for transient errors
            (429 / 5xx / network), not the number of extra retries. The default
            of 3 means the initial request plus up to 2 retries.

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
        self.packages = _AsyncPackagesResource(self._transport)
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
