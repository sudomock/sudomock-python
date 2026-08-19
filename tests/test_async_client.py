"""Tests for the asynchronous SudoMock client."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import UUID

import httpx
import pytest

from sudomock import AsyncSudoMock
from sudomock.exceptions import (
    AuthenticationError,
    InsufficientCreditsError,
    JobFailedError,
    JobTimeoutError,
    RateLimitError,
    ServerError,
    SudoMockError,
    ValidationError,
)
from sudomock.models import (
    AccountInfo,
    AIRender,
    BackgroundRemoval,
    JobAccepted,
    Mockup,
    MockupList,
    Quad,
    Render,
    StudioActionReceipt,
    StudioResultEvent,
    StudioResultPayload,
    StudioSession,
    TwoDMockup,
    TwoDPrintAreasUpdate,
)

from .conftest import (
    ERROR_401,
    ERROR_402,
    ERROR_422_INVALID_IMAGE,
    ERROR_429,
    ERROR_500,
    MOCK_2D_MOCKUP_GET_RESPONSE,
    MOCK_2D_MOCKUP_JOB_ACCEPTED_RESPONSE,
    MOCK_2D_MOCKUP_JOB_FAILED_RESPONSE,
    MOCK_2D_MOCKUP_JOB_QUEUED_RESPONSE,
    MOCK_2D_MOCKUP_JOB_SUCCEEDED_RESPONSE,
    MOCK_2D_MOCKUP_LIST_RESPONSE,
    MOCK_2D_PRINT_AREAS_UPDATE_RESPONSE,
    MOCK_AI_RENDER_JOB_ACCEPTED_RESPONSE,
    MOCK_AI_RENDER_RESPONSE,
    MOCK_ME_RESPONSE,
    MOCK_MOCKUP,
    MOCK_MOCKUP_GET_RESPONSE,
    MOCK_MOCKUP_LIST_RESPONSE,
    MOCK_REMOVE_BACKGROUND_RESPONSE,
    MOCK_RENDER_RESPONSE,
    MOCK_TEXT_RENDER_RESPONSE,
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
        assert result.text_layers[0].font_postscript_name == "Montserrat-Bold"


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

    async def test_create_text_only_render(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/renders").mock(
            return_value=httpx.Response(200, json=MOCK_TEXT_RENDER_RESPONSE)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.renders.create(
                mockup_uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                text_layers=[
                    {
                        "uuid": "66666666-7777-8888-9999-000000000000",
                        "text": "Aylin",
                        "font": "Montserrat-Bold",
                        "font_size": 120,
                        "color": "#FFFFFF",
                        "stroke_color": ["#111111", None],
                        "fit": "overflow",
                    },
                    {
                        "uuid": "88888888-9999-aaaa-bbbb-cccccccccccc",
                        "segments": [{"index": 1, "text": "Studio"}],
                    },
                ],
                export_options={"image_format": "webp", "image_size": 2048},
            )

        assert json.loads(route.calls.last.request.content) == {
            "mockup_uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "text_layers": [
                {
                    "uuid": "66666666-7777-8888-9999-000000000000",
                    "text": "Aylin",
                    "font": "Montserrat-Bold",
                    "font_size": 120,
                    "color": "#FFFFFF",
                    "stroke_color": ["#111111", None],
                    "fit": "overflow",
                },
                {
                    "uuid": "88888888-9999-aaaa-bbbb-cccccccccccc",
                    "segments": [{"index": 1, "text": "Studio"}],
                },
            ],
            "export_options": {"image_format": "webp", "image_size": 2048},
        }
        assert result.warnings[0].code == "TEXT_FIT_SHRUNK"
        assert "text_layers" not in result.model_dump()
        assert result.warnings[0].code == "TEXT_FIT_SHRUNK"

    async def test_insufficient_credits(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/api/v1/renders").mock(return_value=httpx.Response(402, json=ERROR_402))
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(InsufficientCreditsError) as exc_info:
                await client.renders.create(
                    mockup_uuid="test-uuid",
                    smart_objects=[{"uuid": "so-1", "asset": {"url": "https://x.com/d.png"}}],
                )
            assert exc_info.value.error_code == "credits_exhausted"


# ---------------------------------------------------------------------------
# AI resource
# ---------------------------------------------------------------------------


class TestAsyncAI:
    async def test_ai_list_customizable_only(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.get("/api/v1/sudoai/2d-mockups").mock(
            return_value=httpx.Response(200, json=MOCK_2D_MOCKUP_LIST_RESPONSE)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            listing = await client.ai.list(
                limit=20,
                customizable_only=True,
            )

        assert listing.mockups[0].customizable is True
        assert listing.mockups[0].print_areas[0].print_area_id == "pa-1"
        assert listing.mockups[0].surfaces[0].surface_uuid == "surface-1"
        assert not hasattr(listing.mockups[0].surfaces[0], "coverage")
        assert route.calls.last.request.url.params["customizable_only"] == "true"

    async def test_ai_render(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/sudoai/2d-mockups/2d-mockup-001/render").mock(
            return_value=httpx.Response(200, json=MOCK_AI_RENDER_RESPONSE)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.ai.render(
                mockup_uuid="2d-mockup-001",
                print_areas=[{"uuid": "pa-1", "artwork_url": "https://x.com/d.png"}],
            )

        assert isinstance(result, AIRender)
        assert "ai-renders" in result.url
        assert result.render_uuid == "render-2d-001"

        body = json.loads(route.calls.last.request.content)
        # Real contract: mockup id is in the PATH, body is print_areas[] only.
        assert "mockup_uuid" not in body
        assert body["print_areas"][0]["uuid"] == "pa-1"

    async def test_ai_render_async(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/sudoai/2d-mockups/2d-mockup-001/render").mock(
            return_value=httpx.Response(202, json=MOCK_AI_RENDER_JOB_ACCEPTED_RESPONSE)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.ai.render(
                mockup_uuid="2d-mockup-001",
                print_areas=[{"uuid": "pa-1", "artwork_url": "https://x.com/d.png"}],
                is_async=True,
            )

        # Async submit: 202 returns a JobAccepted (job envelope), NOT an AIRender.
        assert isinstance(result, JobAccepted)
        assert result.job_id == "2d-render-job-001"
        assert result.kind == "2d_render"
        assert result.status == "queued"
        assert result.status_url == "/api/v1/jobs/2d-render-job-001"

        body = json.loads(route.calls.last.request.content)
        assert body["is_async"] is True
        assert body["print_areas"][0]["uuid"] == "pa-1"
        assert "mockup_uuid" not in body

    async def test_ai_render_product_surface_uses_surface_uuid(
        self, mock_api: respx.MockRouter
    ) -> None:
        route = mock_api.post("/api/v1/sudoai/2d-mockups/2d-mockup-001/render").mock(
            return_value=httpx.Response(200, json=MOCK_AI_RENDER_RESPONSE)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            await client.ai.render(
                mockup_uuid="2d-mockup-001",
                print_areas=[{"surface_uuid": "surface-1", "color": "#FF0000"}],
            )

        surface = json.loads(route.calls.last.request.content)["print_areas"][0]
        assert surface == {"surface_uuid": "surface-1", "color": "#FF0000"}

    async def test_ai_create(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/sudoai/2d-mockups").mock(
            return_value=httpx.Response(201, json=MOCK_2D_MOCKUP_GET_RESPONSE)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.ai.create(
                source_url="https://example.com/product.jpg",
                name="Product Front",
                idempotency_key="create-2d-001",
            )

        # Sync default: 201 returns the full mockup, NOT a job.
        assert isinstance(result, TwoDMockup)
        assert result.mockup_id == "2d-mockup-001"
        assert result.status == "ready"
        assert result.quads[0].print_area_id == "pa-1"
        assert result.quads[0].name == "Front"
        assert result.customizable is True
        assert result.surfaces[0].surface_uuid == "surface-1"
        assert json.loads(route.calls.last.request.content) == {
            "source_url": "https://example.com/product.jpg",
            "name": "Product Front",
        }
        assert route.calls.last.request.headers["idempotency-key"] == "create-2d-001"
        assert route.calls.last.request.headers["x-api-key"] == TEST_API_KEY

    async def test_ai_create_async(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/sudoai/2d-mockups").mock(
            return_value=httpx.Response(202, json=MOCK_2D_MOCKUP_JOB_ACCEPTED_RESPONSE)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.ai.create(
                source_url="https://example.com/product.jpg",
                is_async=True,
            )

        assert isinstance(result, JobAccepted)
        assert result.job_id == "2d-create-job-001"
        assert result.kind == "2d_create"
        assert result.status == "queued"
        assert result.status_url == "/api/v1/jobs/2d-create-job-001"
        assert json.loads(route.calls.last.request.content) == {
            "source_url": "https://example.com/product.jpg",
            "is_async": True,
        }

    async def test_ai_create_base64_generates_stable_idempotency_key(
        self, mock_api: respx.MockRouter
    ) -> None:
        route = mock_api.post("/api/v1/sudoai/2d-mockups")
        route.side_effect = [
            httpx.Response(500, json=ERROR_500),
            httpx.Response(202, json=MOCK_2D_MOCKUP_JOB_ACCEPTED_RESPONSE),
        ]

        async with AsyncSudoMock(
            api_key=TEST_API_KEY,
            base_url=TEST_BASE_URL,
            max_retries=2,
        ) as client:
            await client.ai.create(source_base64="aW1hZ2U=")

        assert json.loads(route.calls.last.request.content) == {"source_base64": "aW1hZ2U="}
        keys = [call.request.headers["idempotency-key"] for call in route.calls]
        assert len(keys) == 2
        assert keys[0] == keys[1]
        assert UUID(keys[0]).version == 4

    async def test_ai_create_insufficient_credits(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/sudoai/2d-mockups").mock(
            return_value=httpx.Response(402, json=ERROR_402)
        )

        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(InsufficientCreditsError):
                await client.ai.create(source_url="https://example.com/product.jpg")

        assert len(route.calls) == 1

    async def test_ai_create_requires_exactly_one_source(self, mock_api: respx.MockRouter) -> None:
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(ValueError, match="exactly one"):
                await client.ai.create()
            with pytest.raises(ValueError, match="exactly one"):
                await client.ai.create(source_url="")
            with pytest.raises(ValueError, match="exactly one"):
                await client.ai.create(
                    source_url="https://example.com/product.jpg",
                    source_base64="aW1hZ2U=",
                )

        assert len(mock_api.calls) == 0

    async def test_ai_wait_for_2d_mockup_success(self, mock_api: respx.MockRouter) -> None:
        job_route = mock_api.get("/api/v1/jobs/2d-create-job-001")
        job_route.side_effect = [
            httpx.Response(200, json=MOCK_2D_MOCKUP_JOB_QUEUED_RESPONSE),
            httpx.Response(200, json=MOCK_2D_MOCKUP_JOB_SUCCEEDED_RESPONSE),
        ]
        detail_route = mock_api.get("/api/v1/sudoai/2d-mockups/2d-mockup-001").mock(
            return_value=httpx.Response(200, json=MOCK_2D_MOCKUP_GET_RESPONSE)
        )

        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.ai.wait_for_2d_mockup(
                "2d-create-job-001",
                poll_interval=0.0,
            )

        assert isinstance(result, TwoDMockup)
        assert result.mockup_id == "2d-mockup-001"
        assert result.name == "Flat Tee Front"
        assert result.quads[0].print_area_id == "pa-1"
        assert len(job_route.calls) == 2
        assert len(detail_route.calls) == 1

    async def test_ai_wait_for_2d_mockup_rejects_wrong_job_kind(
        self, mock_api: respx.MockRouter
    ) -> None:
        mock_api.get("/api/v1/jobs/video-job-001").mock(
            return_value=httpx.Response(
                200,
                json={
                    **MOCK_2D_MOCKUP_JOB_SUCCEEDED_RESPONSE,
                    "job_id": "video-job-001",
                    "kind": "video",
                },
            )
        )

        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(SudoMockError, match="expected '2d_create'"):
                await client.ai.wait_for_2d_mockup("video-job-001", poll_interval=0.0)

    async def test_ai_wait_for_2d_mockup_missing_mockup_uuid(
        self, mock_api: respx.MockRouter
    ) -> None:
        mock_api.get("/api/v1/jobs/2d-create-job-001").mock(
            return_value=httpx.Response(
                200,
                json={**MOCK_2D_MOCKUP_JOB_SUCCEEDED_RESPONSE, "mockup_uuid": ""},
            )
        )

        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(SudoMockError, match="without a mockup UUID"):
                await client.ai.wait_for_2d_mockup("2d-create-job-001", poll_interval=0.0)

    async def test_ai_wait_for_2d_mockup_failure(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/jobs/2d-create-job-001").mock(
            return_value=httpx.Response(200, json=MOCK_2D_MOCKUP_JOB_FAILED_RESPONSE)
        )

        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(JobFailedError) as exc_info:
                await client.ai.wait_for_2d_mockup("2d-create-job-001", poll_interval=0.0)

        assert exc_info.value.job_id == "2d-create-job-001"
        assert exc_info.value.error_code == "NOT_MOCKUPABLE"
        assert exc_info.value.reason == "The source image is not suitable for a 2D mockup"

    async def test_ai_wait_for_2d_mockup_timeout(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/jobs/2d-create-job-001").mock(
            return_value=httpx.Response(200, json=MOCK_2D_MOCKUP_JOB_QUEUED_RESPONSE)
        )

        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(JobTimeoutError) as exc_info:
                await client.ai.wait_for_2d_mockup(
                    "2d-create-job-001",
                    poll_interval=0.0,
                    timeout=0.0,
                )

        assert exc_info.value.job_id == "2d-create-job-001"

    async def test_ai_update_2d_print_areas(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.put("/api/v1/sudoai/2d-mockups/2d-mockup-001/print-areas").mock(
            return_value=httpx.Response(200, json=MOCK_2D_PRINT_AREAS_UPDATE_RESPONSE)
        )
        print_areas = [{"points": [[100, 100], [500, 100], [500, 500], [100, 500]]}]

        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.ai.update_2d_print_areas("2d-mockup-001", print_areas)

        assert json.loads(route.calls.last.request.content) == {"print_areas": print_areas}
        assert isinstance(result, TwoDPrintAreasUpdate)
        assert result.mockup_id == "2d-mockup-001"
        assert isinstance(result.print_areas[0], Quad)
        assert result.print_areas[0].print_area_id == "pa-1"

    async def test_ai_update_2d_print_areas_forwards_empty_product_surface_state(
        self, mock_api: respx.MockRouter
    ) -> None:
        route = mock_api.put("/api/v1/sudoai/2d-mockups/2d-mockup-001/print-areas").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {"mockup_id": "2d-mockup-001", "print_areas": []},
                },
            )
        )

        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.ai.update_2d_print_areas("2d-mockup-001", [])

        assert json.loads(route.calls.last.request.content) == {"print_areas": []}
        assert result.print_areas == []


# ---------------------------------------------------------------------------
# Images resource
# ---------------------------------------------------------------------------


class TestAsyncImages:
    async def test_remove_background_from_url(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/remove-background").mock(
            return_value=httpx.Response(200, json=MOCK_REMOVE_BACKGROUND_RESPONSE)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.images.remove_background(
                url="https://example.com/product-photo.jpg"
            )

        assert isinstance(result, BackgroundRemoval)
        assert result.url.endswith("cutout.png")
        assert result.width == 1200
        assert result.height == 1600
        assert result.credits_charged == 25
        assert json.loads(route.calls.last.request.content) == {
            "url": "https://example.com/product-photo.jpg"
        }

    async def test_remove_background_from_base64(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/remove-background").mock(
            return_value=httpx.Response(200, json=MOCK_REMOVE_BACKGROUND_RESPONSE)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            await client.images.remove_background(base64="aW1hZ2U=", content_type="image/jpeg")

        assert json.loads(route.calls.last.request.content) == {
            "base64": "aW1hZ2U=",
            "content_type": "image/jpeg",
        }

    async def test_remove_background_requires_exactly_one_source(
        self, mock_api: respx.MockRouter
    ) -> None:
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(ValueError, match="exactly one"):
                await client.images.remove_background()
            with pytest.raises(ValueError, match="exactly one"):
                await client.images.remove_background(
                    url="https://example.com/x.jpg", base64="eA=="
                )
        assert len(mock_api.calls) == 0

    async def test_remove_background_insufficient_credits(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/api/v1/remove-background").mock(
            return_value=httpx.Response(402, json=ERROR_402)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(InsufficientCreditsError):
                await client.images.remove_background(url="https://example.com/x.jpg")

    async def test_remove_background_invalid_image(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/api/v1/remove-background").mock(
            return_value=httpx.Response(422, json=ERROR_422_INVALID_IMAGE)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(ValidationError) as exc_info:
                await client.images.remove_background(url="https://example.com/not-an-image.txt")
            assert exc_info.value.error_code == "INVALID_IMAGE"


# ---------------------------------------------------------------------------
# Studio resource
# ---------------------------------------------------------------------------


class TestAsyncStudio:
    async def test_create_2d_session_with_origin_and_product_context(
        self, mock_api: respx.MockRouter
    ) -> None:
        mock_api.post("/api/v1/studio/create-session").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "session": "sess_test",
                    "expires_in": 1800,
                    "mockup_type": "2d",
                    "message_session_id": "22222222-2222-4222-8222-222222222222",
                    "bootstrap_secret": "secret",
                },
            )
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.studio.create_session(
                mockup_type="2d",
                session_kind="customize",
                mockup_uuid="11111111-1111-4111-8111-111111111111",
                allowed_origin="https://shop.example",
                product_id="product-1",
                variant_id="variant-2",
                action_id="add-to-cart",
                ui={"primary_action_label": "Add to cart"},
            )

        assert isinstance(result, StudioSession)
        assert result.mockup_type == "2d"
        assert json.loads(mock_api.calls[-1].request.content) == {
            "mockup_type": "2d",
            "session_kind": "customize",
            "mockup_uuid": "11111111-1111-4111-8111-111111111111",
            "allowed_origin": "https://shop.example",
            "product_id": "product-1",
            "variant_id": "variant-2",
            "ui": {"primary_action_label": "Add to cart"},
            "action_id": "add-to-cart",
        }

    async def test_consume_psd_action_without_2d_revision_fields(
        self, mock_api: respx.MockRouter
    ) -> None:
        event = StudioResultEvent(
            version=1,
            source="sudomock-studio",
            type="studio.design-submitted",
            request_id="11111111-1111-4111-8111-111111111111",
            message_session_id="22222222-2222-4222-8222-222222222222",
            payload=StudioResultPayload(
                mockup_uuid="33333333-3333-4333-8333-333333333333",
                render_uuid="44444444-4444-4444-8444-444444444444",
                action_id="add-to-cart",
            ),
        )
        action_context = {
            "product_id": "product-1",
            "variant_id": "variant-2",
        }
        mock_api.post("/api/v1/studio/actions/consume").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "replayed": False,
                    "receipt": {
                        "version": 1,
                        "request_id": event.request_id,
                        "message_session_id": event.message_session_id,
                        "type": event.type,
                        "mockup_type": "psd",
                        "session_kind": "customize",
                        "action_id": "add-to-cart",
                        "action_context": action_context,
                        "mockup_uuid": event.payload.mockup_uuid,
                        "render_uuid": event.payload.render_uuid,
                    },
                },
            )
        )

        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.studio.consume_action(
                event,
                action_context=action_context,
            )

        assert isinstance(result, StudioActionReceipt)
        payload = json.loads(mock_api.calls[-1].request.content)["payload"]
        assert payload["action_context"] == action_context
        assert set(payload) == {
            "mockup_uuid",
            "render_uuid",
            "action_id",
            "action_context",
        }


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
