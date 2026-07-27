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
from sudomock.models import Job, JobAccepted, JobList, Mockup, PlanList, Render

from .conftest import (
    ERROR_402,
    ERROR_404,
    ERROR_422,
    MOCK_JOB_ACCEPTED_RESPONSE,
    MOCK_JOB_FAILED_RESPONSE,
    MOCK_JOB_QUEUED_RESPONSE,
    MOCK_JOB_RUNNING_RESPONSE,
    MOCK_JOB_SUCCEEDED_RESPONSE,
    MOCK_JOBS_LIST_RESPONSE,
    MOCK_MOCKUP,
    MOCK_MOCKUP_GET_RESPONSE,
    MOCK_PLANS_RESPONSE,
    MOCK_PSD_UPLOAD_ASYNC_RESPONSE,
    MOCK_PSD_UPLOAD_SYNC_RESPONSE,
    MOCK_RENDER_RESPONSE,
    MOCK_VIDEO_JOB_ACCEPTED_RESPONSE,
    MOCK_WEBHOOK_CREATE_RESPONSE,
    MOCK_WEBHOOK_DELIVERIES_RESPONSE,
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
            result = client.renders.create(mockup_uuid="m-1", smart_objects=_SO, is_async=True)

        assert isinstance(result, JobAccepted)
        assert result.job_id == "job-uuid-abc123"
        assert result.status_url == "/api/v1/jobs/job-uuid-abc123"

        body = json.loads(route.calls.last.request.content)
        assert body["is_async"] is True

    def test_is_async_402(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/api/v1/renders").mock(return_value=httpx.Response(402, json=ERROR_402))
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(InsufficientCreditsError):
                client.renders.create(mockup_uuid="m-1", smart_objects=_SO, is_async=True)


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
        mock_api.get("/api/v1/jobs/not-mine").mock(return_value=httpx.Response(404, json=ERROR_404))
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
        assert job.error == "Processing failed. Retry or contact support with the job ID."
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
            )

        assert isinstance(result, JobAccepted)
        assert result.job_id == "video-job-xyz789"

        body = json.loads(route.calls.last.request.content)
        assert body["video"]["duration_seconds"] == 5
        assert body["video"]["audio"] is True

    def test_create_video_uses_only_public_options(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/renders/video").mock(
            return_value=httpx.Response(202, json=MOCK_VIDEO_JOB_ACCEPTED_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            client.renders.create_video(
                mockup_uuid="m-1",
                smart_objects=_SO,
                duration_seconds=4,
                webhook={
                    "url": "https://example.com/hook",
                    "private_option": "discarded",
                },
            )
        body = json.loads(route.calls.last.request.content)
        assert body["video"] == {"duration_seconds": 4, "audio": False}
        assert body["webhook"] == {"url": "https://example.com/hook"}

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

    def test_create_video_motion_included_and_no_export_label(
        self, mock_api: respx.MockRouter
    ) -> None:
        """VideoOptions wiring: motion is forwarded; export_label is gone (not a
        BE field on the video endpoint)."""
        route = mock_api.post("/api/v1/renders/video").mock(
            return_value=httpx.Response(202, json=MOCK_VIDEO_JOB_ACCEPTED_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            client.renders.create_video(
                mockup_uuid="m-1",
                smart_objects=_SO,
                duration_seconds=5,
                motion="showcase",
            )
        body = json.loads(route.calls.last.request.content)
        assert body["video"]["motion"] == "showcase"
        assert "export_label" not in body
        assert "export_label" not in body["video"]

    def test_create_video_rejects_export_label_kwarg(self) -> None:
        """The removed export_label kwarg must no longer be accepted."""
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(TypeError):
                client.renders.create_video(
                    mockup_uuid="m-1",
                    smart_objects=_SO,
                    duration_seconds=5,
                    export_label="nope",  # type: ignore[call-arg]
                )


# ---------------------------------------------------------------------------
# PSD upload
# ---------------------------------------------------------------------------


class TestPsdUpload:
    def test_upload_sync_returns_mockup(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/psd/upload").mock(
            return_value=httpx.Response(200, json=MOCK_PSD_UPLOAD_SYNC_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.psd.upload(url="https://x.com/file.psd", name="My PSD")
        assert isinstance(result, Mockup)
        assert result.name == "Black T-Shirt Front"
        assert result.text_layers[0].name == "Customer Name"
        assert result.warnings[0].code == "PSD_HIDDEN_SMART_OBJECTS"
        # Real BE field names are psd_file_url / psd_name (not url / name).
        body = json.loads(route.calls.last.request.content)
        assert body["psd_file_url"] == "https://x.com/file.psd"
        assert body["psd_name"] == "My PSD"
        assert "url" not in body
        assert "name" not in body

    def test_upload_async_returns_job(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/psd/upload").mock(
            return_value=httpx.Response(202, json=MOCK_PSD_UPLOAD_ASYNC_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.psd.upload(url="https://x.com/file.psd", is_async=True)
        assert isinstance(result, JobAccepted)
        assert result.job_id == "upload-job-001"
        body = json.loads(route.calls.last.request.content)
        assert body["is_async"] is True
        assert body["psd_file_url"] == "https://x.com/file.psd"


# ---------------------------------------------------------------------------
# jobs.list
# ---------------------------------------------------------------------------


class TestJobsList:
    def test_list_jobs(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.get("/api/v1/jobs").mock(
            return_value=httpx.Response(200, json=MOCK_JOBS_LIST_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.jobs.list(kind="render", limit=10)
        assert isinstance(result, JobList)
        assert len(result.jobs) == 1
        assert result.jobs[0].status == "succeeded"
        assert result.next_cursor == "eyJrIjoiMSJ9"
        assert route.calls.last.request.url.params["kind"] == "render"


# ---------------------------------------------------------------------------
# mockups.update (rename)
# ---------------------------------------------------------------------------


class TestMockupUpdate:
    def test_rename(self, mock_api: respx.MockRouter) -> None:
        uuid = MOCK_MOCKUP["uuid"]
        route = mock_api.patch(f"/api/v1/mockups/{uuid}").mock(
            return_value=httpx.Response(200, json=MOCK_MOCKUP_GET_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.mockups.update(uuid, name="Renamed")
        assert isinstance(result, Mockup)
        body = json.loads(route.calls.last.request.content)
        assert body == {"name": "Renamed"}


# ---------------------------------------------------------------------------
# packages (public)
# ---------------------------------------------------------------------------


class TestPackages:
    def test_plans(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/packages/plans").mock(
            return_value=httpx.Response(200, json=MOCK_PLANS_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.packages.plans()
        assert isinstance(result, PlanList)
        assert result.plans[0].slug == "starter"
        assert result.plans[0].price_monthly == 24.99

    def test_pricing(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/packages/pricing").mock(
            return_value=httpx.Response(200, json=MOCK_PLANS_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.packages.pricing()
        assert len(result.plans) == 1


# ---------------------------------------------------------------------------
# webhook events feed + bulk replay + create body shape
# ---------------------------------------------------------------------------


class TestWebhookExtras:
    def test_events_feed(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.get("/api/v1/webhook-endpoints/events").mock(
            return_value=httpx.Response(200, json=MOCK_WEBHOOK_DELIVERIES_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.webhook_endpoints.events(limit=50)
        assert len(result.deliveries) == 1
        assert route.calls.last.request.url.params["limit"] == "50"

    def test_replay_failed(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/webhook-endpoints/wh-1/deliveries/replay-failed").mock(
            return_value=httpx.Response(202, json={"status": "enqueued", "count": 3})
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            client.webhook_endpoints.replay_failed("wh-1")
        assert len(route.calls) == 1

    def test_create_has_no_enabled_field(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/webhook-endpoints").mock(
            return_value=httpx.Response(201, json=MOCK_WEBHOOK_CREATE_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            client.webhook_endpoints.create(
                url="https://x.com/wh",
                events=["render.succeeded"],
                description="prod hook",
            )
        body = json.loads(route.calls.last.request.content)
        # `enabled` is update-only on the BE; create must not send it.
        assert "enabled" not in body
        assert body["event_types"] == ["render.succeeded"]
        assert body["description"] == "prod hook"
