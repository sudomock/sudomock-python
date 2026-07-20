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
    JobAccepted,
    Mockup,
    MockupList,
    Quad,
    Render,
    TwoDMockup,
    TwoDPrintAreasUpdate,
)

from .conftest import (
    ERROR_401,
    ERROR_402,
    ERROR_404,
    ERROR_422,
    ERROR_429,
    ERROR_500,
    MOCK_2D_MOCKUP_DELETE_RESPONSE,
    MOCK_2D_MOCKUP_GET_RESPONSE,
    MOCK_2D_MOCKUP_JOB_ACCEPTED_RESPONSE,
    MOCK_2D_MOCKUP_JOB_FAILED_RESPONSE,
    MOCK_2D_MOCKUP_JOB_QUEUED_RESPONSE,
    MOCK_2D_MOCKUP_JOB_SUCCEEDED_RESPONSE,
    MOCK_2D_MOCKUP_LIST_RESPONSE,
    MOCK_2D_PRINT_AREAS_UPDATE_RESPONSE,
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


# ---------------------------------------------------------------------------
# AI resource
# ---------------------------------------------------------------------------


class TestAI:
    def test_ai_render(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/sudoai/2d-mockup/render").mock(
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
        # 2D-render print_files have no smart_object_uuid.
        assert result.print_files[0].smart_object_uuid is None
        assert result.print_files[0].export_format == "webp"

        body = json.loads(route.calls.last.request.content)
        # Real contract: mockup_uuid + print_areas[]; the old source_url/
        # artwork_url/product_type fields must NOT be present.
        assert body["mockup_uuid"] == "2d-mockup-001"
        assert body["print_areas"][0]["uuid"] == "pa-1"
        assert "source_url" not in body
        assert "product_type" not in body

    def test_ai_render_with_options(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/sudoai/2d-mockup/render").mock(
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

    def test_ai_create(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/sudoai/2d-mockups").mock(
            return_value=httpx.Response(202, json=MOCK_2D_MOCKUP_JOB_ACCEPTED_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.ai.create(
                source_url="https://example.com/product.jpg",
                name="Product Front",
                idempotency_key="create-2d-001",
            )

        assert isinstance(result, JobAccepted)
        assert result.job_id == "2d-create-job-001"
        assert result.kind == "2d_create"
        assert result.status == "queued"
        assert result.status_url == "/api/v1/jobs/2d-create-job-001"
        assert json.loads(route.calls.last.request.content) == {
            "source_url": "https://example.com/product.jpg",
            "name": "Product Front",
        }
        assert route.calls.last.request.headers["idempotency-key"] == "create-2d-001"
        assert route.calls.last.request.headers["x-api-key"] == TEST_API_KEY

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
        detail_route = mock_api.get("/api/v1/sudoai/2d-mockup/2d-mockup-001").mock(
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

    def test_ai_wait_for_2d_mockup_rejects_wrong_job_kind(
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

        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(SudoMockError, match="expected '2d_create'"):
                client.ai.wait_for_2d_mockup("video-job-001", poll_interval=0.0)

    def test_ai_wait_for_2d_mockup_missing_mockup_uuid(
        self, mock_api: respx.MockRouter
    ) -> None:
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
        route = mock_api.put("/api/v1/sudoai/2d-mockup/2d-mockup-001/print-areas").mock(
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

    def test_ai_list_get_delete(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/sudoai/2d-mockups").mock(
            return_value=httpx.Response(200, json=MOCK_2D_MOCKUP_LIST_RESPONSE)
        )
        mock_api.get("/api/v1/sudoai/2d-mockup/2d-mockup-001").mock(
            return_value=httpx.Response(200, json=MOCK_2D_MOCKUP_GET_RESPONSE)
        )
        mock_api.delete("/api/v1/sudoai/2d-mockup/2d-mockup-001").mock(
            return_value=httpx.Response(200, json=MOCK_2D_MOCKUP_DELETE_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            listing = client.ai.list(limit=20)
            assert listing.total == 1
            assert listing.mockups[0].mockup_id == "2d-mockup-001"

            one = client.ai.get("2d-mockup-001")
            assert one.mockup_id == "2d-mockup-001"
            assert one.name == "Flat Tee Front"

            client.ai.delete("2d-mockup-001")  # should not raise


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
            assert exc_info.value.body["detail"] == "Internal server error"


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
