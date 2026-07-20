"""Pydantic v2 response models for the SudoMock API.

All models use ``model_config = {"extra": "allow"}`` so that new fields
added to the API do not break existing SDK versions.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TCH003 - Pydantic needs this at runtime
from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Shared / base
# ---------------------------------------------------------------------------


class _Base(BaseModel):
    """Base model with forward-compatible config."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)


# ---------------------------------------------------------------------------
# Account & subscription
# ---------------------------------------------------------------------------


class Account(_Base):
    """User account information."""

    uuid: str
    email: str
    name: Optional[str] = None
    created_at: datetime


class Subscription(_Base):
    """Active subscription details."""

    plan: str
    status: str
    # Plan tier slug (e.g. ``free`` / ``starter`` / ``scale``).
    tier: Optional[str] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False
    # Where the subscription is billed: ``shopify`` | ``stripe`` | ``none``.
    billing_channel: Optional[str] = None


class Usage(_Base):
    """Credit usage within the current billing period."""

    credits_used_this_month: int
    credits_limit: int
    credits_remaining: int
    billing_period_start: datetime
    billing_period_end: datetime


class ApiKeyInfo(_Base):
    """Metadata about the API key used for authentication."""

    name: str
    created_at: datetime
    last_used_at: Optional[datetime] = None
    total_requests: int


class AccountInfo(_Base):
    """Aggregate response for GET /api/v1/me."""

    account: Account
    subscription: Subscription
    usage: Usage
    api_key: ApiKeyInfo


# ---------------------------------------------------------------------------
# Smart objects & mockups
# ---------------------------------------------------------------------------


class Size(_Base):
    """Width/height pair."""

    width: int
    height: int


class Position(_Base):
    """Layer position on the PSD canvas."""

    x: int
    y: int
    width: int
    height: int


class SmartObject(_Base):
    """A single smart-object layer within a mockup."""

    uuid: str
    name: Optional[str] = None
    size: Optional[Size] = None
    position: Optional[Position] = None
    # Forward-compatible: extra fields silently accepted


class Mockup(_Base):
    """A mockup template parsed from a PSD file."""

    uuid: str
    name: str
    smart_objects: list[SmartObject] = Field(default_factory=list)
    width: Optional[int] = None
    height: Optional[int] = None
    # Main preview thumbnail (720px). This is the field returned by the API for
    # PSD mockups -- ``psd.upload`` (sync), ``mockups.list`` and ``mockups.get``
    # all populate ``thumbnail`` (an empty string when generation failed). The
    # full size ladder (720 / 480 / 240) is accepted via ``extra='allow'`` under
    # ``thumbnails``. ``thumbnail_url`` below is kept for forward-compatibility
    # only and is not currently emitted by these endpoints.
    thumbnail: Optional[str] = None
    thumbnail_url: Optional[str] = None
    created_at: Optional[datetime] = None


class MockupList(_Base):
    """Paginated list of mockups."""

    mockups: list[Mockup]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


class PrintFile(_Base):
    """A single rendered output file.

    Returned by both the still-render path (``renders.create`` —
    ``smart_object_uuid`` set, plus ``render_uuid``) and the SudoAI 2D-render
    path (``ai.render`` — ``smart_object_uuid`` absent, ``duration_ms`` /
    ``export_format`` present instead). Fields that only appear on one path are
    optional so a single model covers both.
    """

    export_path: str
    # Present on still renders; the SudoAI 2D-render print_files omit it.
    smart_object_uuid: Optional[str] = None
    # Present on still renders (route-level field, not always in the envelope).
    render_uuid: Optional[str] = None
    # Present on SudoAI 2D-render print_files.
    duration_ms: Optional[int] = None
    export_format: Optional[str] = None

    @property
    def url(self) -> str:
        """Alias for ``export_path`` for convenient access."""
        return self.export_path


class Render(_Base):
    """Result of a render request."""

    print_files: list[PrintFile]

    @property
    def url(self) -> str:
        """Shortcut: URL of the first print file."""
        if not self.print_files:
            raise ValueError("Render contains no print files")
        return self.print_files[0].url


# ---------------------------------------------------------------------------
# SudoAI 2D render
# ---------------------------------------------------------------------------


class AIRender(_Base):
    """Result of a SudoAI 2D-mockup render (``POST /sudoai/2d-mockup/render``).

    The 2D-render ``print_files`` carry ``export_path`` / ``duration_ms`` /
    ``export_format`` (no ``smart_object_uuid``).
    """

    print_files: list[PrintFile] = Field(default_factory=list)

    @property
    def url(self) -> str:
        """Shortcut: URL of the first print file."""
        if not self.print_files:
            raise ValueError("AI render contains no print files")
        return self.print_files[0].url


class Quad(_Base):
    """A printable four-point area on a 2D mockup."""

    print_area_id: str
    points: list[list[float]]
    sort_order: int


class TwoDPrintAreasUpdate(_Base):
    """Updated geometry returned after replacing 2D print areas."""

    mockup_id: str
    print_areas: list[Quad] = Field(default_factory=list)


class TwoDMockup(_Base):
    """A SudoAI 2D mockup (``GET /sudoai/2d-mockup/{id}`` / list).

    The detail endpoint returns ``quads``; the list endpoint returns
    ``print_areas``. Both are accepted via ``extra='allow'``.
    """

    mockup_id: str
    name: Optional[str] = None
    status: Optional[str] = None
    thumbnail_url: Optional[str] = None
    watermarked_source_url: Optional[str] = None
    source_width: Optional[int] = None
    source_height: Optional[int] = None
    quads: list[Quad] = Field(default_factory=list)
    version: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TwoDMockupList(_Base):
    """Paginated list of SudoAI 2D mockups.

    The API returns ``{data: [...], total, limit, offset, success}``; the
    client lifts the array into ``mockups`` with the sibling pagination fields.
    """

    mockups: list[TwoDMockup] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Async jobs (is_async renders / uploads / video)
# ---------------------------------------------------------------------------


class JobAccepted(_Base):
    """Acknowledgement returned by a ``202 Accepted`` async submission.

    Returned by ``renders.create(..., is_async=True)``, ``psd.upload(...,
    is_async=True)``, ``renders.create_video(...)``, and ``ai.create(...)``.
    Poll for completion with :meth:`jobs.get` or :meth:`jobs.wait` using
    :attr:`job_id`.
    """

    job_id: str
    kind: Optional[str] = None
    status: Optional[str] = None
    status_url: Optional[str] = None


class PaygCost(_Base):
    """Pay-as-you-go cost breakdown for a job (only present on PAYG jobs).

    Mirrors the nested ``payg`` object in ``GET /api/v1/jobs/{job_id}``:
    ``{credits, unit_price, cost}`` where ``cost`` is ``credits * unit_price``
    in USD (or ``None`` if either input is missing).
    """

    credits: Optional[int] = None
    unit_price: Optional[float] = None
    cost: Optional[float] = None


class Job(_Base):
    """Status of an async job from ``GET /api/v1/jobs/{job_id}``.

    The terminal states are ``"succeeded"`` and ``"failed"``; ``"queued"``
    and ``"running"`` are non-terminal. The current state value is exposed on
    :attr:`status` (the API field is ``status``).
    """

    job_id: Optional[str] = None
    kind: Optional[str] = None
    status: str
    model: Optional[str] = None
    result_url: Optional[str] = None
    mockup_uuid: Optional[str] = None
    error: Optional[Union[str, dict[str, Any]]] = None
    # Real charge for the job. For credit/subscription jobs this is the
    # deducted credit count; for PAYG it is the billable credit count (NOT the
    # stored 0). The dollar amount lives in :attr:`payg`.
    credits_charged: Optional[int] = None
    # Nested cost breakdown, present only for PAYG jobs (else ``None``).
    payg: Optional[PaygCost] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Terminal-state helpers ------------------------------------------------

    @property
    def is_terminal(self) -> bool:
        """True once the job has reached a terminal state."""
        return self.status in ("succeeded", "failed")

    @property
    def succeeded(self) -> bool:
        """True if the job finished successfully."""
        return self.status == "succeeded"

    @property
    def failed(self) -> bool:
        """True if the job failed."""
        return self.status == "failed"

    def failure_details(self) -> tuple[Optional[str], Optional[str]]:
        """Return the machine-readable code and human-readable failure reason."""
        if isinstance(self.error, dict):
            error_code = self.error.get("error_code")
            reason = self.error.get("message") or self.error.get("reason")
            return (
                error_code if isinstance(error_code, str) else None,
                reason if isinstance(reason, str) else None,
            )
        return None, self.error

    @property
    def url(self) -> str:
        """Shortcut: the result URL (only available once succeeded)."""
        if not self.result_url:
            raise ValueError(
                f"Job has no result_url (status={self.status!r}); it may not have succeeded yet"
            )
        return self.result_url


class JobList(_Base):
    """Keyset-paginated list of async jobs (``GET /api/v1/jobs``).

    Each item carries the same fields as :class:`Job` plus display extras
    (``duration_seconds``, ``audio``, ``mockup_name``, ``poster_url``) which are
    accepted via ``extra='allow'``. Pass :attr:`next_cursor` back to
    ``jobs.list(cursor=...)`` to fetch the next page (``None`` when exhausted).
    """

    jobs: list[Job] = Field(default_factory=list)
    next_cursor: Optional[str] = None


# ---------------------------------------------------------------------------
# Video render
# ---------------------------------------------------------------------------


class VideoOptions(_Base):
    """Video generation options for ``renders.create_video``.

    Attributes:
        duration_seconds: Clip length; must be in the chosen model's allowed
            set or the API returns ``400`` (``INVALID_VIDEO_DURATION``). If
            omitted at the API the server defaults to ``5`` seconds.
        audio: Whether to generate audio (default off).
        motion: Animation style, ``ambient`` (default) or ``showcase``.
        advanced_model: Optional model override (otherwise auto-selected by
            tier). When omitted the API picks the default for your plan.
    """

    duration_seconds: int
    audio: bool = False
    motion: Optional[str] = None
    advanced_model: Optional[str] = None


# ---------------------------------------------------------------------------
# Webhook endpoints
# ---------------------------------------------------------------------------


class WebhookEndpoint(_Base):
    """A registered outbound webhook endpoint.

    Mirrors the API's ``WebhookEndpointResponse``: the identifier is ``id``,
    subscribed events are ``event_types`` (empty = subscribe to all), and the
    ``secret`` is masked (``whsec_****<last4>``) except on create / rotate
    where the full value is returned once.
    """

    id: str
    url: str
    secret: Optional[str] = None
    description: Optional[str] = None
    event_types: list[str] = Field(default_factory=list)
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class WebhookEndpointList(_Base):
    """List of registered webhook endpoints.

    The API list endpoint returns a bare JSON array; the client wraps it in
    this convenience model (``webhook_endpoints``).
    """

    webhook_endpoints: list[WebhookEndpoint] = Field(default_factory=list)


class WebhookSecret(_Base):
    """Result of rotating a webhook signing secret.

    The rotate endpoint returns the full endpoint object with the unmasked
    ``secret``; this convenience model exposes the ``secret`` field directly
    (extra endpoint fields are accepted via ``extra="allow"``).
    """

    secret: str


class WebhookDelivery(_Base):
    """A single delivery-attempt log row.

    Mirrors the API's ``WebhookDeliveryResponse``: ``id`` is the row id,
    ``job_id`` is the originating job, the HTTP response code is
    ``http_status``, and ``attempt`` is the retry counter.
    """

    id: str
    endpoint_id: Optional[str] = None
    job_id: Optional[str] = None
    event_type: Optional[str] = None
    status: Optional[str] = None
    http_status: Optional[int] = None
    attempt: int = 0
    last_error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class WebhookDeliveryList(_Base):
    """List of delivery attempts for a webhook endpoint.

    The API deliveries endpoint returns a bare JSON array; the client wraps it
    in this convenience model (``deliveries``).
    """

    deliveries: list[WebhookDelivery] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Packages / pricing
# ---------------------------------------------------------------------------


class Plan(_Base):
    """A subscription plan (``GET /api/v1/packages/plans`` / ``/pricing``)."""

    id: str
    name: str
    slug: Optional[str] = None
    tier: Optional[str] = None
    description: Optional[str] = None
    price_monthly: Optional[float] = None
    price_yearly: Optional[float] = None
    credits_per_month: Optional[int] = None
    max_concurrent_requests: Optional[int] = None
    max_concurrent_uploads: Optional[int] = None
    stripe_price_id: Optional[str] = None
    stripe_price_id_yearly: Optional[str] = None


class PlanList(_Base):
    """List of available plans (the API returns ``{plans: [...]}``)."""

    plans: list[Plan] = Field(default_factory=list)
