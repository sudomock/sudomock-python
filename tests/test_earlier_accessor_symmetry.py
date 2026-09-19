"""The earlier accessors read and write the same field, and can be deleted.

``client.ai`` and ``client.mockups`` are the accessors that predate the 0.11.0
naming pass; they stay pinned to the endpoints their callers have always used.
Reading one must return what was last written to it, and writing one must not
disturb ``photo_mockups`` / ``psd_mockups``. Otherwise the ordinary
save-and-restore pattern around a test double (``saved = client.ai`` ...
``client.ai = saved``, or ``mock.patch.object``) silently moves the current
accessor onto the earlier endpoint and leaves it there.

``mock.patch.object`` also deletes the attribute on exit, so the earlier names
need a deleter; deleting one restores the accessor the client was built with.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import httpx
import pytest

from sudomock import AsyncSudoMock, SudoMock

from .conftest import (
    MOCK_2D_MOCKUP_LIST_RESPONSE,
    MOCK_MOCKUP_LIST_RESPONSE,
    TEST_API_KEY,
    TEST_BASE_URL,
)

if TYPE_CHECKING:
    import respx

EARLIER_PHOTO_PATH = "/api/v1/sudoai/2d-mockups"
EARLIER_PSD_PATH = "/api/v1/mockups"
CURRENT_PHOTO_PATH = "/api/v1/photo-mockups"
CURRENT_PSD_PATH = "/api/v1/psd-mockups"


class _Stub:
    """Stands in for a resource; records nothing but says it was called."""

    def list(self) -> str:
        return "stubbed"


# ---------------------------------------------------------------------------
# Writing an earlier name does not move the current accessor
# ---------------------------------------------------------------------------


class TestAssignmentStaysOnTheEarlierName:
    def test_ai_assignment_leaves_photo_mockups_alone(self) -> None:
        client = SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
        current = client.photo_mockups
        client.ai = _Stub()

        assert client.photo_mockups is current

    def test_mockups_assignment_leaves_psd_mockups_alone(self) -> None:
        client = SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
        current = client.psd_mockups
        client.mockups = _Stub()

        assert client.psd_mockups is current

    async def test_async_ai_assignment_leaves_photo_mockups_alone(self) -> None:
        client = AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
        current = client.photo_mockups
        client.ai = _Stub()

        assert client.photo_mockups is current

    async def test_async_mockups_assignment_leaves_psd_mockups_alone(self) -> None:
        client = AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
        current = client.psd_mockups
        client.mockups = _Stub()

        assert client.psd_mockups is current


# ---------------------------------------------------------------------------
# Save, override, restore: both accessors come back to where they started
# ---------------------------------------------------------------------------


class TestSaveAndRestoreRoundTrip:
    def test_ai_round_trip_restores_both_accessors(self) -> None:
        client = SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
        with pytest.warns(DeprecationWarning):
            saved_earlier = client.ai
        saved_current = client.photo_mockups

        client.ai = _Stub()
        client.ai = saved_earlier

        with pytest.warns(DeprecationWarning):
            assert client.ai is saved_earlier
        assert client.photo_mockups is saved_current

    def test_mockups_round_trip_restores_both_accessors(self) -> None:
        client = SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
        with pytest.warns(DeprecationWarning):
            saved_earlier = client.mockups
        saved_current = client.psd_mockups

        client.mockups = _Stub()
        client.mockups = saved_earlier

        with pytest.warns(DeprecationWarning):
            assert client.mockups is saved_earlier
        assert client.psd_mockups is saved_current

    async def test_async_round_trip_restores_both_accessors(self) -> None:
        client = AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
        with pytest.warns(DeprecationWarning):
            saved_ai = client.ai
            saved_mockups = client.mockups
        saved_photo = client.photo_mockups
        saved_psd = client.psd_mockups

        client.ai = _Stub()
        client.mockups = _Stub()
        client.ai = saved_ai
        client.mockups = saved_mockups

        with pytest.warns(DeprecationWarning):
            assert client.ai is saved_ai
            assert client.mockups is saved_mockups
        assert client.photo_mockups is saved_photo
        assert client.psd_mockups is saved_psd

    def test_round_trip_keeps_the_current_accessor_on_the_current_endpoint(
        self, mock_api: respx.MockRouter
    ) -> None:
        earlier = mock_api.get(EARLIER_PHOTO_PATH).mock(
            return_value=httpx.Response(200, json=MOCK_2D_MOCKUP_LIST_RESPONSE)
        )
        current = mock_api.get(CURRENT_PHOTO_PATH).mock(
            return_value=httpx.Response(200, json=MOCK_2D_MOCKUP_LIST_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.warns(DeprecationWarning):
                saved = client.ai
            client.ai = _Stub()
            client.ai = saved

            client.photo_mockups.list()

        assert current.called
        assert not earlier.called


# ---------------------------------------------------------------------------
# Deleting an earlier name (what mock.patch.object does on exit)
# ---------------------------------------------------------------------------


class TestEarlierNamesAreDeletable:
    def test_patch_object_ai_round_trip(self, mock_api: respx.MockRouter) -> None:
        earlier = mock_api.get(EARLIER_PHOTO_PATH).mock(
            return_value=httpx.Response(200, json=MOCK_2D_MOCKUP_LIST_RESPONSE)
        )
        current = mock_api.get(CURRENT_PHOTO_PATH).mock(
            return_value=httpx.Response(200, json=MOCK_2D_MOCKUP_LIST_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            saved_current = client.photo_mockups
            stub = _Stub()
            with mock.patch.object(client, "ai", stub):
                with pytest.warns(DeprecationWarning):
                    assert client.ai is stub

            # Back to the accessor the client was built with: earlier endpoint.
            with pytest.warns(DeprecationWarning):
                client.ai.list()
            assert client.photo_mockups is saved_current

        assert earlier.called
        assert not current.called

    def test_patch_object_mockups_round_trip(self, mock_api: respx.MockRouter) -> None:
        earlier = mock_api.get(EARLIER_PSD_PATH).mock(
            return_value=httpx.Response(200, json=MOCK_MOCKUP_LIST_RESPONSE)
        )
        current = mock_api.get(CURRENT_PSD_PATH).mock(
            return_value=httpx.Response(200, json=MOCK_MOCKUP_LIST_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            saved_current = client.psd_mockups
            with mock.patch.object(client, "mockups", _Stub()):
                pass

            with pytest.warns(DeprecationWarning):
                client.mockups.list()
            assert client.psd_mockups is saved_current

        assert earlier.called
        assert not current.called

    async def test_async_patch_object_round_trip(self, mock_api: respx.MockRouter) -> None:
        earlier = mock_api.get(EARLIER_PHOTO_PATH).mock(
            return_value=httpx.Response(200, json=MOCK_2D_MOCKUP_LIST_RESPONSE)
        )
        current = mock_api.get(CURRENT_PHOTO_PATH).mock(
            return_value=httpx.Response(200, json=MOCK_2D_MOCKUP_LIST_RESPONSE)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            saved_current = client.photo_mockups
            with mock.patch.object(client, "ai", _Stub()):
                pass

            with pytest.warns(DeprecationWarning):
                await client.ai.list()
            assert client.photo_mockups is saved_current

        assert earlier.called
        assert not current.called

    async def test_async_patch_object_mockups_round_trip(self, mock_api: respx.MockRouter) -> None:
        earlier = mock_api.get(EARLIER_PSD_PATH).mock(
            return_value=httpx.Response(200, json=MOCK_MOCKUP_LIST_RESPONSE)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with mock.patch.object(client, "mockups", _Stub()):
                pass
            with pytest.warns(DeprecationWarning):
                await client.mockups.list()

        assert earlier.called


# ---------------------------------------------------------------------------
# Watchdog: everything the earlier names already did keeps happening
# ---------------------------------------------------------------------------


class TestEarlierNamesKeepTheirExistingBehaviour:
    def test_reading_an_earlier_name_still_warns(self) -> None:
        client = SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
        with pytest.warns(DeprecationWarning):
            assert client.ai is not None
        with pytest.warns(DeprecationWarning):
            assert client.mockups is not None

    def test_assignment_is_still_what_the_earlier_name_returns(self) -> None:
        client = SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
        stub = _Stub()
        client.ai = stub
        with pytest.warns(DeprecationWarning):
            assert client.ai is stub
            assert client.ai.list() == "stubbed"

    def test_earlier_names_still_call_earlier_endpoints(self, mock_api: respx.MockRouter) -> None:
        earlier = mock_api.get(EARLIER_PHOTO_PATH).mock(
            return_value=httpx.Response(200, json=MOCK_2D_MOCKUP_LIST_RESPONSE)
        )
        current = mock_api.get(CURRENT_PHOTO_PATH).mock(
            return_value=httpx.Response(200, json=MOCK_2D_MOCKUP_LIST_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.warns(DeprecationWarning):
                client.ai.list()

        assert earlier.called
        assert not current.called
