"""Tests for the asynchronous SudoMock client."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest

from sudomock import AsyncSudoMock
from sudomock.exceptions import (
    AuthenticationError,
    InsufficientCreditsError,
    RateLimitError,
    ServerError,
    SudoMockError,
)
from sudomock.models import AccountInfo, AIRender, Mockup, MockupList, Render

from .conftest import (
    ERROR_401,
    ERROR_402,
    ERROR_429,
    ERROR_500,
    MOCK_AI_RENDER_RESPONSE,
    MOCK_ME_RESPONSE,
    MOCK_MOCKUP,
    MOCK_MOCKUP_GET_RESPONSE,
    MOCK_MOCKUP_LIST_RESPONSE,
    MOCK_RENDER_RESPONSE,
    TEST_API_KEY,
    TEST_BASE_URL,
)

if TYPE_CHECKING:
    import respx

# ---------------------------------------------------------------------------
# Client initialization
# ---------------------------------------------------------------------------


class TestAsyncClientInit:
    async def test_api_key_from_constructor(self) -> None:
        client = AsyncSudoMock(api_key="sm_explicit")
        assert client._api_key == "sm_explicit"
        await client.close()

    async def test_api_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SUDOMOCK_API_KEY", "sm_from_env")
        client = AsyncSudoMock()
        assert client._api_key == "sm_from_env"
        await client.close()

    async def test_missing_api_key_raises(self) -> None:
        with pytest.raises(SudoMockError, match="API key"):
            AsyncSudoMock()

    async def test_async_context_manager(self) -> None:
        async with AsyncSudoMock(api_key="sm_x") as client:
            assert client._api_key == "sm_x"


# ---------------------------------------------------------------------------
# Mockups resource
# ---------------------------------------------------------------------------


class TestAsyncMockupsList:
    async def test_list_mockups(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/mockups").mock(
            return_value=httpx.Response(200, json=MOCK_MOCKUP_LIST_RESPONSE)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.mockups.list()

        assert isinstance(result, MockupList)
        assert result.total == 1
        assert result.mockups[0].uuid == MOCK_MOCKUP["uuid"]

    async def test_list_with_params(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.get("/api/v1/mockups").mock(
            return_value=httpx.Response(200, json=MOCK_MOCKUP_LIST_RESPONSE)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            await client.mockups.list(limit=10, offset=5)

        request = route.calls.last.request
        assert request.url.params["limit"] == "10"
        assert request.url.params["offset"] == "5"


class TestAsyncMockupsGet:
    async def test_get_mockup(self, mock_api: respx.MockRouter) -> None:
        uuid = MOCK_MOCKUP["uuid"]
        mock_api.get(f"/api/v1/mockups/{uuid}").mock(
            return_value=httpx.Response(200, json=MOCK_MOCKUP_GET_RESPONSE)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.mockups.get(uuid)

        assert isinstance(result, Mockup)
        assert result.name == "Black T-Shirt Front"


class TestAsyncMockupsDelete:
    async def test_delete_mockup(self, mock_api: respx.MockRouter) -> None:
        uuid = "some-uuid"
        mock_api.delete(f"/api/v1/mockups/{uuid}").mock(return_value=httpx.Response(204))
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            await client.mockups.delete(uuid)


# ---------------------------------------------------------------------------
# Renders resource
# ---------------------------------------------------------------------------


class TestAsyncRenders:
    async def test_create_render(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/api/v1/renders").mock(
            return_value=httpx.Response(200, json=MOCK_RENDER_RESPONSE)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.renders.create(
                mockup_uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                smart_objects=[
                    {
                        "uuid": "11111111-2222-3333-4444-555555555555",
                        "asset": {"url": "https://example.com/design.png"},
                    }
                ],
            )

        assert isinstance(result, Render)
        assert "render.webp" in result.url

    async def test_insufficient_credits(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/api/v1/renders").mock(return_value=httpx.Response(402, json=ERROR_402))
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(InsufficientCreditsError):
                await client.renders.create(
                    mockup_uuid="test-uuid",
                    smart_objects=[{"uuid": "so-1", "asset": {"url": "https://x.com/d.png"}}],
                )


# ---------------------------------------------------------------------------
# AI resource
# ---------------------------------------------------------------------------


class TestAsyncAI:
    async def test_ai_render(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/api/v1/sudoai/render").mock(
            return_value=httpx.Response(200, json=MOCK_AI_RENDER_RESPONSE)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.ai.render(
                source_url="https://example.com/product.jpg",
                artwork_url="https://example.com/design.png",
            )

        assert isinstance(result, AIRender)
        assert "ai-renders" in result.url


# ---------------------------------------------------------------------------
# Account resource
# ---------------------------------------------------------------------------


class TestAsyncAccount:
    async def test_get_account(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/me").mock(return_value=httpx.Response(200, json=MOCK_ME_RESPONSE))
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.account.get()

        assert isinstance(result, AccountInfo)
        assert result.usage.credits_remaining == 37153


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestAsyncErrorHandling:
    async def test_401_raises_auth_error(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/mockups").mock(return_value=httpx.Response(401, json=ERROR_401))
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(AuthenticationError):
                await client.mockups.list()

    async def test_429_raises_rate_limit_error(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/mockups").mock(return_value=httpx.Response(429, json=ERROR_429))
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(RateLimitError):
                await client.mockups.list()

    async def test_500_raises_server_error(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/mockups").mock(return_value=httpx.Response(500, json=ERROR_500))
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(ServerError):
                await client.mockups.list()


# ---------------------------------------------------------------------------
# Retry behavior
# ---------------------------------------------------------------------------


class TestAsyncRetry:
    async def test_retries_on_500(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.get("/api/v1/mockups")
        route.side_effect = [
            httpx.Response(500, json=ERROR_500),
            httpx.Response(200, json=MOCK_MOCKUP_LIST_RESPONSE),
        ]
        async with AsyncSudoMock(
            api_key=TEST_API_KEY, base_url=TEST_BASE_URL, max_retries=2
        ) as client:
            result = await client.mockups.list()

        assert result.total == 1
        assert len(route.calls) == 2

    async def test_no_retry_on_4xx(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.get("/api/v1/mockups")
        route.mock(return_value=httpx.Response(401, json=ERROR_401))
        async with AsyncSudoMock(
            api_key=TEST_API_KEY, base_url=TEST_BASE_URL, max_retries=3
        ) as client:
            with pytest.raises(AuthenticationError):
                await client.mockups.list()

        assert len(route.calls) == 1


# ---------------------------------------------------------------------------
# User-Agent header
# ---------------------------------------------------------------------------


class TestAsyncUserAgent:
    async def test_user_agent_header(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.get("/api/v1/mockups").mock(
            return_value=httpx.Response(200, json=MOCK_MOCKUP_LIST_RESPONSE)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            await client.mockups.list()

        ua = route.calls.last.request.headers["user-agent"]
        assert ua.startswith("sudomock-python/")
