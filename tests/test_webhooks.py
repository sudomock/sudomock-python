"""Tests for webhook endpoint management and signature verification."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import TYPE_CHECKING

import httpx
import pytest

from sudomock import SudoMock, verify_webhook_signature
from sudomock.exceptions import WebhookVerificationError
from sudomock.models import WebhookEndpoint, WebhookEndpointList

from .conftest import (
    MOCK_WEBHOOK_CREATE_RESPONSE,
    MOCK_WEBHOOK_DELIVERIES_RESPONSE,
    MOCK_WEBHOOK_GET_RESPONSE,
    MOCK_WEBHOOK_LIST_RESPONSE,
    MOCK_WEBHOOK_ROTATE_RESPONSE,
    TEST_API_KEY,
    TEST_BASE_URL,
)

if TYPE_CHECKING:
    import respx


# ---------------------------------------------------------------------------
# Webhook endpoint management (x-api-key alt-auth)
# ---------------------------------------------------------------------------


class TestWebhookEndpointsCRUD:
    def test_list(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/webhook-endpoints").mock(
            return_value=httpx.Response(200, json=MOCK_WEBHOOK_LIST_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.webhook_endpoints.list()
        assert isinstance(result, WebhookEndpointList)
        assert len(result.webhook_endpoints) == 1
        assert result.webhook_endpoints[0].url.endswith("/sudomock")

    def test_create(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/webhook-endpoints").mock(
            return_value=httpx.Response(201, json=MOCK_WEBHOOK_CREATE_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.webhook_endpoints.create(
                url="https://example.com/webhooks/sudomock",
                events=["render.succeeded", "render.failed"],
            )
        assert isinstance(result, WebhookEndpoint)
        assert result.secret == "whsec_testsecret123"
        body = json.loads(route.calls.last.request.content)
        assert body["event_types"] == ["render.succeeded", "render.failed"]
        assert body["enabled"] is True

    def test_create_uses_api_key(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/webhook-endpoints").mock(
            return_value=httpx.Response(201, json=MOCK_WEBHOOK_CREATE_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            client.webhook_endpoints.create(url="https://x.com/wh", events=["a"])
        assert route.calls.last.request.headers["x-api-key"] == TEST_API_KEY

    def test_get(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/webhook-endpoints/wh-uuid-1").mock(
            return_value=httpx.Response(200, json=MOCK_WEBHOOK_GET_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.webhook_endpoints.get("wh-uuid-1")
        assert result.id == "wh-uuid-1"

    def test_update(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.patch("/api/v1/webhook-endpoints/wh-uuid-1").mock(
            return_value=httpx.Response(200, json=MOCK_WEBHOOK_GET_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            client.webhook_endpoints.update("wh-uuid-1", enabled=False)
        body = json.loads(route.calls.last.request.content)
        assert body == {"enabled": False}

    def test_delete(self, mock_api: respx.MockRouter) -> None:
        mock_api.delete("/api/v1/webhook-endpoints/wh-uuid-1").mock(
            return_value=httpx.Response(204)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            client.webhook_endpoints.delete("wh-uuid-1")

    def test_rotate_secret(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/api/v1/webhook-endpoints/wh-uuid-1/rotate-secret").mock(
            return_value=httpx.Response(200, json=MOCK_WEBHOOK_ROTATE_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.webhook_endpoints.rotate_secret("wh-uuid-1")
        assert result.secret == "whsec_rotated456"

    def test_test_delivery(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post("/api/v1/webhook-endpoints/wh-uuid-1/test").mock(
            return_value=httpx.Response(202)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            client.webhook_endpoints.test("wh-uuid-1")
        assert len(route.calls) == 1

    def test_deliveries(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/api/v1/webhook-endpoints/wh-uuid-1/deliveries").mock(
            return_value=httpx.Response(200, json=MOCK_WEBHOOK_DELIVERIES_RESPONSE)
        )
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            result = client.webhook_endpoints.deliveries("wh-uuid-1")
        assert len(result.deliveries) == 1
        assert result.deliveries[0].http_status == 500
        assert result.deliveries[0].id == "dlv-1"

    def test_replay_delivery(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.post(
            "/api/v1/webhook-endpoints/wh-uuid-1/deliveries/dlv-1/replay"
        ).mock(return_value=httpx.Response(202))
        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            client.webhook_endpoints.replay_delivery("wh-uuid-1", "dlv-1")
        assert len(route.calls) == 1


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------

_SECRET = "whsec_topsecret"


def _sign(secret: str, timestamp: int, body: bytes) -> str:
    """Compute the hex HMAC-SHA256 digest of f"{ts}.{body}" (the X-SudoMock-Signature value)."""
    payload = f"{timestamp}.".encode() + body
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


class TestVerifyWebhookSignature:
    def test_valid_signature(self) -> None:
        body = b'{"event":"render.succeeded"}'
        ts = int(time.time())
        sig = _sign(_SECRET, ts, body)
        assert verify_webhook_signature(_SECRET, sig, str(ts), body) is True

    def test_valid_with_str_body_and_secret(self) -> None:
        body = '{"event":"render.succeeded"}'
        ts = int(time.time())
        sig = _sign(_SECRET, ts, body.encode())
        # str secret + str body should also work
        assert verify_webhook_signature(_SECRET, sig, str(ts), body) is True

    def test_int_timestamp_accepted(self) -> None:
        body = b'{"event":"render.succeeded"}'
        ts = int(time.time())
        sig = _sign(_SECRET, ts, body)
        # the timestamp header may be passed as an int too
        assert verify_webhook_signature(_SECRET, sig, ts, body) is True

    def test_tampered_body_fails(self) -> None:
        body = b'{"event":"render.succeeded"}'
        ts = int(time.time())
        sig = _sign(_SECRET, ts, body)
        with pytest.raises(WebhookVerificationError, match="mismatch"):
            verify_webhook_signature(_SECRET, sig, str(ts), b'{"event":"tampered"}')

    def test_wrong_secret_fails(self) -> None:
        body = b"payload"
        ts = int(time.time())
        sig = _sign(_SECRET, ts, body)
        with pytest.raises(WebhookVerificationError, match="mismatch"):
            verify_webhook_signature("whsec_wrong", sig, str(ts), body)

    def test_missing_signature_header(self) -> None:
        with pytest.raises(WebhookVerificationError, match="Missing X-SudoMock-Signature"):
            verify_webhook_signature(_SECRET, "", "12345", b"x")

    def test_missing_timestamp_header(self) -> None:
        with pytest.raises(WebhookVerificationError, match="Missing X-SudoMock-Timestamp"):
            verify_webhook_signature(_SECRET, "deadbeef", "", b"x")

    def test_non_integer_timestamp(self) -> None:
        with pytest.raises(WebhookVerificationError, match="Invalid timestamp"):
            verify_webhook_signature(_SECRET, "deadbeef", "abc", b"x")

    def test_expired_timestamp_rejected(self) -> None:
        body = b"payload"
        old_ts = int(time.time()) - 1000
        sig = _sign(_SECRET, old_ts, body)
        with pytest.raises(WebhookVerificationError, match="tolerance"):
            verify_webhook_signature(_SECRET, sig, str(old_ts), body)

    def test_tolerance_zero_disables_replay_check(self) -> None:
        body = b"payload"
        old_ts = int(time.time()) - 100000
        sig = _sign(_SECRET, old_ts, body)
        # signature still valid, replay window disabled
        assert verify_webhook_signature(_SECRET, sig, str(old_ts), body, tolerance=0) is True

    def test_future_timestamp_within_tolerance_ok(self) -> None:
        body = b"payload"
        future_ts = int(time.time()) + 10
        sig = _sign(_SECRET, future_ts, body)
        assert verify_webhook_signature(_SECRET, sig, str(future_ts), body) is True
