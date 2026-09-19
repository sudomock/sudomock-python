"""Family paths and helper names (0.11.0).

``client.photo_mockups`` talks to ``/api/v1/photo-mockups`` and
``client.psd_mockups`` to ``/api/v1/psd-mockups``. ``client.ai`` and
``client.mockups`` keep working as deprecated aliases of those same objects,
and the ``PhotoMockup*`` model names are the same classes as the older
``TwoDMockup*`` / ``AIRender`` names.
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

import httpx
import pytest

import sudomock
from sudomock import AsyncSudoMock, SudoMock
from sudomock.models import (
    AIRender,
    PhotoMockup,
    PhotoMockupList,
    PhotoMockupPrintAreasUpdate,
    PhotoMockupRender,
    TwoDMockup,
    TwoDMockupList,
    TwoDPrintAreasUpdate,
)

from .conftest import (
    MOCK_2D_MOCKUP_CREATE_RESPONSE,
    MOCK_2D_MOCKUP_LIST_RESPONSE,
    MOCK_MOCKUP_GET_RESPONSE,
    MOCK_MOCKUP_LIST_RESPONSE,
    TEST_API_KEY,
    TEST_BASE_URL,
)

if TYPE_CHECKING:
    import respx

PSD_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


# ---------------------------------------------------------------------------
# Wire paths
# ---------------------------------------------------------------------------


class TestFamilyPaths:
    def test_photo_mockups_create_posts_to_family_path(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/photo-mockups").mock(
            return_value=httpx.Response(201, json=MOCK_2D_MOCKUP_CREATE_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.photo_mockups.create(source_url="https://example.com/p.jpg")

        assert route.called
        assert isinstance(result, PhotoMockup)

    def test_psd_mockups_get_uses_family_path(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.get(f"/api/v1/psd-mockups/{PSD_UUID}").mock(
            return_value=httpx.Response(200, json=MOCK_MOCKUP_GET_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.psd_mockups.get(PSD_UUID)

        assert route.called
        assert result.uuid == PSD_UUID

    def test_new_names_do_not_warn(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/photo-mockups").mock(
            return_value=httpx.Response(200, json=MOCK_2D_MOCKUP_LIST_RESPONSE)
        )
        mock_api.get("/api/v1/psd-mockups").mock(
            return_value=httpx.Response(200, json=MOCK_MOCKUP_LIST_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                client.photo_mockups.list()
                client.psd_mockups.list()

    async def test_async_photo_mockups_list_uses_family_path(
        self, mock_api: respx.MockRouter
    ) -> None:
        route = mock_api.get("/api/v1/photo-mockups").mock(
            return_value=httpx.Response(200, json=MOCK_2D_MOCKUP_LIST_RESPONSE)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            listing = await client.photo_mockups.list()

        assert route.called
        assert isinstance(listing, PhotoMockupList)

    async def test_async_psd_mockups_list_uses_family_path(
        self, mock_api: respx.MockRouter
    ) -> None:
        route = mock_api.get("/api/v1/psd-mockups").mock(
            return_value=httpx.Response(200, json=MOCK_MOCKUP_LIST_RESPONSE)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            listing = await client.psd_mockups.list()

        assert route.called
        assert listing.total == 1


# ---------------------------------------------------------------------------
# Deprecated helper names
# ---------------------------------------------------------------------------


class TestDeprecatedAliases:
    def test_sync_ai_is_photo_mockups(self) -> None:
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.warns(DeprecationWarning, match="photo_mockups"):
                assert client.ai is client.photo_mockups

    def test_sync_mockups_is_psd_mockups(self) -> None:
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.warns(DeprecationWarning, match="psd_mockups"):
                assert client.mockups is client.psd_mockups

    async def test_async_ai_is_photo_mockups(self) -> None:
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.warns(DeprecationWarning, match="photo_mockups"):
                assert client.ai is client.photo_mockups

    async def test_async_mockups_is_psd_mockups(self) -> None:
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.warns(DeprecationWarning, match="psd_mockups"):
                assert client.mockups is client.psd_mockups

    def test_alias_still_reaches_family_path(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.get("/api/v1/photo-mockups").mock(
            return_value=httpx.Response(200, json=MOCK_2D_MOCKUP_LIST_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.warns(DeprecationWarning):
                client.ai.list()

        assert route.called


# ---------------------------------------------------------------------------
# Model name aliases
# ---------------------------------------------------------------------------


class TestModelAliases:
    @pytest.mark.parametrize(
        ("new", "old"),
        [
            (PhotoMockup, TwoDMockup),
            (PhotoMockupList, TwoDMockupList),
            (PhotoMockupPrintAreasUpdate, TwoDPrintAreasUpdate),
            (PhotoMockupRender, AIRender),
        ],
    )
    def test_same_class(self, new: type, old: type) -> None:
        assert new is old

    @pytest.mark.parametrize(
        "name",
        [
            "PhotoMockup",
            "PhotoMockupList",
            "PhotoMockupPrintAreasUpdate",
            "PhotoMockupRender",
            "TwoDMockup",
            "TwoDMockupList",
            "TwoDPrintAreasUpdate",
            "AIRender",
        ],
    )
    def test_exported(self, name: str) -> None:
        assert name in sudomock.__all__
        assert getattr(sudomock, name) is getattr(sudomock.models, name)
