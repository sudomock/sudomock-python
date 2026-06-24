"""Outbound webhook signature verification.

SudoMock signs every webhook delivery with an HMAC-SHA256 signature carried
in **two separate headers**::

    X-SudoMock-Signature: <hex_digest>
    X-SudoMock-Timestamp: <unix_ts>

The signed payload is ``f"{timestamp}.{raw_body}"`` where ``raw_body`` is the
exact raw request body (do **not** re-serialize the parsed JSON). The signature
is the hex HMAC-SHA256 digest of that payload under the endpoint's signing
secret. Verification is constant-time, and deliveries older than the tolerance
window (default 300s) are rejected to mitigate replay attacks.

Usage::

    from sudomock import verify_webhook_signature
    from sudomock.exceptions import WebhookVerificationError

    @app.post("/webhooks/sudomock")
    async def handler(request):
        raw = await request.body()
        sig = request.headers["X-SudoMock-Signature"]
        ts = request.headers["X-SudoMock-Timestamp"]
        try:
            verify_webhook_signature(secret, sig, ts, raw)
        except WebhookVerificationError:
            return Response(status_code=400)
        ...
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Union

from .exceptions import WebhookVerificationError

__all__ = ["verify_webhook_signature"]

# Default tolerance for the timestamp anti-replay check, in seconds.
DEFAULT_TOLERANCE = 300


def _to_bytes(value: Union[str, bytes]) -> bytes:
    return value.encode("utf-8") if isinstance(value, str) else value


def verify_webhook_signature(
    secret: Union[str, bytes],
    signature_header: str,
    timestamp_header: Union[str, int],
    raw_body: Union[str, bytes],
    *,
    tolerance: int = DEFAULT_TOLERANCE,
) -> bool:
    """Verify an inbound SudoMock webhook signature.

    SudoMock sends the signature and timestamp in two separate headers
    (``X-SudoMock-Signature`` and ``X-SudoMock-Timestamp``). The signature is
    the hex HMAC-SHA256 digest of ``f"{timestamp}.{raw_body}"`` under the
    endpoint's signing secret.

    Args:
        secret: The endpoint's signing secret (``whsec_...``).
        signature_header: The raw ``X-SudoMock-Signature`` header value (a hex
            digest).
        timestamp_header: The raw ``X-SudoMock-Timestamp`` header value (a unix
            timestamp; ``str`` or ``int``).
        raw_body: The exact raw request body (bytes or str). Do not pass
            re-serialized JSON -- whitespace differences break the signature.
        tolerance: Maximum allowed age of the delivery in seconds (default
            300). Pass ``0`` to disable the replay-window check.

    Returns:
        ``True`` if the signature is valid.

    Raises:
        WebhookVerificationError: If either header is missing, the timestamp is
            not an integer or is outside the tolerance window, or the signature
            does not match.
    """
    if not signature_header:
        raise WebhookVerificationError("Missing X-SudoMock-Signature header")
    if timestamp_header is None or timestamp_header == "":
        raise WebhookVerificationError("Missing X-SudoMock-Timestamp header")

    try:
        ts_int = int(timestamp_header)
    except (ValueError, TypeError) as exc:
        raise WebhookVerificationError(f"Invalid timestamp header: {timestamp_header!r}") from exc

    if tolerance > 0:
        age = abs(int(time.time()) - ts_int)
        if age > tolerance:
            raise WebhookVerificationError(
                f"Timestamp outside tolerance window ({age}s > {tolerance}s); "
                "possible replay attack"
            )

    body_bytes = _to_bytes(raw_body)
    # Signed material is f"{ts}.{raw_body}" -- the timestamp uses its raw
    # string form so a value with leading zeros / whitespace round-trips
    # exactly. We re-stringify the parsed int to normalize int/str input but
    # the server always sends a canonical decimal string.
    signed_payload = _to_bytes(str(ts_int)) + b"." + body_bytes
    computed = hmac.new(_to_bytes(secret), signed_payload, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed, signature_header):
        raise WebhookVerificationError("Signature mismatch")

    return True
