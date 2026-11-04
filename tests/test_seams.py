"""Seam check and seam fix on both clients, and the seam fix job fields."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
import pytest

from sudomock import AsyncSudoMock, SudoMock
from sudomock.exceptions import InsufficientCreditsError, ValidationError
from sudomock.models import Job, JobAccepted, SeamCheck

from .conftest import ERROR_402, TEST_API_KEY, TEST_BASE_URL

if TYPE_CHECKING:
    import respx

JOB_ID = "7a7a7a7a-7a7a-7a7a-7a7a-7a7a7a7a7a7a"
TILE = "https://example.com/pattern-tile.png"
RESULT = "https://cdn.sudomock.com/seam-fixed/v1/u/u1/abc-result.png"
ALTERNATIVE = "https://cdn.sudomock.com/seam-fixed/v1/u/u1/abc-alternative.png"

CHECK_VISIBLE = {
    "success": True,
    "data": {
        "status": "visible_seam",
        "seams": [
            {"side": "left_right", "status": "visible_seam", "ranges": [[0, 412], [1630, 2048]]},
        ],
        "width": 2048,
        "height": 2048,
        "fixable": True,
        "unfixable_reason": None,
        "previous_fix": {"job_id": JOB_ID, "result_url": RESULT, "alternative_url": None},
        "unexpected": "dropped",
    },
}

FIX_ACCEPTED = {
    "job_id": JOB_ID,
    "kind": "seam_fix",
    "status": "queued",
    "status_url": f"/api/v1/jobs/{JOB_ID}",
}

FIX_SUCCEEDED = {
    "job_id": JOB_ID,
    "kind": "seam_fix",
    "status": "succeeded",
    "result_url": RESULT,
    "alternative_url": ALTERNATIVE,
    "result_status": "seamless",
    "changes": "whole_tile",
    "stage": "finishing",
    "mockup_uuid": None,
    "error": None,
    "credits_charged": 60,
    "payg": None,
    "created_at": "2026-11-05T00:00:00Z",
    "updated_at": "2026-11-05T00:00:40Z",
}

TRANSPARENT_EDGES_422 = {
    "detail": "The tile has transparent pixels along its edges, so its seams cannot be fixed.",
    "error_code": "TILE_HAS_TRANSPARENT_EDGES",
    "success": False,
}


@pytest.fixture
def client() -> SudoMock:
    return SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL, max_retries=1)


class TestCheckSeams:
    def test_sends_the_source_and_crop_aspect(
        self, mock_api: respx.MockRouter, client: SudoMock
    ) -> None:
        route = mock_api.post("/api/v1/check-seams").mock(
            return_value=httpx.Response(200, json=CHECK_VISIBLE)
        )
        check = client.images.check_seams(url=TILE, crop_aspect=1.5)

        assert json.loads(route.calls.last.request.content) == {
            "url": TILE,
            "crop_aspect": 1.5,
        }
        assert isinstance(check, SeamCheck)
        assert check.status == "visible_seam"
        assert check.seams[0].side == "left_right"
        assert check.seams[0].ranges == [[0, 412], [1630, 2048]]
        assert check.fixable is True
        assert check.unfixable_reason is None
        assert check.previous_fix is not None
        assert check.previous_fix.job_id == JOB_ID
        assert check.previous_fix.result_url == RESULT
        assert check.previous_fix.alternative_url is None
        assert not hasattr(check, "unexpected")

    def test_base64_with_content_type(self, mock_api: respx.MockRouter, client: SudoMock) -> None:
        route = mock_api.post("/api/v1/check-seams").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {
                        "status": "seamless",
                        "seams": [],
                        "width": 512,
                        "height": 512,
                        "fixable": False,
                        "unfixable_reason": "too_large",
                        "previous_fix": None,
                    },
                },
            )
        )
        check = client.images.check_seams(base64="aW1hZ2U=", content_type="image/png")

        assert json.loads(route.calls.last.request.content) == {
            "base64": "aW1hZ2U=",
            "content_type": "image/png",
        }
        assert check.seams == []
        assert check.unfixable_reason == "too_large"
        assert check.previous_fix is None

    @pytest.mark.parametrize(
        "kwargs",
        [
            {},
            {"url": TILE, "base64": "eA=="},
            {"url": TILE, "crop_aspect": 0},
            {"url": TILE, "crop_aspect": -1.0},
            {"url": TILE, "crop_aspect": float("nan")},
            {"url": TILE, "crop_aspect": True},
        ],
    )
    def test_refuses_a_bad_source_or_crop_aspect_without_a_call(
        self, mock_api: respx.MockRouter, client: SudoMock, kwargs: dict[str, object]
    ) -> None:
        route = mock_api.post("/api/v1/check-seams")
        with pytest.raises(ValueError):
            client.images.check_seams(**kwargs)  # type: ignore[arg-type]
        assert not route.called


class TestFixSeams:
    def test_submits_with_a_fresh_idempotency_key(
        self, mock_api: respx.MockRouter, client: SudoMock
    ) -> None:
        route = mock_api.post("/api/v1/fix-seams").mock(
            return_value=httpx.Response(202, json=FIX_ACCEPTED)
        )
        job = client.images.fix_seams(url=TILE, crop_aspect=2.0)

        request = route.calls.last.request
        assert json.loads(request.content) == {"url": TILE, "crop_aspect": 2.0}
        assert len(request.headers["Idempotency-Key"]) == 36
        assert isinstance(job, JobAccepted)
        assert job.job_id == JOB_ID
        assert job.kind == "seam_fix"
        assert job.status_url == f"/api/v1/jobs/{JOB_ID}"

    def test_sends_the_caller_key(self, mock_api: respx.MockRouter, client: SudoMock) -> None:
        route = mock_api.post("/api/v1/fix-seams").mock(
            return_value=httpx.Response(202, json=FIX_ACCEPTED)
        )
        client.images.fix_seams(url=TILE, idempotency_key="tile-42")
        assert route.calls.last.request.headers["Idempotency-Key"] == "tile-42"

    def test_a_refused_tile_raises_with_its_code(
        self, mock_api: respx.MockRouter, client: SudoMock
    ) -> None:
        mock_api.post("/api/v1/fix-seams").mock(
            return_value=httpx.Response(422, json=TRANSPARENT_EDGES_422)
        )
        with pytest.raises(ValidationError) as caught:
            client.images.fix_seams(url=TILE)
        assert caught.value.error_code == "TILE_HAS_TRANSPARENT_EDGES"

    def test_insufficient_credits(self, mock_api: respx.MockRouter, client: SudoMock) -> None:
        mock_api.post("/api/v1/fix-seams").mock(return_value=httpx.Response(402, json=ERROR_402))
        with pytest.raises(InsufficientCreditsError):
            client.images.fix_seams(url=TILE)


class TestSeamFixJob:
    def test_the_job_carries_the_seam_fix_fields(
        self, mock_api: respx.MockRouter, client: SudoMock
    ) -> None:
        mock_api.get(f"/api/v1/jobs/{JOB_ID}").mock(
            return_value=httpx.Response(200, json=FIX_SUCCEEDED)
        )
        job = client.jobs.get(JOB_ID)

        assert isinstance(job, Job)
        assert job.kind == "seam_fix"
        assert job.result_url == RESULT
        assert job.alternative_url == ALTERNATIVE
        assert job.result_status == "seamless"
        assert job.changes == "whole_tile"
        assert job.stage == "finishing"
        assert job.credits_charged == 60

    def test_a_failed_fix_keeps_its_public_code(
        self, mock_api: respx.MockRouter, client: SudoMock
    ) -> None:
        mock_api.get(f"/api/v1/jobs/{JOB_ID}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "job_id": JOB_ID,
                    "kind": "seam_fix",
                    "status": "failed",
                    "result_url": None,
                    "alternative_url": None,
                    "result_status": None,
                    "changes": None,
                    "stage": "fixing",
                    "error": {
                        "error_code": "TILE_NOT_FIXABLE",
                        "message": "This image could not be made into a seamless tile.",
                    },
                    "credits_charged": 0,
                },
            )
        )
        job = client.jobs.wait(JOB_ID, poll_interval=0)

        assert job.failed
        assert job.failure_details() == (
            "TILE_NOT_FIXABLE",
            "This image could not be made into a seamless tile.",
        )
        assert job.stage == "fixing"
        assert job.alternative_url is None

    def test_lists_seam_fix_jobs_by_kind(
        self, mock_api: respx.MockRouter, client: SudoMock
    ) -> None:
        route = mock_api.get("/api/v1/jobs").mock(
            return_value=httpx.Response(200, json={"jobs": [FIX_SUCCEEDED], "next_cursor": None})
        )
        page = client.jobs.list(kind="seam_fix")

        assert route.calls.last.request.url.params["kind"] == "seam_fix"
        assert page.jobs[0].alternative_url == ALTERNATIVE


class TestAsyncSeams:
    async def test_check_and_fix(self, mock_api: respx.MockRouter) -> None:
        check_route = mock_api.post("/api/v1/check-seams").mock(
            return_value=httpx.Response(200, json=CHECK_VISIBLE)
        )
        fix_route = mock_api.post("/api/v1/fix-seams").mock(
            return_value=httpx.Response(202, json=FIX_ACCEPTED)
        )
        mock_api.get(f"/api/v1/jobs/{JOB_ID}").mock(
            return_value=httpx.Response(200, json=FIX_SUCCEEDED)
        )
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            check = await client.images.check_seams(url=TILE, crop_aspect=0.75)
            job = await client.images.fix_seams(url=TILE, crop_aspect=0.75)
            done = await client.jobs.wait(job.job_id, poll_interval=0)

        assert json.loads(check_route.calls.last.request.content) == {
            "url": TILE,
            "crop_aspect": 0.75,
        }
        assert check.status == "visible_seam"
        assert "Idempotency-Key" in fix_route.calls.last.request.headers
        assert job.kind == "seam_fix"
        assert done.alternative_url == ALTERNATIVE
        assert done.changes == "whole_tile"

    async def test_refuses_both_sources(self, mock_api: respx.MockRouter) -> None:
        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(ValueError):
                await client.images.fix_seams(url=TILE, base64="eA==")
            with pytest.raises(ValueError):
                await client.images.check_seams()
