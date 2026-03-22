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
from typing import Any

from ._http import (
    DEFAULT_BASE_URL,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RENDER_TIMEOUT,
    DEFAULT_TIMEOUT,
    SyncTransport,
)
from .exceptions import SudoMockError
from .models import AccountInfo, AIRender, Mockup, MockupList, Render


class _MockupsResource:
    """Mockup template operations (list, get, delete)."""

    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def list(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
        search: str | None = None,
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
        export_options: dict[str, Any] | None = None,
        export_label: str | None = None,
    ) -> Render:
        """Create a new render from a mockup template.

        Args:
            mockup_uuid: UUID of the mockup to render.
            smart_objects: List of smart object configurations, each containing
                ``uuid`` and ``asset`` (with ``url``, optional ``fit``, ``rotate``,
                ``position``, ``size``).
            export_options: Optional export settings (``image_format``, ``image_size``,
                ``quality``).
            export_label: Optional label for the export filename.

        Returns:
            :class:`Render` with ``print_files`` and a convenience ``.url`` property.

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

        resp = self._transport.request(
            "POST",
            "/api/v1/renders",
            json=body,
            timeout=self._transport._render_timeout,
        )
        data = resp.json()["data"]
        return Render.model_validate(data)


class _AIResource:
    """SudoAI operations (AI-powered mockup rendering)."""

    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def render(
        self,
        *,
        source_url: str,
        artwork_url: str | None = None,
        product_type: str | None = None,
        segment_index: int | None = None,
        print_area_x: int | None = None,
        print_area_y: int | None = None,
        color: str | None = None,
        adjustments: dict[str, Any] | None = None,
        placement: dict[str, Any] | None = None,
        export_options: dict[str, Any] | None = None,
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
        api_key: str | None = None,
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
        self.ai = _AIResource(self._transport)
        self.account = _AccountResource(self._transport)

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._transport.close()

    def __enter__(self) -> SudoMock:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"SudoMock(base_url={self._base_url!r})"
