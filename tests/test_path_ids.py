"""An id the caller supplies stays inside its own path segment.

An id often arrives from an application's own end user. Unencoded, a ``?`` in
it escapes its path segment and adds a query parameter the caller never asked
for, which on a destructive route is how a read turns into a delete.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import httpx
import pytest

from sudomock import AsyncSudoMock, SudoMock

from .conftest import TEST_API_KEY, TEST_BASE_URL

if TYPE_CHECKING:
    import respx

HOSTILE = "a1b2c3d4-0000-0000-0000-000000000000?recursive=true&foo=1"
ENCODED = "%3Frecursive%3Dtrue"


@pytest.fixture()
def client() -> SudoMock:
    return SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL, max_retries=1)


def _raw_path(request: httpx.Request) -> str:
    """The path as it goes on the wire; ``url.path`` decodes the escapes back."""
    return request.url.raw_path.decode()


def _assert_contained(request: httpx.Request) -> None:
    assert "recursive" not in request.url.params
    assert "foo" not in request.url.params
    assert ENCODED in _raw_path(request)


class TestIdsStayInThePath:
    def test_every_resource_that_puts_an_id_in_a_path(
        self, client: SudoMock, mock_api: respx.MockRouter
    ) -> None:
        empty = httpx.Response(200, json={"success": True, "data": {}})
        routes = [
            mock_api.get(path__startswith="/api/v1/psd-mockups/").mock(return_value=empty),
            mock_api.get(path__startswith="/api/v1/photo-mockups/").mock(return_value=empty),
            mock_api.get(path__startswith="/api/v1/jobs/").mock(return_value=empty),
            mock_api.get(path__startswith="/api/v1/webhook-endpoints/").mock(
                return_value=httpx.Response(200, json={"uuid": "e1", "url": "https://x.test"})
            ),
            mock_api.post(path__startswith="/api/v1/webhook-endpoints/").mock(
                return_value=httpx.Response(200, json={})
            ),
        ]

        for call in (
            lambda: client.psd_mockups.get(HOSTILE),
            lambda: client.photo_mockups.get(HOSTILE),
            lambda: client.jobs.get(HOSTILE),
            lambda: client.webhook_endpoints.get(HOSTILE),
            lambda: client.webhook_endpoints.replay_delivery(HOSTILE, HOSTILE),
        ):
            # The shape of the reply is not the point; the url is.
            with contextlib.suppress(Exception):
                call()

        seen = [c.request for route in routes for c in route.calls]
        assert len(seen) == 5
        for request in seen:
            _assert_contained(request)
        # Both ids on the two-id route are encoded, not just the first.
        replay = seen[-1]
        assert _raw_path(replay).count(ENCODED) == 2

    async def test_the_async_client_contains_an_id_too(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.get(path__startswith="/api/v1/psd-mockups/").mock(
            return_value=httpx.Response(200, json={"success": True, "data": {}})
        )

        async with AsyncSudoMock(
            api_key=TEST_API_KEY, base_url=TEST_BASE_URL, max_retries=1
        ) as client:
            with contextlib.suppress(Exception):
                await client.psd_mockups.get(HOSTILE)

        _assert_contained(route.calls.last.request)
