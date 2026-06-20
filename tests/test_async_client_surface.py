"""Tests for the new surface on the asyncio AsyncSudoMock client.

These cover the server-async render queue (is_async / jobs / video / psd)
and webhook management, driven through the asyncio I/O client.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
import pytest

from sudomock import AsyncSudoMock
from sudomock.exceptions import InsufficientCreditsError, NotFoundError
from sudomock.models import Job, JobAccepted, Mockup, Render, WebhookEndpoint

from .conftest import (
    ERROR_402,
    ERROR_404,
    MOCK_JOB_ACCEPTED_RESPONSE,
    MOCK_JOB_QUEUED_RESPONSE,
    MOCK_JOB_RUNNING_RESPONSE,
    MOCK_JOB_SUCCEEDED_RESPONSE,
    MOCK_PSD_UPLOAD_ASYNC_RESPONSE,
    MOCK_PSD_UPLOAD_SYNC_RESPONSE,
    MOCK_RENDER_RESPONSE,
    MOCK_VIDEO_JOB_ACCEPTED_RESPONSE,
    MOCK_WEBHOOK_CREATE_RESPONSE,
    TEST_API_KEY,
    TEST_BASE_URL,
)

if TYPE_CHECKING:
    import respx

_SO = [{"uuid": "so-1", "asset": {"url": "https://x.com/d.png"}}]


class TestAsyncRenderSurface:
    async def test_sync_render(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/api/v1/renders").mock(
            return_value=httpx.Response(200, json=MOCK_RENDER_RESPONSE)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.renders.create(mockup_uuid="m-1", smart_objects=_SO)
        assert isinstance(result, Render)

    async def test_is_async_render(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/renders").mock(
            return_value=httpx.Response(202, json=MOCK_JOB_ACCEPTED_RESPONSE)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.renders.create(
                mockup_uuid="m-1", smart_objects=_SO, is_async=True
            )
        assert isinstance(result, JobAccepted)
        body = json.loads(route.calls.last.request.content)
        assert body["is_async"] is True

    async def test_is_async_402(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/api/v1/renders").mock(
            return_value=httpx.Response(402, json=ERROR_402)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(InsufficientCreditsError):
                await client.renders.create(
                    mockup_uuid="m-1", smart_objects=_SO, is_async=True
                )


class TestAsyncJobs:
    async def test_get(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/jobs/job-1").mock(
            return_value=httpx.Response(200, json=MOCK_JOB_SUCCEEDED_RESPONSE)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            job = await client.jobs.get("job-1")
        assert isinstance(job, Job)
        assert job.succeeded

    async def test_get_404(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/jobs/x").mock(
            return_value=httpx.Response(404, json=ERROR_404)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(NotFoundError):
                await client.jobs.get("x")

    async def test_wait_polls(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.get("/api/v1/jobs/job-1")
        route.side_effect = [
            httpx.Response(200, json=MOCK_JOB_QUEUED_RESPONSE),
            httpx.Response(200, json=MOCK_JOB_RUNNING_RESPONSE),
            httpx.Response(200, json=MOCK_JOB_SUCCEEDED_RESPONSE),
        ]
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            job = await client.jobs.wait("job-1", poll_interval=0.0)
        assert job.succeeded
        assert len(route.calls) == 3

    async def test_wait_timeout(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/jobs/job-1").mock(
            return_value=httpx.Response(200, json=MOCK_JOB_QUEUED_RESPONSE)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(TimeoutError):
                await client.jobs.wait("job-1", poll_interval=0.0, timeout=0.0)


class TestAsyncVideo:
    async def test_create_video(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/renders/video").mock(
            return_value=httpx.Response(202, json=MOCK_VIDEO_JOB_ACCEPTED_RESPONSE)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.renders.create_video(
                mockup_uuid="m-1", smart_objects=_SO, duration_seconds=5
            )
        assert isinstance(result, JobAccepted)
        body = json.loads(route.calls.last.request.content)
        assert body["video"]["duration_seconds"] == 5


class TestAsyncPsd:
    async def test_upload_sync(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/api/v1/psd/upload").mock(
            return_value=httpx.Response(200, json=MOCK_PSD_UPLOAD_SYNC_RESPONSE)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.psd.upload(url="https://x.com/f.psd")
        assert isinstance(result, Mockup)

    async def test_upload_async(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/api/v1/psd/upload").mock(
            return_value=httpx.Response(202, json=MOCK_PSD_UPLOAD_ASYNC_RESPONSE)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.psd.upload(url="https://x.com/f.psd", is_async=True)
        assert isinstance(result, JobAccepted)


class TestAsyncWebhooks:
    async def test_create(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/api/v1/webhook-endpoints").mock(
            return_value=httpx.Response(201, json=MOCK_WEBHOOK_CREATE_RESPONSE)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = await client.webhook_endpoints.create(
                url="https://x.com/wh", events=["render.succeeded"]
            )
        assert isinstance(result, WebhookEndpoint)
        assert result.secret == "whsec_testsecret123"

    async def test_rotate_and_replay(self, mock_api: respx.MockRouter) -> None:
        rotate_body = {"success": True, "data": {"secret": "whsec_new"}}
        mock_api.post("/api/v1/webhook-endpoints/wh-1/rotate-secret").mock(
            return_value=httpx.Response(200, json=rotate_body)
        )
        route = mock_api.post(
            "/api/v1/webhook-endpoints/wh-1/deliveries/dlv-1/replay"
        ).mock(return_value=httpx.Response(202))
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            secret = await client.webhook_endpoints.rotate_secret("wh-1")
            await client.webhook_endpoints.replay_delivery("wh-1", "dlv-1")
        assert secret.secret == "whsec_new"
        assert len(route.calls) == 1
