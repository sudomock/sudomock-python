"""Tests for the synchronous SudoMock client."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import UUID

import httpx
import pytest

from sudomock import SudoMock
from sudomock.exceptions import (
    AuthenticationError,
    InsufficientCreditsError,
    JobFailedError,
    JobTimeoutError,
    NotFoundError,
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
    ERROR_404,
    ERROR_422,
    ERROR_422_INVALID_IMAGE,
    ERROR_429,
    ERROR_500,
    ERROR_502_BACKGROUND_REMOVAL,
    MOCK_2D_MOCKUP_DELETE_RESPONSE,
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


class TestClientInit:
    def test_api_key_from_constructor(self) -> None:
        client = SudoMock(api_key="sm_explicit")
        assert client._api_key == "sm_explicit"
        client.close()

    def test_api_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SUDOMOCK_API_KEY", "sm_from_env")
        client = SudoMock()
        assert client._api_key == "sm_from_env"
        client.close()

    def test_constructor_overrides_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SUDOMOCK_API_KEY", "sm_env")
        client = SudoMock(api_key="sm_explicit")
        assert client._api_key == "sm_explicit"
        client.close()

    def test_missing_api_key_raises(self) -> None:
        with pytest.raises(SudoMockError, match="API key"):
            SudoMock()

    def test_custom_base_url(self) -> None:
        client = SudoMock(api_key="sm_x", base_url="https://custom.api.com")
        assert client._base_url == "https://custom.api.com"
        client.close()

    def test_custom_timeout(self) -> None:
        client = SudoMock(api_key="sm_x", timeout=60.0)
        assert client._timeout == 60.0
        client.close()

    def test_context_manager(self) -> None:
        with SudoMock(api_key="sm_x") as client:
            assert client._api_key == "sm_x"


# ---------------------------------------------------------------------------
# Mockups resource
# ---------------------------------------------------------------------------


class TestMockupsList:
    def test_list_mockups(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/mockups").mock(
            return_value=httpx.Response(200, json=MOCK_MOCKUP_LIST_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.mockups.list()

        assert isinstance(result, MockupList)
        assert result.total == 1
        assert len(result.mockups) == 1
        assert result.mockups[0].uuid == MOCK_MOCKUP["uuid"]

    def test_list_with_params(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.get("/api/v1/mockups").mock(
            return_value=httpx.Response(200, json=MOCK_MOCKUP_LIST_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            client.mockups.list(limit=10, offset=5)

        request = route.calls.last.request
        assert request.url.params["limit"] == "10"
        assert request.url.params["offset"] == "5"

    def test_list_sends_api_key_header(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.get("/api/v1/mockups").mock(
            return_value=httpx.Response(200, json=MOCK_MOCKUP_LIST_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            client.mockups.list()

        request = route.calls.last.request
        assert request.headers["x-api-key"] == TEST_API_KEY


class TestMockupsGet:
    def test_get_mockup(self, mock_api: respx.MockRouter) -> None:
        uuid = MOCK_MOCKUP["uuid"]
        mock_api.get(f"/api/v1/mockups/{uuid}").mock(
            return_value=httpx.Response(200, json=MOCK_MOCKUP_GET_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.mockups.get(uuid)

        assert isinstance(result, Mockup)
        assert result.uuid == uuid
        assert result.name == "Black T-Shirt Front"
        assert len(result.smart_objects) == 1
        assert result.text_layers[0].font_postscript_name == "Montserrat-Bold"

    def test_get_not_found(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/mockups/nonexistent").mock(
            return_value=httpx.Response(404, json=ERROR_404)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(NotFoundError):
                client.mockups.get("nonexistent")


class TestMockupsDelete:
    def test_delete_mockup(self, mock_api: respx.MockRouter) -> None:
        uuid = "some-uuid"
        mock_api.delete(f"/api/v1/mockups/{uuid}").mock(return_value=httpx.Response(204))
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            # Should not raise
            client.mockups.delete(uuid)


# ---------------------------------------------------------------------------
# Renders resource
# ---------------------------------------------------------------------------


class TestRenders:
    def test_create_render(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/api/v1/renders").mock(
            return_value=httpx.Response(200, json=MOCK_RENDER_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.renders.create(
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
        assert len(result.print_files) == 1

    def test_create_render_with_options(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/renders").mock(
            return_value=httpx.Response(200, json=MOCK_RENDER_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            client.renders.create(
                mockup_uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                smart_objects=[
                    {
                        "uuid": "11111111-2222-3333-4444-555555555555",
                        "asset": {"url": "https://example.com/design.png"},
                    }
                ],
                export_options={"image_format": "png", "quality": 100},
                export_label="my-render",
            )

        body = json.loads(route.calls.last.request.content)
        assert body["export_options"]["image_format"] == "png"
        assert body["export_label"] == "my-render"

    def test_create_render_with_remove_background_asset(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/renders").mock(
            return_value=httpx.Response(200, json=MOCK_RENDER_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            client.renders.create(
                mockup_uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                smart_objects=[
                    {
                        "uuid": "11111111-2222-3333-4444-555555555555",
                        "asset": {
                            "url": "https://example.com/photo.jpg",
                            "remove_background": True,
                        },
                    }
                ],
            )

        body = json.loads(route.calls.last.request.content)
        assert body["smart_objects"][0]["asset"]["remove_background"] is True

    def test_create_text_only_render(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/renders").mock(
            return_value=httpx.Response(200, json=MOCK_TEXT_RENDER_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.renders.create(
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

    def test_render_uses_longer_timeout(self, mock_api: respx.MockRouter) -> None:
        """Render requests should use the render_timeout, not the default."""
        mock_api.post("/api/v1/renders").mock(
            return_value=httpx.Response(200, json=MOCK_RENDER_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL, render_timeout=180.0) as client:
            assert client._render_timeout == 180.0
            client.renders.create(
                mockup_uuid="test-uuid",
                smart_objects=[{"uuid": "so-1", "asset": {"url": "https://x.com/d.png"}}],
            )

    def test_insufficient_credits(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/api/v1/renders").mock(return_value=httpx.Response(402, json=ERROR_402))
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(InsufficientCreditsError) as exc_info:
                client.renders.create(
                    mockup_uuid="test-uuid",
                    smart_objects=[{"uuid": "so-1", "asset": {"url": "https://x.com/d.png"}}],
                )
            assert exc_info.value.credits_reset_at == "2026-02-01T00:00:00Z"
            assert exc_info.value.error_code == "credits_exhausted"


# ---------------------------------------------------------------------------
# AI resource
# ---------------------------------------------------------------------------


class TestAI:
    def test_ai_render(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/sudoai/2d-mockups/2d-mockup-001/render").mock(
            return_value=httpx.Response(200, json=MOCK_AI_RENDER_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.ai.render(
                mockup_uuid="2d-mockup-001",
                print_areas=[
                    {
                        "uuid": "pa-1",
                        "artwork_url": "https://example.com/design.png",
                    }
                ],
            )

        assert isinstance(result, AIRender)
        assert "ai-renders" in result.url
        assert result.render_uuid == "render-2d-001"
        # 2D-render print_files have no smart_object_uuid.
        assert result.print_files[0].smart_object_uuid is None
        assert result.print_files[0].export_format == "webp"

        body = json.loads(route.calls.last.request.content)
        # Real contract: mockup id is in the PATH, body is print_areas[] only;
        # the old mockup_uuid/source_url/product_type fields must NOT be present.
        assert "mockup_uuid" not in body
        assert body["print_areas"][0]["uuid"] == "pa-1"
        assert "source_url" not in body
        assert "product_type" not in body

    def test_ai_render_with_options(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/sudoai/2d-mockups/2d-mockup-001/render").mock(
            return_value=httpx.Response(200, json=MOCK_AI_RENDER_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            client.ai.render(
                mockup_uuid="2d-mockup-001",
                print_areas=[{"uuid": "pa-1", "color": "#FF0000"}],
                export_options={"image_format": "png"},
            )

        body = json.loads(route.calls.last.request.content)
        assert body["print_areas"][0]["color"] == "#FF0000"
        assert body["export_options"]["image_format"] == "png"

    def test_ai_render_product_surface_uses_surface_uuid(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/sudoai/2d-mockups/2d-mockup-001/render").mock(
            return_value=httpx.Response(200, json=MOCK_AI_RENDER_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            client.ai.render(
                mockup_uuid="2d-mockup-001",
                print_areas=[{"surface_uuid": "surface-1", "color": "#FF0000"}],
            )

        surface = json.loads(route.calls.last.request.content)["print_areas"][0]
        assert surface == {"surface_uuid": "surface-1", "color": "#FF0000"}

    def test_ai_render_with_remove_background(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/sudoai/2d-mockups/2d-mockup-001/render").mock(
            return_value=httpx.Response(200, json=MOCK_AI_RENDER_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            client.ai.render(
                mockup_uuid="2d-mockup-001",
                print_areas=[
                    {
                        "uuid": "pa-1",
                        "artwork_url": "https://example.com/photo.jpg",
                        "remove_background": True,
                    }
                ],
            )

        body = json.loads(route.calls.last.request.content)
        assert body["print_areas"][0]["remove_background"] is True

    def test_ai_render_async(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/sudoai/2d-mockups/2d-mockup-001/render").mock(
            return_value=httpx.Response(202, json=MOCK_AI_RENDER_JOB_ACCEPTED_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.ai.render(
                mockup_uuid="2d-mockup-001",
                print_areas=[{"uuid": "pa-1", "artwork_url": "https://example.com/design.png"}],
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
        # Path-param contract preserved: mockup id is NOT in the body.
        assert "mockup_uuid" not in body

    def test_ai_create(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/sudoai/2d-mockups").mock(
            return_value=httpx.Response(201, json=MOCK_2D_MOCKUP_GET_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.ai.create(
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

    def test_ai_create_async(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/sudoai/2d-mockups").mock(
            return_value=httpx.Response(202, json=MOCK_2D_MOCKUP_JOB_ACCEPTED_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.ai.create(
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

    def test_ai_create_base64_generates_stable_idempotency_key(
        self, mock_api: respx.MockRouter
    ) -> None:
        route = mock_api.post("/api/v1/sudoai/2d-mockups")
        route.side_effect = [
            httpx.Response(500, json=ERROR_500),
            httpx.Response(202, json=MOCK_2D_MOCKUP_JOB_ACCEPTED_RESPONSE),
        ]

        with SudoMock(
            api_key=TEST_API_KEY,
            base_url=TEST_BASE_URL,
            max_retries=2,
        ) as client:
            client.ai.create(source_base64="aW1hZ2U=")

        assert json.loads(route.calls.last.request.content) == {"source_base64": "aW1hZ2U="}
        keys = [call.request.headers["idempotency-key"] for call in route.calls]
        assert len(keys) == 2
        assert keys[0] == keys[1]
        assert UUID(keys[0]).version == 4

    def test_ai_create_insufficient_credits(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/sudoai/2d-mockups").mock(
            return_value=httpx.Response(402, json=ERROR_402)
        )

        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(InsufficientCreditsError):
                client.ai.create(source_url="https://example.com/product.jpg")

        assert len(route.calls) == 1

    def test_ai_create_requires_exactly_one_source(self, mock_api: respx.MockRouter) -> None:
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(ValueError, match="exactly one"):
                client.ai.create()
            with pytest.raises(ValueError, match="exactly one"):
                client.ai.create(source_url="")
            with pytest.raises(ValueError, match="exactly one"):
                client.ai.create(
                    source_url="https://example.com/product.jpg",
                    source_base64="aW1hZ2U=",
                )

        assert len(mock_api.calls) == 0

    def test_ai_wait_for_2d_mockup_success(self, mock_api: respx.MockRouter) -> None:
        job_route = mock_api.get("/api/v1/jobs/2d-create-job-001")
        job_route.side_effect = [
            httpx.Response(200, json=MOCK_2D_MOCKUP_JOB_QUEUED_RESPONSE),
            httpx.Response(200, json=MOCK_2D_MOCKUP_JOB_SUCCEEDED_RESPONSE),
        ]
        detail_route = mock_api.get("/api/v1/sudoai/2d-mockups/2d-mockup-001").mock(
            return_value=httpx.Response(200, json=MOCK_2D_MOCKUP_GET_RESPONSE)
        )

        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.ai.wait_for_2d_mockup(
                "2d-create-job-001",
                poll_interval=0.0,
            )

        assert isinstance(result, TwoDMockup)
        assert result.mockup_id == "2d-mockup-001"
        assert result.name == "Flat Tee Front"
        assert result.quads[0].print_area_id == "pa-1"
        assert len(job_route.calls) == 2
        assert len(detail_route.calls) == 1

    def test_ai_wait_for_2d_mockup_rejects_wrong_job_kind(self, mock_api: respx.MockRouter) -> None:
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

        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(SudoMockError, match="expected '2d_create'"):
                client.ai.wait_for_2d_mockup("video-job-001", poll_interval=0.0)

    def test_ai_wait_for_2d_mockup_missing_mockup_uuid(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/jobs/2d-create-job-001").mock(
            return_value=httpx.Response(
                200,
                json={**MOCK_2D_MOCKUP_JOB_SUCCEEDED_RESPONSE, "mockup_uuid": ""},
            )
        )

        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(SudoMockError, match="without a mockup UUID"):
                client.ai.wait_for_2d_mockup("2d-create-job-001", poll_interval=0.0)

    def test_ai_wait_for_2d_mockup_failure(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/jobs/2d-create-job-001").mock(
            return_value=httpx.Response(200, json=MOCK_2D_MOCKUP_JOB_FAILED_RESPONSE)
        )

        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(JobFailedError) as exc_info:
                client.ai.wait_for_2d_mockup("2d-create-job-001", poll_interval=0.0)

        assert exc_info.value.job_id == "2d-create-job-001"
        assert exc_info.value.error_code == "NOT_MOCKUPABLE"
        assert exc_info.value.reason == "The source image is not suitable for a 2D mockup"

    def test_ai_wait_for_2d_mockup_timeout(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/jobs/2d-create-job-001").mock(
            return_value=httpx.Response(200, json=MOCK_2D_MOCKUP_JOB_QUEUED_RESPONSE)
        )

        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(JobTimeoutError) as exc_info:
                client.ai.wait_for_2d_mockup(
                    "2d-create-job-001",
                    poll_interval=0.0,
                    timeout=0.0,
                )

        assert exc_info.value.job_id == "2d-create-job-001"

    def test_ai_update_2d_print_areas(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.put("/api/v1/sudoai/2d-mockups/2d-mockup-001/print-areas").mock(
            return_value=httpx.Response(200, json=MOCK_2D_PRINT_AREAS_UPDATE_RESPONSE)
        )
        print_areas = [{"points": [[100, 100], [500, 100], [500, 500], [100, 500]]}]

        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.ai.update_2d_print_areas("2d-mockup-001", print_areas)

        assert json.loads(route.calls.last.request.content) == {"print_areas": print_areas}
        assert isinstance(result, TwoDPrintAreasUpdate)
        assert result.mockup_id == "2d-mockup-001"
        assert isinstance(result.print_areas[0], Quad)
        assert result.print_areas[0].print_area_id == "pa-1"

    def test_ai_update_2d_print_areas_forwards_empty_product_surface_state(
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

        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.ai.update_2d_print_areas("2d-mockup-001", [])

        assert json.loads(route.calls.last.request.content) == {"print_areas": []}
        assert result.print_areas == []

    def test_ai_list_get_delete(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/sudoai/2d-mockups").mock(
            return_value=httpx.Response(200, json=MOCK_2D_MOCKUP_LIST_RESPONSE)
        )
        mock_api.get("/api/v1/sudoai/2d-mockups/2d-mockup-001").mock(
            return_value=httpx.Response(200, json=MOCK_2D_MOCKUP_GET_RESPONSE)
        )
        mock_api.delete("/api/v1/sudoai/2d-mockups/2d-mockup-001").mock(
            return_value=httpx.Response(200, json=MOCK_2D_MOCKUP_DELETE_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            listing = client.ai.list(limit=20, customizable_only=True)
            assert listing.total == 1
            assert listing.mockups[0].mockup_id == "2d-mockup-001"
            assert listing.mockups[0].customizable is True
            assert listing.mockups[0].print_areas[0].print_area_id == "pa-1"
            assert listing.mockups[0].surfaces[0].surface_uuid == "surface-1"

            one = client.ai.get("2d-mockup-001")
            assert one.mockup_id == "2d-mockup-001"
            assert one.name == "Flat Tee Front"
            assert one.customizable is True
            assert one.surfaces[0].model_dump() == {
                "surface_uuid": "surface-1",
                "coverage": "full",
            }

            client.ai.delete("2d-mockup-001")  # should not raise

        assert mock_api.calls[0].request.url.params["customizable_only"] == "true"


# ---------------------------------------------------------------------------
# Images resource
# ---------------------------------------------------------------------------


class TestImages:
    def test_remove_background_from_url(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/remove-background").mock(
            return_value=httpx.Response(200, json=MOCK_REMOVE_BACKGROUND_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.images.remove_background(url="https://example.com/product-photo.jpg")

        assert isinstance(result, BackgroundRemoval)
        assert result.url.endswith("cutout.png")
        assert result.width == 1200
        assert result.height == 1600
        assert result.credits_charged == 25
        assert json.loads(route.calls.last.request.content) == {
            "url": "https://example.com/product-photo.jpg"
        }

    def test_remove_background_from_base64(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/remove-background").mock(
            return_value=httpx.Response(200, json=MOCK_REMOVE_BACKGROUND_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            client.images.remove_background(base64="aW1hZ2U=", content_type="image/jpeg")

        assert json.loads(route.calls.last.request.content) == {
            "base64": "aW1hZ2U=",
            "content_type": "image/jpeg",
        }

    def test_remove_background_requires_exactly_one_source(
        self, mock_api: respx.MockRouter
    ) -> None:
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(ValueError, match="exactly one"):
                client.images.remove_background()
            with pytest.raises(ValueError, match="exactly one"):
                client.images.remove_background(url="https://example.com/x.jpg", base64="eA==")
        assert len(mock_api.calls) == 0

    def test_remove_background_insufficient_credits(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/api/v1/remove-background").mock(
            return_value=httpx.Response(402, json=ERROR_402)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(InsufficientCreditsError):
                client.images.remove_background(url="https://example.com/x.jpg")

    def test_remove_background_invalid_image(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/api/v1/remove-background").mock(
            return_value=httpx.Response(422, json=ERROR_422_INVALID_IMAGE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(ValidationError) as exc_info:
                client.images.remove_background(url="https://example.com/not-an-image.txt")
            assert exc_info.value.error_code == "INVALID_IMAGE"

    def test_remove_background_processing_failure_refunds(self, mock_api: respx.MockRouter) -> None:
        """A 502 surfaces the failure code; the API refunds the credits."""
        mock_api.post("/api/v1/remove-background").mock(
            return_value=httpx.Response(502, json=ERROR_502_BACKGROUND_REMOVAL)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL, max_retries=1) as client:
            with pytest.raises(ServerError) as exc_info:
                client.images.remove_background(url="https://example.com/product.jpg")
            assert exc_info.value.error_code == "BACKGROUND_REMOVAL_FAILED"


# ---------------------------------------------------------------------------
# Studio resource
# ---------------------------------------------------------------------------


class TestStudio:
    def test_create_psd_session_with_origin_and_product_context(
        self, mock_api: respx.MockRouter
    ) -> None:
        route = mock_api.post("/api/v1/studio/create-session").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "session": "sess_test",
                    "expires_in": 900,
                    "mockup_type": "psd",
                    "message_session_id": "11111111-1111-4111-8111-111111111111",
                    "bootstrap_secret": "secret",
                },
            )
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.studio.create_session(
                mockup_type="psd",
                session_kind="customize",
                mockup_uuid="22222222-2222-4222-8222-222222222222",
                allowed_origin="https://shop.example",
                product_id="product-1",
                variant_id="variant-2",
                action_id="add-to-cart",
            )

        assert isinstance(result, StudioSession)
        assert result.message_session_id == "11111111-1111-4111-8111-111111111111"
        assert result.bootstrap_secret == "secret"
        assert json.loads(route.calls[0].request.content) == {
            "mockup_type": "psd",
            "session_kind": "customize",
            "mockup_uuid": "22222222-2222-4222-8222-222222222222",
            "allowed_origin": "https://shop.example",
            "product_id": "product-1",
            "variant_id": "variant-2",
            "action_id": "add-to-cart",
        }

    def test_consume_action_sends_only_the_server_confirmation_envelope(
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
            "shop": "shop.example",
            "product_id": "product-1",
            "variant_id": "variant-2",
        }
        route = mock_api.post("/api/v1/studio/actions/consume").mock(
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
                        "mockup_type": "2d",
                        "session_kind": "customize",
                        "action_id": "add-to-cart",
                        "action_context": action_context,
                        "mockup_uuid": event.payload.mockup_uuid,
                        "render_uuid": event.payload.render_uuid,
                    },
                },
            )
        )

        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.studio.consume_action(
                event,
                action_context=action_context,
            )

        assert isinstance(result, StudioActionReceipt)
        assert result.model_dump(mode="json") == {
            "success": True,
            "replayed": False,
            "receipt": {
                "version": 1,
                "request_id": event.request_id,
                "message_session_id": event.message_session_id,
                "type": event.type,
                "mockup_type": "2d",
                "session_kind": "customize",
                "action_id": "add-to-cart",
                "action_context": action_context,
                "mockup_uuid": event.payload.mockup_uuid,
                "render_uuid": event.payload.render_uuid,
            },
        }
        assert json.loads(route.calls[0].request.content) == {
            "version": 1,
            "request_id": event.request_id,
            "message_session_id": event.message_session_id,
            "type": event.type,
            "payload": {
                **event.payload.model_dump(),
                "action_context": action_context,
            },
        }


# ---------------------------------------------------------------------------
# Account resource
# ---------------------------------------------------------------------------


class TestAccount:
    def test_get_account(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/me").mock(return_value=httpx.Response(200, json=MOCK_ME_RESPONSE))
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.account.get()

        assert isinstance(result, AccountInfo)
        assert result.account.email == "dev@example.com"
        assert result.subscription.plan == "pro"
        assert result.usage.credits_remaining == 37153
        assert result.api_key.total_requests == 847293


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_401_raises_auth_error(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/mockups").mock(return_value=httpx.Response(401, json=ERROR_401))
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(AuthenticationError) as exc_info:
                client.mockups.list()
            assert exc_info.value.status_code == 401

    def test_402_raises_credit_error(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/mockups").mock(return_value=httpx.Response(402, json=ERROR_402))
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(InsufficientCreditsError):
                client.mockups.list()

    def test_404_raises_not_found(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/mockups/missing").mock(
            return_value=httpx.Response(404, json=ERROR_404)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(NotFoundError):
                client.mockups.get("missing")

    def test_422_raises_validation_error(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/api/v1/renders").mock(return_value=httpx.Response(422, json=ERROR_422))
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(ValidationError):
                client.renders.create(
                    mockup_uuid="bad",
                    smart_objects=[],
                )

    def test_429_raises_rate_limit_error(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/mockups").mock(return_value=httpx.Response(429, json=ERROR_429))
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(RateLimitError) as exc_info:
                client.mockups.list()
            assert exc_info.value.retry_after == 30

    def test_500_raises_server_error(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/mockups").mock(return_value=httpx.Response(500, json=ERROR_500))
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(ServerError) as exc_info:
                client.mockups.list()
            assert exc_info.value.status_code == 500

    def test_all_errors_inherit_base(self) -> None:
        """All error types should be catchable via SudoMockError."""
        for exc_cls in (
            AuthenticationError,
            InsufficientCreditsError,
            JobFailedError,
            JobTimeoutError,
            NotFoundError,
            ValidationError,
            RateLimitError,
            ServerError,
        ):
            assert issubclass(exc_cls, SudoMockError)

    def test_error_contains_body(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/mockups").mock(return_value=httpx.Response(500, json=ERROR_500))
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(ServerError) as exc_info:
                client.mockups.list()
            assert exc_info.value.body is not None
            assert (
                exc_info.value.body["detail"]
                == "SudoMock could not complete the request. Retry shortly."
            )


# ---------------------------------------------------------------------------
# Retry behavior
# ---------------------------------------------------------------------------


class TestRetry:
    def test_retries_on_500(self, mock_api: respx.MockRouter) -> None:
        """Server errors should be retried (up to max_retries)."""
        route = mock_api.get("/api/v1/mockups")
        route.side_effect = [
            httpx.Response(500, json=ERROR_500),
            httpx.Response(500, json=ERROR_500),
            httpx.Response(200, json=MOCK_MOCKUP_LIST_RESPONSE),
        ]
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL, max_retries=3) as client:
            result = client.mockups.list()

        assert result.total == 1
        assert len(route.calls) == 3

    def test_retries_on_429(self, mock_api: respx.MockRouter) -> None:
        """Rate limit errors should be retried."""
        route = mock_api.get("/api/v1/mockups")
        route.side_effect = [
            httpx.Response(429, json=ERROR_429),
            httpx.Response(200, json=MOCK_MOCKUP_LIST_RESPONSE),
        ]
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL, max_retries=2) as client:
            result = client.mockups.list()

        assert result.total == 1

    def test_no_retry_on_4xx(self, mock_api: respx.MockRouter) -> None:
        """Client errors (except 429) should NOT be retried."""
        route = mock_api.get("/api/v1/mockups")
        route.mock(return_value=httpx.Response(401, json=ERROR_401))
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL, max_retries=3) as client:
            with pytest.raises(AuthenticationError):
                client.mockups.list()

        assert len(route.calls) == 1

    def test_retries_exhausted(self, mock_api: respx.MockRouter) -> None:
        """After all retries exhausted, the last error should be raised."""
        route = mock_api.get("/api/v1/mockups")
        route.side_effect = [
            httpx.Response(500, json=ERROR_500),
            httpx.Response(500, json=ERROR_500),
            httpx.Response(500, json=ERROR_500),
        ]
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL, max_retries=3) as client:
            with pytest.raises(ServerError):
                client.mockups.list()


# ---------------------------------------------------------------------------
# User-Agent header
# ---------------------------------------------------------------------------


class TestUserAgent:
    def test_user_agent_header(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.get("/api/v1/mockups").mock(
            return_value=httpx.Response(200, json=MOCK_MOCKUP_LIST_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            client.mockups.list()

        ua = route.calls.last.request.headers["user-agent"]
        assert ua.startswith("sudomock-python/")
