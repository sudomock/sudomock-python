"""Outbound webhook signature verification.

SudoMock signs every webhook delivery with an HMAC-SHA256 signature carried
in the ``SudoMock-Signature`` header::

    SudoMock-Signature: t=<unix_ts>,v1=<hex_digest>

The signed payload is ``f"{t}.{raw_body}"`` where ``raw_body`` is the exact
raw request body (do **not** re-serialize the parsed JSON). Verification is
constant-time, and deliveries older than the tolerance window (default 300s)
are rejected to mitigate replay attacks.

Usage::

    from sudomock import verify_webhook_signature
    from sudomock.exceptions import WebhookVerificationError

    @app.post("/webhooks/sudomock")
    async def handler(request):
        raw = await request.body()
        sig = request.headers["SudoMock-Signature"]
        try:
            verify_webhook_signature(secret, sig, raw)
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


def _parse_signature_header(header: str) -> tuple[str, str]:
    """Parse ``t=<ts>,v1=<hex>`` into ``(timestamp, signature)``.

    Raises:
        WebhookVerificationError: If the header is malformed.
    """
    timestamp: str = ""
    signature: str = ""
    for part in header.split(","):
        key, _, value = part.strip().partition("=")
        if key == "t":
            timestamp = value
        elif key == "v1":
            signature = value

    if not timestamp or not signature:
        raise WebhookVerificationError(
            "Malformed signature header: expected 't=<ts>,v1=<hex>'"
        )
    return timestamp, signature


def verify_webhook_signature(
    secret: Union[str, bytes],
    signature_header: str,
    raw_body: Union[str, bytes],
    *,
    tolerance: int = DEFAULT_TOLERANCE,
) -> bool:
    """Verify an inbound SudoMock webhook signature.

    Args:
        secret: The endpoint's signing secret (``whsec_...``).
        signature_header: The raw ``SudoMock-Signature`` header value.
        raw_body: The exact raw request body (bytes or str). Do not pass
            re-serialized JSON -- whitespace differences break the signature.
        tolerance: Maximum allowed age of the delivery in seconds (default
            300). Pass ``0`` to disable the replay-window check.

    Returns:
        ``True`` if the signature is valid.

    Raises:
        WebhookVerificationError: If the header is malformed, the timestamp
            is outside the tolerance window, or the signature does not match.
    """
    timestamp, expected_sig = _parse_signature_header(signature_header)

    try:
        ts_int = int(timestamp)
    except ValueError as exc:
        raise WebhookVerificationError(
            f"Invalid timestamp in signature header: {timestamp!r}"
        ) from exc

    if tolerance > 0:
        age = abs(int(time.time()) - ts_int)
        if age > tolerance:
            raise WebhookVerificationError(
                f"Timestamp outside tolerance window ({age}s > {tolerance}s); "
                "possible replay attack"
            )

    body_bytes = _to_bytes(raw_body)
    signed_payload = _to_bytes(timestamp) + b"." + body_bytes
    computed = hmac.new(
        _to_bytes(secret), signed_payload, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed, expected_sig):
        raise WebhookVerificationError("Signature mismatch")

    return True
