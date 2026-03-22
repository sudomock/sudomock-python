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

MOCK_AI_RENDER_RESPONSE = {
    "success": True,
    "data": {
        "print_files": [
            {
                "export_path": "https://cdn.sudomock.com/ai-renders/xyz789/render.webp",
                "smart_object_uuid": "auto-detected",
            }
        ]
    },
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
