"""Earlier accessors stay pinned to the endpoints they have always called.

``client.ai`` and ``client.mockups`` are the accessors that shipped before the
0.11.0 naming pass. Code written against them is code that was never changed,
so they keep calling ``/api/v1/sudoai/2d-mockups`` and ``/api/v1/mockups`` —
the endpoints those callers have been reaching all along. ``photo_mockups`` and
``psd_mockups`` are the current accessors and use the current endpoints.

Assignment to the earlier names keeps working, so test doubles injected by
existing suites are still the object that gets called.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest

from sudomock import AsyncSudoMock, SudoMock

from .conftest import (
    MOCK_2D_MOCKUP_CREATE_RESPONSE,
    MOCK_2D_MOCKUP_GET_RESPONSE,
    MOCK_2D_MOCKUP_LIST_RESPONSE,
    MOCK_MOCKUP_GET_RESPONSE,
    MOCK_MOCKUP_LIST_RESPONSE,
    TEST_API_KEY,
    TEST_BASE_URL,
)

if TYPE_CHECKING:
    import respx

PSD_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
PHOTO_ID = "2d-mockup-001"

EARLIER_PHOTO_PATH = "/api/v1/sudoai/2d-mockups"
EARLIER_PSD_PATH = "/api/v1/mockups"
CURRENT_PHOTO_PATH = "/api/v1/photo-mockups"
CURRENT_PSD_PATH = "/api/v1/psd-mockups"


# ---------------------------------------------------------------------------
# Earlier accessors -> earlier endpoints
# ---------------------------------------------------------------------------


class TestEarlierAccessorsKeepEarlierEndpoints:
    def test_ai_list_calls_earlier_endpoint(self, mock_api: respx.MockRouter) -> None:
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

    def test_ai_create_posts_to_earlier_endpoint(self, mock_api: respx.MockRouter) -> None:
        earlier = mock_api.post(EARLIER_PHOTO_PATH).mock(
            return_value=httpx.Response(201, json=MOCK_2D_MOCKUP_CREATE_RESPONSE)
        )
        current = mock_api.post(CURRENT_PHOTO_PATH).mock(
            return_value=httpx.Response(201, json=MOCK_2D_MOCKUP_CREATE_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.warns(DeprecationWarning):
                client.ai.create(source_url="https://example.com/p.jpg")

        assert earlier.called
        assert not current.called

    def test_ai_get_calls_earlier_endpoint(self, mock_api: respx.MockRouter) -> None:
        earlier = mock_api.get(f"{EARLIER_PHOTO_PATH}/{PHOTO_ID}").mock(
            return_value=httpx.Response(200, json=MOCK_2D_MOCKUP_GET_RESPONSE)
        )
        current = mock_api.get(f"{CURRENT_PHOTO_PATH}/{PHOTO_ID}").mock(
            return_value=httpx.Response(200, json=MOCK_2D_MOCKUP_GET_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.warns(DeprecationWarning):
                client.ai.get(PHOTO_ID)

        assert earlier.called
        assert not current.called

    def test_mockups_list_calls_earlier_endpoint(self, mock_api: respx.MockRouter) -> None:
        earlier = mock_api.get(EARLIER_PSD_PATH).mock(
            return_value=httpx.Response(200, json=MOCK_MOCKUP_LIST_RESPONSE)
        )
        current = mock_api.get(CURRENT_PSD_PATH).mock(
            return_value=httpx.Response(200, json=MOCK_MOCKUP_LIST_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.warns(DeprecationWarning):
                client.mockups.list()

        assert earlier.called
        assert not current.called

    def test_mockups_get_calls_earlier_endpoint(self, mock_api: respx.MockRouter) -> None:
        earlier = mock_api.get(f"{EARLIER_PSD_PATH}/{PSD_UUID}").mock(
            return_value=httpx.Response(200, json=MOCK_MOCKUP_GET_RESPONSE)
        )
        current = mock_api.get(f"{CURRENT_PSD_PATH}/{PSD_UUID}").mock(
            return_value=httpx.Response(200, json=MOCK_MOCKUP_GET_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.warns(DeprecationWarning):
                client.mockups.get(PSD_UUID)

        assert earlier.called
        assert not current.called

    async def test_async_ai_list_calls_earlier_endpoint(self, mock_api: respx.MockRouter) -> None:
        earlier = mock_api.get(EARLIER_PHOTO_PATH).mock(
            return_value=httpx.Response(200, json=MOCK_2D_MOCKUP_LIST_RESPONSE)
        )
        current = mock_api.get(CURRENT_PHOTO_PATH).mock(
            return_value=httpx.Response(200, json=MOCK_2D_MOCKUP_LIST_RESPONSE)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.warns(DeprecationWarning):
                accessor = client.ai
            await accessor.list()

        assert earlier.called
        assert not current.called

    async def test_async_mockups_list_calls_earlier_endpoint(
        self, mock_api: respx.MockRouter
    ) -> None:
        earlier = mock_api.get(EARLIER_PSD_PATH).mock(
            return_value=httpx.Response(200, json=MOCK_MOCKUP_LIST_RESPONSE)
        )
        current = mock_api.get(CURRENT_PSD_PATH).mock(
            return_value=httpx.Response(200, json=MOCK_MOCKUP_LIST_RESPONSE)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.warns(DeprecationWarning):
                accessor = client.mockups
            await accessor.list()

        assert earlier.called
        assert not current.called


# ---------------------------------------------------------------------------
# Current accessors -> current endpoints
# ---------------------------------------------------------------------------


class TestCurrentAccessorsKeepCurrentEndpoints:
    def test_photo_mockups_list_calls_current_endpoint(self, mock_api: respx.MockRouter) -> None:
        earlier = mock_api.get(EARLIER_PHOTO_PATH).mock(
            return_value=httpx.Response(200, json=MOCK_2D_MOCKUP_LIST_RESPONSE)
        )
        current = mock_api.get(CURRENT_PHOTO_PATH).mock(
            return_value=httpx.Response(200, json=MOCK_2D_MOCKUP_LIST_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            client.photo_mockups.list()

        assert current.called
        assert not earlier.called

    def test_psd_mockups_list_calls_current_endpoint(self, mock_api: respx.MockRouter) -> None:
        earlier = mock_api.get(EARLIER_PSD_PATH).mock(
            return_value=httpx.Response(200, json=MOCK_MOCKUP_LIST_RESPONSE)
        )
        current = mock_api.get(CURRENT_PSD_PATH).mock(
            return_value=httpx.Response(200, json=MOCK_MOCKUP_LIST_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            client.psd_mockups.list()

        assert current.called
        assert not earlier.called

    async def test_async_photo_mockups_list_calls_current_endpoint(
        self, mock_api: respx.MockRouter
    ) -> None:
        earlier = mock_api.get(EARLIER_PHOTO_PATH).mock(
            return_value=httpx.Response(200, json=MOCK_2D_MOCKUP_LIST_RESPONSE)
        )
        current = mock_api.get(CURRENT_PHOTO_PATH).mock(
            return_value=httpx.Response(200, json=MOCK_2D_MOCKUP_LIST_RESPONSE)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            await client.photo_mockups.list()

        assert current.called
        assert not earlier.called


# ---------------------------------------------------------------------------
# Assignment to the earlier names still reaches the injected double
# ---------------------------------------------------------------------------


class _Stub:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def list(self) -> str:
        self.calls.append("list")
        return "stubbed"


class TestEarlierNamesStayAssignable:
    def test_ai_assignment_is_what_ai_returns(self) -> None:
        client = SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
        stub = _Stub()
        client.ai = stub
        with pytest.warns(DeprecationWarning):
            assert client.ai is stub
        with pytest.warns(DeprecationWarning):
            assert client.ai.list() == "stubbed"
        assert stub.calls == ["list"]

    def test_mockups_assignment_is_what_mockups_returns(self) -> None:
        client = SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
        stub = _Stub()
        client.mockups = stub
        with pytest.warns(DeprecationWarning):
            assert client.mockups is stub

    async def test_async_assignment_is_what_the_earlier_names_return(self) -> None:
        client = AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
        stub = _Stub()
        client.ai = stub
        client.mockups = stub
        with pytest.warns(DeprecationWarning):
            assert client.ai is stub
        with pytest.warns(DeprecationWarning):
            assert client.mockups is stub
