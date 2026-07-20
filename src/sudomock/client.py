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
from uuid import uuid4

from ._http import (
    DEFAULT_BASE_URL,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RENDER_TIMEOUT,
    DEFAULT_TIMEOUT,
    SyncTransport,
)
from .exceptions import JobFailedError, JobTimeoutError, SudoMockError
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
    TwoDPrintAreasUpdate,
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


class _MockupsResource:
    """Mockup template operations (list, get, delete)."""

    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def list(
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
        resp = self._transport.request(
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

    def update(self, uuid: str, *, name: str) -> Mockup:
        """Rename a mockup.

        Args:
            uuid: Mockup identifier.
            name: New mockup name (1..255 characters).

        Returns:
            The updated :class:`Mockup`.

        Raises:
            NotFoundError: If the mockup does not exist.
        """
        resp = self._transport.request("PATCH", f"/api/v1/mockups/{uuid}", json={"name": name})
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
            carrying ``job_id`` and ``status_url``.

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
        if is_async or resp.status_code == 202:
            # Async submit (202) returns a BARE body {job_id, kind, status,
            # status_url} — no {success, data} envelope. The sync path still wraps.
            return JobAccepted.model_validate(resp.json())
        return Render.model_validate(resp.json()["data"])

    def create_video(
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

        Two **mutually exclusive** input modes:

        * **Render mode** -- pass ``mockup_uuid`` + ``smart_objects``; the worker
          renders the input still, then animates it.
        * **Raw-image mode** -- pass ``image_url`` (public https); the URL is
          animated directly. ``mockup_uuid`` is then an optional association.

        The first video render on a free plan is granted once for the lifetime
        of the account. Credit cost is computed from the chosen model, the
        ``duration_seconds`` and whether ``audio`` is enabled.

        Args:
            mockup_uuid: UUID of the mockup to animate (render mode; optional
                association in raw-image mode).
            smart_objects: Smart object configurations (render mode; same shape
                as :meth:`create`).
            image_url: Public https image URL to animate directly (raw-image
                mode).
            duration_seconds: Clip length. Must be one of the chosen model's
                allowed durations, otherwise the API returns ``400``
                (``INVALID_VIDEO_DURATION``). The server defaults to ``5``
                seconds when the field is omitted.
            audio: Whether to generate audio (default off).
            motion: Animation style, ``ambient`` (default) or ``showcase``.
            advanced_model: Optional model override; otherwise auto-selected
                by your plan tier.
            export_options: Optional export settings (render-mode still config).
            webhook: Optional per-job webhook override, e.g.
                ``{"url": "https://your-app.com/hook"}``.

        Returns:
            :class:`JobAccepted` with ``job_id`` and ``status_url``. Poll
            with :meth:`SudoMock.jobs.get` / :meth:`SudoMock.jobs.wait`.

        Raises:
            ValueError: If neither ``image_url`` nor ``mockup_uuid`` is given.
            InsufficientCreditsError: If credits are exhausted / free video
                already used.
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

        resp = self._transport.request(
            "POST",
            "/api/v1/renders/video",
            json=body,
            timeout=self._transport._render_timeout,
        )
        # Video submit returns a BARE 202 body {job_id, kind, status,
        # status_url, ...} — no {success, data} envelope.
        return JobAccepted.model_validate(resp.json())


class _JobsResource:
    """Async job polling."""

    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def list(
        self,
        *,
        kind: Optional[str] = None,
        mockup_uuid: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> JobList:
        """List your async jobs, newest first (keyset-paginated).

        Args:
            kind: Filter by job kind: ``video``, ``render``, ``upload``, or
                ``2d_create``.
            mockup_uuid: Filter by source mockup (raw-image videos excluded).
            limit: Page size, 1..50 (default server-side: 20).
            cursor: Opaque keyset cursor from a previous page's ``next_cursor``.

        Returns:
            :class:`JobList` with ``jobs`` and ``next_cursor`` (``None`` when
            the final page is reached).
        """
        resp = self._transport.request(
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

    def get(self, job_id: str) -> Job:
        """Fetch the current status of an async job.

        Args:
            job_id: The ``job_id`` returned by an async submission.

        Returns:
            :class:`Job` with ``status`` (``queued`` / ``running`` /
            ``succeeded`` / ``failed``) and, once terminal, ``result_url``.

        Raises:
            NotFoundError: If the job does not exist or is not owned by you.
        """
        resp = self._transport.request("GET", f"/api/v1/jobs/{job_id}")
        # The job-poll endpoint returns a BARE body {job_id, status, ...} —
        # no {success, data} envelope.
        return Job.model_validate(resp.json())

    def wait(
        self,
        job_id: str,
        *,
        poll_interval: float = 2.0,
        timeout: float = 300.0,
    ) -> Job:
        """Poll :meth:`get` until the job reaches a terminal state.

        Args:
            job_id: The ``job_id`` returned by an async submission.
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
            job = self.get(job_id)
            if job.is_terminal:
                return job
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Job {job_id} did not finish within {timeout}s (last status: {job.status!r})"
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
        # BE field names are psd_file_url / psd_name (the SDK keeps the friendly
        # url= / name= kwargs and maps them here).
        body: dict[str, Any] = {"psd_file_url": url}
        if name is not None:
            body["psd_name"] = name
        if is_async:
            body["is_async"] = True

        resp = self._transport.request(
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
        # The API returns a BARE JSON array of endpoints — no {success, data}
        # envelope. Wrap it into the convenience list model.
        return WebhookEndpointList(webhook_endpoints=resp.json())

    def create(
        self,
        *,
        url: str,
        events: _StrList,
        description: Optional[str] = None,
    ) -> WebhookEndpoint:
        """Register a new webhook endpoint.

        Args:
            url: HTTPS URL that will receive POSTed events.
            events: Event types to subscribe to (e.g. ``["render.succeeded"]``);
                an empty list subscribes to ALL events.
            description: Optional human-readable label (≤255 chars).

        Returns:
            The created :class:`WebhookEndpoint` (includes the signing
            ``secret`` on creation).
        """
        # API field is `event_types` (empty list = subscribe to all events).
        # NOTE: the create endpoint has no `enabled` field (it is update-only).
        body: dict[str, Any] = {"url": url, "event_types": events}
        if description is not None:
            body["description"] = description
        resp = self._transport.request("POST", "/api/v1/webhook-endpoints", json=body)
        # BARE endpoint object (no {success, data} envelope).
        return WebhookEndpoint.model_validate(resp.json())

    def events(
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
        resp = self._transport.request(
            "GET",
            "/api/v1/webhook-endpoints/events",
            params={"status": status, "event_type": event_type, "limit": limit},
        )
        # BARE JSON array of delivery rows (no {success, data} envelope).
        return WebhookDeliveryList(deliveries=resp.json())

    def get(self, uuid: str) -> WebhookEndpoint:
        """Get a single webhook endpoint by UUID."""
        resp = self._transport.request("GET", f"/api/v1/webhook-endpoints/{uuid}")
        # BARE endpoint object (no {success, data} envelope).
        return WebhookEndpoint.model_validate(resp.json())

    def update(
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
        resp = self._transport.request("PATCH", f"/api/v1/webhook-endpoints/{uuid}", json=body)
        # BARE endpoint object (no {success, data} envelope).
        return WebhookEndpoint.model_validate(resp.json())

    def delete(self, uuid: str) -> None:
        """Delete a webhook endpoint."""
        self._transport.request("DELETE", f"/api/v1/webhook-endpoints/{uuid}")

    def rotate_secret(self, uuid: str) -> WebhookSecret:
        """Rotate the signing secret for an endpoint.

        Returns:
            :class:`WebhookSecret` with the new ``secret``.
        """
        resp = self._transport.request("POST", f"/api/v1/webhook-endpoints/{uuid}/rotate-secret")
        # BARE endpoint object carrying the unmasked `secret` (no {success, data}
        # envelope); WebhookSecret picks the secret, extra fields are accepted.
        return WebhookSecret.model_validate(resp.json())

    def test(self, uuid: str) -> None:
        """Send a synthetic test delivery to an endpoint."""
        self._transport.request("POST", f"/api/v1/webhook-endpoints/{uuid}/test")

    def deliveries(self, uuid: str) -> WebhookDeliveryList:
        """List recent delivery attempts for an endpoint."""
        resp = self._transport.request("GET", f"/api/v1/webhook-endpoints/{uuid}/deliveries")
        # The API returns a BARE JSON array of delivery rows — no {success, data}
        # envelope. Wrap it into the convenience list model.
        return WebhookDeliveryList(deliveries=resp.json())

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

    def replay_failed(self, uuid: str) -> None:
        """Re-attempt ALL failed/dead deliveries for an endpoint.

        Args:
            uuid: The webhook endpoint UUID.
        """
        self._transport.request(
            "POST",
            f"/api/v1/webhook-endpoints/{uuid}/deliveries/replay-failed",
        )


class _AIResource:
    """SudoAI 2D-mockup operations."""

    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def create(
        self,
        *,
        source_url: Optional[str] = None,
        source_base64: Optional[str] = None,
        name: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> JobAccepted:
        """Create a 2D mockup from a source image (costs 25 credits).

        Exactly one source must be supplied. The request returns immediately;
        use :meth:`wait_for_2d_mockup` to wait for the finished mockup.

        Args:
            source_url: Public HTTPS URL of the source image.
            source_base64: Base64-encoded source image.
            name: Optional mockup name.
            idempotency_key: Optional key for safely retrying this submission. A
                UUID is generated when omitted.

        Returns:
            :class:`JobAccepted` with ``job_id`` and ``status_url``.

        Raises:
            ValueError: If both or neither source inputs are supplied.
            InsufficientCreditsError: If fewer than 25 credits remain.
        """
        if bool(source_url) == bool(source_base64):
            raise ValueError("create requires exactly one of source_url or source_base64")

        body: dict[str, Any] = {
            "source_url" if source_url else "source_base64": source_url or source_base64
        }
        if name is not None:
            body["name"] = name
        if idempotency_key is None:
            idempotency_key = str(uuid4())

        resp = self._transport.request(
            "POST",
            "/api/v1/sudoai/2d-mockups",
            json=body,
            headers={"Idempotency-Key": idempotency_key},
        )
        return JobAccepted.model_validate(resp.json())

    def wait_for_2d_mockup(
        self,
        job_id: str,
        *,
        poll_interval: float = 2.0,
        timeout: float = 180.0,
    ) -> TwoDMockup:
        """Wait for a 2D-mockup creation job and return its full details.

        Raises:
            JobFailedError: If creation fails. The exception exposes the
                ``error_code`` and the human-readable ``reason`` returned by the API.
            JobTimeoutError: If creation does not finish within ``timeout``.
        """
        try:
            job = _JobsResource(self._transport).wait(
                job_id,
                poll_interval=poll_interval,
                timeout=timeout,
            )
        except TimeoutError as exc:
            raise JobTimeoutError(job_id, timeout=timeout) from exc

        if job.kind not in (None, "2d_create"):
            raise SudoMockError(f"Job {job_id} has kind {job.kind!r}; expected '2d_create'")
        if job.failed:
            error_code, reason = job.failure_details()
            raise JobFailedError(
                job_id,
                error_code=error_code,
                reason=reason,
            )
        if not job.mockup_uuid:
            raise SudoMockError(f"Job {job_id} succeeded without a mockup UUID")
        return self.get(job.mockup_uuid)

    def update_2d_print_areas(
        self,
        mockup_id: str,
        print_areas: list[dict[str, Any]],
    ) -> TwoDPrintAreasUpdate:
        """Replace a 2D mockup's print areas (free; zero credits).

        Args:
            mockup_id: 2D mockup identifier.
            print_areas: One to eight print areas, each with four ``[x, y]`` points.

        Returns:
            The updated print-area geometry.
        """
        resp = self._transport.request(
            "PUT",
            f"/api/v1/sudoai/2d-mockup/{mockup_id}/print-areas",
            json={"print_areas": print_areas},
        )
        return TwoDPrintAreasUpdate.model_validate(resp.json()["data"])

    def render(
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
                and optional ``adjustments`` / ``placement``. At least one of
                ``artwork_url`` or ``color`` must be supplied per area.
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

        resp = self._transport.request(
            "POST",
            "/api/v1/sudoai/2d-mockup/render",
            json=body,
            timeout=self._transport._render_timeout,
        )
        data = resp.json()["data"]
        return AIRender.model_validate(data)

    def list(
        self,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> TwoDMockupList:
        """List your SudoAI 2D mockups (free; zero credits).

        Args:
            limit: Page size, 1..100 (default server-side: 20).
            offset: Pagination offset.

        Returns:
            :class:`TwoDMockupList` with ``mockups``, ``total``, ``limit``,
            ``offset``.
        """
        resp = self._transport.request(
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

    def get(self, mockup_id: str) -> TwoDMockup:
        """Get a single 2D mockup by id (free; zero credits).

        Raises:
            NotFoundError: If the 2D mockup does not exist.
        """
        resp = self._transport.request("GET", f"/api/v1/sudoai/2d-mockup/{mockup_id}")
        return TwoDMockup.model_validate(resp.json()["data"])

    def delete(self, mockup_id: str) -> None:
        """Delete a 2D mockup and all of its associated data (free; zero credits).

        Raises:
            NotFoundError: If the 2D mockup does not exist.
        """
        self._transport.request("DELETE", f"/api/v1/sudoai/2d-mockup/{mockup_id}")


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


class _PackagesResource:
    """Public plan / pricing lookup (no authentication required)."""

    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def plans(self) -> PlanList:
        """List all active subscription plans."""
        resp = self._transport.request("GET", "/api/v1/packages/plans")
        return PlanList.model_validate(resp.json())

    def pricing(self) -> PlanList:
        """List public pricing (same shape as :meth:`plans`)."""
        resp = self._transport.request("GET", "/api/v1/packages/pricing")
        return PlanList.model_validate(resp.json())


class SudoMock:
    """Synchronous client for the SudoMock API.

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
        self.packages = _PackagesResource(self._transport)
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
