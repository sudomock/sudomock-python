"""Shared fixtures for SudoMock SDK tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import respx

if TYPE_CHECKING:
    from collections.abc import Generator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_API_KEY = "sm_test_key_1234567890abcdef"
TEST_BASE_URL = "https://api.sudomock.com"

# ---------------------------------------------------------------------------
# Mock response payloads
# ---------------------------------------------------------------------------

MOCK_MOCKUP = {
    "uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    "name": "Black T-Shirt Front",
    "smart_objects": [
        {
            "uuid": "11111111-2222-3333-4444-555555555555",
            "name": "Front Design",
            "size": {"width": 800, "height": 600},
            "position": {"x": 100, "y": 200, "width": 800, "height": 600},
        }
    ],
    "width": 2000,
    "height": 2400,
    "thumbnail_url": "https://cdn.sudomock.com/thumbnails/aaa.png",
    "created_at": "2026-01-15T10:30:00Z",
}

MOCK_MOCKUP_LIST_RESPONSE = {
    "success": True,
    "data": {
        "mockups": [MOCK_MOCKUP],
        "total": 1,
        "limit": 20,
        "offset": 0,
    },
}

MOCK_MOCKUP_GET_RESPONSE = {
    "success": True,
    "data": MOCK_MOCKUP,
}

MOCK_RENDER_RESPONSE = {
    "success": True,
    "data": {
        "print_files": [
            {
                "export_path": "https://cdn.sudomock.com/renders/abc123/render.webp",
                "smart_object_uuid": "11111111-2222-3333-4444-555555555555",
            }
        ]
    },
}

# SudoAI 2D render: print_files carry export_path / duration_ms / export_format
# (NO smart_object_uuid). Matches POST /sudoai/2d-mockup/render.
MOCK_AI_RENDER_RESPONSE = {
    "success": True,
    "data": {
        "print_files": [
            {
                "export_path": "https://cdn.sudomock.com/ai-renders/xyz789/render.webp",
                "duration_ms": 412,
                "export_format": "webp",
            }
        ]
    },
}

# 2D mockup detail (GET /sudoai/2d-mockup/{id}) — has quads.
MOCK_2D_MOCKUP = {
    "mockup_id": "2d-mockup-001",
    "name": "Flat Tee Front",
    "status": "ready",
    "thumbnail_url": "https://cdn.sudomock.com/2d/thumb.png",
    "watermarked_source_url": "https://cdn.sudomock.com/2d/src.png",
    "source_width": 2000,
    "source_height": 2000,
    "quads": [{"print_area_id": "pa-1", "points": [], "sort_order": 0}],
    "version": 1,
    "created_at": "2026-06-21T10:00:00Z",
    "updated_at": "2026-06-21T10:00:00Z",
}

MOCK_2D_MOCKUP_GET_RESPONSE = {"data": MOCK_2D_MOCKUP, "success": True}

# 2D mockup list (GET /sudoai/2d-mockups) — data array + sibling pagination.
MOCK_2D_MOCKUP_LIST_RESPONSE = {
    "data": [
        {
            "mockup_id": "2d-mockup-001",
            "name": "Flat Tee Front",
            "status": "ready",
            "thumbnail_url": "https://cdn.sudomock.com/2d/thumb.png",
            "watermarked_source_url": "https://cdn.sudomock.com/2d/src.png",
            "source_width": 2000,
            "source_height": 2000,
            "print_areas": [{"print_area_id": "pa-1"}],
            "version": 1,
            "created_at": "2026-06-21T10:00:00Z",
            "updated_at": "2026-06-21T10:00:00Z",
        }
    ],
    "total": 1,
    "limit": 20,
    "offset": 0,
    "success": True,
}

MOCK_2D_MOCKUP_DELETE_RESPONSE = {"data": {"deleted": True}, "success": True}

MOCK_2D_MOCKUP_JOB_ACCEPTED_RESPONSE = {
    "job_id": "2d-create-job-001",
    "kind": "2d_create",
    "status": "queued",
    "status_url": "/api/v1/jobs/2d-create-job-001",
}

MOCK_2D_MOCKUP_JOB_QUEUED_RESPONSE = {
    "job_id": "2d-create-job-001",
    "kind": "2d_create",
    "status": "queued",
}

MOCK_2D_MOCKUP_JOB_SUCCEEDED_RESPONSE = {
    "job_id": "2d-create-job-001",
    "kind": "2d_create",
    "status": "succeeded",
    "result_url": "/api/v1/sudoai/2d-mockup/2d-mockup-001",
    "mockup_uuid": "2d-mockup-001",
    "error": None,
}

MOCK_2D_MOCKUP_JOB_FAILED_RESPONSE = {
    "job_id": "2d-create-job-001",
    "kind": "2d_create",
    "status": "failed",
    "result_url": None,
    "mockup_uuid": None,
    "error": {
        "error_code": "NOT_MOCKUPABLE",
        "message": "The source image is not suitable for a 2D mockup",
    },
}

MOCK_2D_PRINT_AREAS_UPDATE_RESPONSE = {
    "data": {
        "mockup_id": "2d-mockup-001",
        "print_areas": [
            {
                "print_area_id": "pa-1",
                "points": [[100, 100], [500, 100], [500, 500], [100, 500]],
                "sort_order": 0,
            }
        ],
    },
    "success": True,
}

# Packages / pricing (GET /packages/plans|pricing) — {plans: [...]}.
MOCK_PLANS_RESPONSE = {
    "plans": [
        {
            "id": "plan-starter",
            "name": "Starter",
            "slug": "starter",
            "tier": "starter",
            "description": "For solo sellers",
            "price_monthly": 24.99,
            "price_yearly": 224.0,
            "credits_per_month": 1000,
            "max_concurrent_requests": 3,
            "max_concurrent_uploads": 3,
            "stripe_price_id": "price_123",
            "stripe_price_id_yearly": "price_456",
        }
    ]
}

# Jobs list (GET /jobs) — bare {jobs: [...], next_cursor}.
MOCK_JOBS_LIST_RESPONSE = {
    "jobs": [
        {
            "job_id": "job-uuid-abc123",
            "kind": "render",
            "status": "succeeded",
            "result_url": "https://cdn.sudomock.com/renders/abc/render.webp",
            "credits_charged": 1,
            "duration_seconds": None,
            "audio": False,
            "mockup_name": "Black T-Shirt Front",
            "poster_url": None,
        }
    ],
    "next_cursor": "eyJrIjoiMSJ9",
}

MOCK_ME_RESPONSE = {
    "success": True,
    "data": {
        "account": {
            "uuid": "user-uuid-1234",
            "email": "dev@example.com",
            "name": "Acme Corp",
            "created_at": "2025-06-15T10:30:00Z",
        },
        "subscription": {
            "plan": "pro",
            "status": "active",
            "current_period_end": "2026-02-05T00:00:00Z",
            "cancel_at_period_end": False,
        },
        "usage": {
            "credits_used_this_month": 12847,
            "credits_limit": 50000,
            "credits_remaining": 37153,
            "billing_period_start": "2026-01-01T00:00:00Z",
            "billing_period_end": "2026-02-01T00:00:00Z",
        },
        "api_key": {
            "name": "Production Key",
            "created_at": "2025-06-15T10:30:00Z",
            "last_used_at": "2026-01-05T00:25:00Z",
            "total_requests": 847293,
        },
    },
}

# Async job submission (202). The async submit + job-poll endpoints return BARE
# bodies (no {success, data} envelope) — these fixtures match the real BE.
MOCK_JOB_ACCEPTED_RESPONSE = {
    "job_id": "job-uuid-abc123",
    "kind": "render",
    "status": "queued",
    "status_url": "/api/v1/jobs/job-uuid-abc123",
}

MOCK_JOB_QUEUED_RESPONSE = {
    "job_id": "job-uuid-abc123",
    "kind": "render",
    "status": "queued",
}

MOCK_JOB_RUNNING_RESPONSE = {
    "job_id": "job-uuid-abc123",
    "kind": "render",
    "status": "running",
}

MOCK_JOB_SUCCEEDED_RESPONSE = {
    "job_id": "job-uuid-abc123",
    "kind": "render",
    "status": "succeeded",
    "model": None,
    "result_url": "https://cdn.sudomock.com/renders/job-uuid-abc123/render.webp",
    "mockup_uuid": None,
    "error": None,
    "credits_charged": 1,
    "payg": None,
    "created_at": "2026-06-21T10:00:00Z",
    "updated_at": "2026-06-21T10:00:05Z",
}

# A PAYG job: jobs.credits is 0 on the BE, the real cost is surfaced via the
# nested payg object (credits_charged == billable count, NOT 0).
MOCK_JOB_PAYG_SUCCEEDED_RESPONSE = {
    "job_id": "payg-job-001",
    "kind": "render",
    "status": "succeeded",
    "model": None,
    "result_url": "https://cdn.sudomock.com/renders/payg-job-001/render.webp",
    "mockup_uuid": None,
    "error": None,
    "credits_charged": 2,
    "payg": {"credits": 2, "unit_price": 0.0035, "cost": 0.007},
    "created_at": "2026-06-21T10:00:00Z",
    "updated_at": "2026-06-21T10:00:05Z",
}

MOCK_JOB_FAILED_RESPONSE = {
    "job_id": "job-uuid-abc123",
    "kind": "render",
    "status": "failed",
    "result_url": None,
    "error": "render engine error",
}

MOCK_VIDEO_JOB_ACCEPTED_RESPONSE = {
    "job_id": "video-job-xyz789",
    "kind": "video",
    "status": "queued",
    "status_url": "/api/v1/jobs/video-job-xyz789",
}

# Sync PSD upload still uses the {success, data} envelope (that endpoint wraps).
MOCK_PSD_UPLOAD_SYNC_RESPONSE = {
    "success": True,
    "data": MOCK_MOCKUP,
}

# Async PSD submit (202) returns a BARE body (no envelope).
MOCK_PSD_UPLOAD_ASYNC_RESPONSE = {
    "job_id": "upload-job-001",
    "kind": "upload",
    "status": "queued",
    "status_url": "/api/v1/jobs/upload-job-001",
}

# Webhook endpoints. Field names mirror the API's WebhookEndpointResponse:
# id (not uuid), event_types (not events), description, updated_at. The secret
# is full only on create / rotate; masked elsewhere.
MOCK_WEBHOOK_ENDPOINT = {
    "id": "wh-uuid-1",
    "url": "https://example.com/webhooks/sudomock",
    "secret": "whsec_testsecret123",
    "description": None,
    "event_types": ["render.succeeded", "render.failed"],
    "enabled": True,
    "created_at": "2026-06-21T10:00:00Z",
    "updated_at": None,
}

# All webhook-endpoint responses are BARE (no {success, data} envelope):
# create/get/update/rotate return a bare endpoint object; list/deliveries return
# bare JSON arrays. These fixtures match the real BE (FastAPI response_model
# serialization, not the legacy {success, data} wrapper).
MOCK_WEBHOOK_CREATE_RESPONSE = MOCK_WEBHOOK_ENDPOINT

MOCK_WEBHOOK_LIST_RESPONSE = [MOCK_WEBHOOK_ENDPOINT]

MOCK_WEBHOOK_GET_RESPONSE = MOCK_WEBHOOK_ENDPOINT

# Rotate returns the full endpoint with the unmasked secret.
MOCK_WEBHOOK_ROTATE_RESPONSE = {**MOCK_WEBHOOK_ENDPOINT, "secret": "whsec_rotated456"}

# Delivery rows mirror WebhookDeliveryResponse: id, endpoint_id, job_id,
# event_type, status, http_status (not response_status), attempt, last_error.
# The deliveries endpoint returns a BARE JSON array.
MOCK_WEBHOOK_DELIVERIES_RESPONSE = [
    {
        "id": "dlv-1",
        "endpoint_id": "wh-uuid-1",
        "job_id": "job-uuid-abc123",
        "event_type": "render.succeeded",
        "status": "failed",
        "http_status": 500,
        "attempt": 2,
        "last_error": "non-2xx response: 500",
        "created_at": "2026-06-21T10:05:00Z",
        "updated_at": "2026-06-21T10:06:00Z",
    }
]

# Error responses
ERROR_401 = {"detail": "Invalid or missing API key", "success": False}
ERROR_402 = {
    "detail": "Insufficient credits",
    "success": False,
    "error_code": "credits_exhausted",
    "credits_reset_at": "2026-02-01T00:00:00Z",
}
ERROR_404 = {"detail": "Mockup not found", "success": False}
ERROR_422 = {"detail": "Validation error: mockup_uuid is required", "success": False}
ERROR_429 = {
    "detail": "Rate limit exceeded",
    "success": False,
    "error": {"retry_after": 30},
}
ERROR_500 = {"detail": "Internal server error", "success": False}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def api_key() -> str:
    """Return a test API key."""
    return TEST_API_KEY


@pytest.fixture()
def base_url() -> str:
    """Return the test base URL."""
    return TEST_BASE_URL


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure SUDOMOCK_API_KEY is not leaking from the real environment."""
    monkeypatch.delenv("SUDOMOCK_API_KEY", raising=False)


@pytest.fixture()
def mock_api() -> Generator[respx.MockRouter, None, None]:
    """Provide a ``respx`` mock router scoped to the test base URL."""
    with respx.mock(base_url=TEST_BASE_URL, assert_all_called=False) as router:
        yield router
