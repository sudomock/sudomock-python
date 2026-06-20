"""Tests for the server-async surface: is_async renders, jobs, video, psd.

NOTE: "async" here means the *server-side render queue* (``is_async=True``
-> 202 + poll), not Python ``asyncio``. These tests exercise the synchronous
:class:`SudoMock` client.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
import pytest

from sudomock import SudoMock
from sudomock.exceptions import InsufficientCreditsError, NotFoundError, ValidationError
from sudomock.models import Job, JobAccepted, Mockup, Render

from .conftest import (
    ERROR_402,
    ERROR_404,
    ERROR_422,
    MOCK_JOB_ACCEPTED_RESPONSE,
    MOCK_JOB_FAILED_RESPONSE,
    MOCK_JOB_QUEUED_RESPONSE,
    MOCK_JOB_RUNNING_RESPONSE,
    MOCK_JOB_SUCCEEDED_RESPONSE,
    MOCK_PSD_UPLOAD_ASYNC_RESPONSE,
    MOCK_PSD_UPLOAD_SYNC_RESPONSE,
    MOCK_RENDER_RESPONSE,
    MOCK_VIDEO_JOB_ACCEPTED_RESPONSE,
    TEST_API_KEY,
    TEST_BASE_URL,
)

if TYPE_CHECKING:
    import respx

_SO = [{"uuid": "so-1", "asset": {"url": "https://x.com/d.png"}}]


# ---------------------------------------------------------------------------
# is_async renders
# ---------------------------------------------------------------------------


class TestAsyncRender:
    def test_sync_default_returns_render(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/api/v1/renders").mock(
            return_value=httpx.Response(200, json=MOCK_RENDER_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.renders.create(mockup_uuid="m-1", smart_objects=_SO)
        assert isinstance(result, Render)

    def test_is_async_returns_job_accepted(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/renders").mock(
            return_value=httpx.Response(202, json=MOCK_JOB_ACCEPTED_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.renders.create(
                mockup_uuid="m-1", smart_objects=_SO, is_async=True
            )

        assert isinstance(result, JobAccepted)
        assert result.render_uuid == "job-uuid-abc123"
        assert result.status_url == "/api/v1/jobs/job-uuid-abc123"

        body = json.loads(route.calls.last.request.content)
        assert body["is_async"] is True

    def test_is_async_402(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/api/v1/renders").mock(
            return_value=httpx.Response(402, json=ERROR_402)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(InsufficientCreditsError):
                client.renders.create(
                    mockup_uuid="m-1", smart_objects=_SO, is_async=True
                )


# ---------------------------------------------------------------------------
# Jobs polling
# ---------------------------------------------------------------------------


class TestJobs:
    def test_get_queued(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/jobs/job-1").mock(
            return_value=httpx.Response(200, json=MOCK_JOB_QUEUED_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            job = client.jobs.get("job-1")
        assert isinstance(job, Job)
        assert job.status == "queued"
        assert not job.is_terminal

    def test_get_succeeded(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/jobs/job-1").mock(
            return_value=httpx.Response(200, json=MOCK_JOB_SUCCEEDED_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            job = client.jobs.get("job-1")
        assert job.succeeded
        assert job.is_terminal
        assert "render.webp" in job.url
        assert job.credits_charged == 1

    def test_get_owner_scope_404(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/jobs/not-mine").mock(
            return_value=httpx.Response(404, json=ERROR_404)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(NotFoundError):
                client.jobs.get("not-mine")

    def test_failed_url_raises(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/jobs/job-1").mock(
            return_value=httpx.Response(200, json=MOCK_JOB_FAILED_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            job = client.jobs.get("job-1")
        assert job.failed
        assert job.error == "render engine error"
        with pytest.raises(ValueError, match="no result_url"):
            _ = job.url

    def test_wait_polls_until_terminal(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.get("/api/v1/jobs/job-1")
        route.side_effect = [
            httpx.Response(200, json=MOCK_JOB_QUEUED_RESPONSE),
            httpx.Response(200, json=MOCK_JOB_RUNNING_RESPONSE),
            httpx.Response(200, json=MOCK_JOB_SUCCEEDED_RESPONSE),
        ]
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            job = client.jobs.wait("job-1", poll_interval=0.0)
        assert job.succeeded
        assert len(route.calls) == 3

    def test_wait_timeout(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/jobs/job-1").mock(
            return_value=httpx.Response(200, json=MOCK_JOB_QUEUED_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(TimeoutError, match="did not finish"):
                client.jobs.wait("job-1", poll_interval=0.0, timeout=0.0)


# ---------------------------------------------------------------------------
# Video
# ---------------------------------------------------------------------------


class TestVideo:
    def test_create_video_returns_job(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/renders/video").mock(
            return_value=httpx.Response(202, json=MOCK_VIDEO_JOB_ACCEPTED_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.renders.create_video(
                mockup_uuid="m-1",
                smart_objects=_SO,
                duration_seconds=5,
                audio=True,
                advanced_model="veo-3.1-fast",
            )

        assert isinstance(result, JobAccepted)
        assert result.render_uuid == "video-job-xyz789"

        body = json.loads(route.calls.last.request.content)
        assert body["video"]["duration_seconds"] == 5
        assert body["video"]["audio"] is True
        assert body["video"]["advanced_model"] == "veo-3.1-fast"

    def test_create_video_no_model_omits_key(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/renders/video").mock(
            return_value=httpx.Response(202, json=MOCK_VIDEO_JOB_ACCEPTED_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            client.renders.create_video(
                mockup_uuid="m-1", smart_objects=_SO, duration_seconds=4
            )
        body = json.loads(route.calls.last.request.content)
        assert "advanced_model" not in body["video"]
        assert body["video"]["audio"] is False

    def test_create_video_bad_duration_422(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/api/v1/renders/video").mock(
            return_value=httpx.Response(422, json=ERROR_422)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(ValidationError):
                client.renders.create_video(
                    mockup_uuid="m-1", smart_objects=_SO, duration_seconds=999
                )

    def test_create_video_402(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/api/v1/renders/video").mock(
            return_value=httpx.Response(402, json=ERROR_402)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(InsufficientCreditsError):
                client.renders.create_video(
                    mockup_uuid="m-1", smart_objects=_SO, duration_seconds=5
                )


# ---------------------------------------------------------------------------
# PSD upload
# ---------------------------------------------------------------------------


class TestPsdUpload:
    def test_upload_sync_returns_mockup(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/api/v1/psd/upload").mock(
            return_value=httpx.Response(200, json=MOCK_PSD_UPLOAD_SYNC_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.psd.upload(url="https://x.com/file.psd", name="My PSD")
        assert isinstance(result, Mockup)
        assert result.name == "Black T-Shirt Front"

    def test_upload_async_returns_job(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/psd/upload").mock(
            return_value=httpx.Response(202, json=MOCK_PSD_UPLOAD_ASYNC_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.psd.upload(url="https://x.com/file.psd", is_async=True)
        assert isinstance(result, JobAccepted)
        assert result.render_uuid == "upload-job-001"
        body = json.loads(route.calls.last.request.content)
        assert body["is_async"] is True
