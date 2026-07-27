"""Pydantic v2 response models for the outcome-only SudoMock API."""

from __future__ import annotations

from datetime import datetime  # noqa: TCH003 - Pydantic needs this at runtime
from typing import Any, Literal, Optional, TypedDict

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ._public_contract import (
    is_implementation_key,
    public_error_code,
    public_error_text,
)

# ---------------------------------------------------------------------------
# Shared / base
# ---------------------------------------------------------------------------


class _Base(BaseModel):
    """Forward-compatible base for established customer-facing resources."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def hide_implementation_fields(cls, value: Any) -> Any:
        if not isinstance(value, dict) or cls.model_config.get("extra") == "forbid":
            return value
        return {
            key: item
            for key, item in value.items()
            if key in cls.model_fields or not is_implementation_key(key)
        }


class _Outcome(_Base):
    """Strict outcome surface that drops undocumented fields."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


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


class StudioSessionUi(TypedDict, total=False):
    """Request-scoped Studio labels and primary action color."""

    primary_action_label: str
    secondary_action_label: str
    accent_color: str


class StudioSession(_Outcome):
    """Opaque Studio session returned by POST /studio/create-session."""

    success: Literal[True] = True
    session: str
    expires_in: int
    mockup_type: Literal["psd", "2d"]
    message_session_id: str
    bootstrap_secret: str


class StudioResultPayload(_Outcome):
    """Outcome-only Studio result callback payload."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    mockup_uuid: str
    render_uuid: str
    action_id: Optional[str] = None


class StudioResultEvent(_Outcome):
    """Setup or customize result sent by the Studio iframe."""

    version: Literal[1]
    source: Literal["sudomock-studio"]
    type: Literal["studio.mockup-saved", "studio.design-submitted"]
    request_id: str
    message_session_id: str
    payload: StudioResultPayload

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class StudioActionContext(TypedDict, total=False):
    """Server-owned commerce context bound while consuming a Studio action."""

    shop: str
    product_id: str
    variant_id: str


class StudioActionContextData(_Outcome):
    """Commerce context returned in a confirmed Studio action."""

    shop: Optional[str] = None
    product_id: Optional[str] = None
    variant_id: Optional[str] = None


class StudioActionReceiptData(_Outcome):
    """Receipt bound to one session, render, action, and request."""

    version: Literal[1]
    request_id: str
    message_session_id: str
    type: Literal["studio.mockup-saved", "studio.design-submitted"]
    mockup_type: Literal["psd", "2d"]
    session_kind: Literal["setup", "customize"]
    action_id: Optional[str] = None
    action_context: StudioActionContextData
    mockup_uuid: str
    render_uuid: str


class StudioActionReceipt(_Outcome):
    """Exactly-once server confirmation result for one Studio event."""

    success: Literal[True] = True
    replayed: bool
    receipt: StudioActionReceiptData


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


class TextSegment(_Base):
    """One styled segment of a text layer."""

    index: int
    text: str
    font_postscript_name: Optional[str] = None
    font_size: Optional[float] = None
    color: Optional[str] = None


class TextLayer(_Base):
    """An editable text layer returned with a mockup."""

    uuid: str
    name: str
    text_content: Optional[str] = None
    font_postscript_name: Optional[str] = None
    font_size: Optional[float] = None
    color: Optional[str] = None
    font_available: Optional[bool] = None
    is_editable: bool = False
    segment_count: int = 1
    segments: Optional[list[TextSegment]] = None
    visible: Optional[bool] = None
    has_stroke_effect: bool = False
    stroke_count: int = 0
    has_color_overlay: bool = False
    has_clipped_artwork: Optional[bool] = None
    suggested_edit_together: Optional[list[str]] = None


class ApiWarning(_Outcome):
    """A non-fatal advisory returned with a successful request."""

    code: str
    message: str

    @model_validator(mode="after")
    def hide_implementation_details(self) -> ApiWarning:
        self.code = public_error_code(self.code) or "RENDER_WARNING"
        self.message = (
            public_error_text(
                self.message,
                "The request completed with an advisory.",
            )
            or "The request completed with an advisory."
        )
        return self


class Mockup(_Base):
    """A mockup template parsed from a PSD file."""

    uuid: str
    name: str
    smart_objects: list[SmartObject] = Field(default_factory=list)
    text_layers: list[TextLayer] = Field(default_factory=list)
    warnings: list[ApiWarning] = Field(default_factory=list)
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


class PrintFile(_Outcome):
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


class Render(_Outcome):
    """Result of a render request."""

    print_files: list[PrintFile]
    render_uuid: Optional[str] = None
    warnings: list[ApiWarning] = Field(default_factory=list)

    @property
    def url(self) -> str:
        """Shortcut: URL of the first print file."""
        if not self.print_files:
            raise ValueError("Render contains no print files")
        return self.print_files[0].url


# ---------------------------------------------------------------------------
# SudoAI 2D render
# ---------------------------------------------------------------------------


class AIRender(_Outcome):
    """Result of a SudoAI 2D-mockup render (``POST /sudoai/2d-mockups/{id}/render``).

    The 2D-render ``print_files`` carry ``export_path`` / ``duration_ms`` /
    ``export_format`` (no ``smart_object_uuid``). The render transaction id is
    exposed as ``render_uuid`` (a sibling of ``print_files`` in the ``data``
    envelope).
    """

    print_files: list[PrintFile] = Field(default_factory=list)
    render_uuid: Optional[str] = None

    @property
    def url(self) -> str:
        """Shortcut: URL of the first print file."""
        if not self.print_files:
            raise ValueError("AI render contains no print files")
        return self.print_files[0].url


class Quad(_Outcome):
    """A printable four-point area on a 2D mockup."""

    print_area_id: str
    points: list[list[float]]
    sort_order: int
    name: Optional[str] = None


class FullSurface(_Outcome):
    """A full product surface available as a render target."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    surface_uuid: str
    coverage: Literal["full"]


class TwoDPrintAreasUpdate(_Outcome):
    """Updated geometry returned after replacing 2D print areas."""

    mockup_id: str
    print_areas: list[Quad] = Field(default_factory=list)


class TwoDMockup(_Outcome):
    """A SudoAI 2D mockup (``GET /sudoai/2d-mockups/{id}`` / list).

    The detail endpoint returns ``quads``; the list endpoint returns
    ``print_areas``. Both are accepted via ``extra='allow'``.
    """

    mockup_id: str
    name: Optional[str] = None
    status: Optional[str] = None
    customizable: bool
    thumbnail_url: Optional[str] = None
    watermarked_source_url: Optional[str] = None
    source_width: Optional[int] = None
    source_height: Optional[int] = None
    quads: list[Quad] = Field(default_factory=list)
    print_areas: list[Quad] = Field(default_factory=list)
    surfaces: list[FullSurface] = Field(default_factory=list)
    version: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TwoDMockupList(_Outcome):
    """Paginated list of SudoAI 2D mockups.

    The API returns ``{data: [...], total, limit, offset, success}``; the
    client lifts the array into ``mockups`` with the sibling pagination fields.
    """

    mockups: list[TwoDMockup] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Background removal
# ---------------------------------------------------------------------------


class BackgroundRemoval(_Outcome):
    """Transparent-PNG cutout returned by ``POST /remove-background``.

    ``url`` is signed and valid for 7 days.
    """

    url: str
    width: int
    height: int
    credits_charged: int


# ---------------------------------------------------------------------------
# Async jobs (is_async renders / uploads / video)
# ---------------------------------------------------------------------------


class JobAccepted(_Outcome):
    """Acknowledgement returned by a ``202 Accepted`` async submission.

    Returned by ``renders.create(..., is_async=True)``, ``psd.upload(...,
    is_async=True)``, ``renders.create_video(...)``, and ``ai.create(...,
    is_async=True)``. Poll for completion with :meth:`jobs.get` or
    :meth:`jobs.wait` using :attr:`job_id`.
    """

    job_id: str
    kind: Optional[str] = None
    status: Optional[str] = None
    status_url: Optional[str] = None
    estimated_credits: Optional[int] = None
    outcome_tier: Optional[str] = None


class PaygCost(_Outcome):
    """Pay-as-you-go cost breakdown for a job (only present on PAYG jobs).

    Mirrors the nested ``payg`` object in ``GET /api/v1/jobs/{job_id}``:
    ``{credits, unit_price, cost}`` where ``cost`` is ``credits * unit_price``
    in USD (or ``None`` if either input is missing).
    """

    credits: Optional[int] = None
    unit_price: Optional[float] = None
    cost: Optional[float] = None


class Job(_Outcome):
    """Status of an async job from ``GET /api/v1/jobs/{job_id}``.

    The terminal states are ``"succeeded"`` and ``"failed"``; ``"queued"``
    and ``"running"`` are non-terminal. The current state value is exposed on
    :attr:`status` (the API field is ``status``).
    """

    job_id: Optional[str] = None
    kind: Optional[str] = None
    status: str
    result_url: Optional[str] = None
    mockup_uuid: Optional[str] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    # Real charge for the job. For credit/subscription jobs this is the
    # deducted credit count; for PAYG it is the billable credit count (NOT the
    # stored 0). The dollar amount lives in :attr:`payg`.
    credits_charged: Optional[int] = None
    # Nested cost breakdown, present only for PAYG jobs (else ``None``).
    payg: Optional[PaygCost] = None
    duration_seconds: Optional[int] = None
    audio: Optional[bool] = None
    mockup_name: Optional[str] = None
    poster_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @model_validator(mode="before")
    @classmethod
    def outcome_only_error(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        public = dict(value)
        error = public.get("error")
        error_code = public.get("error_code")
        if isinstance(error, dict):
            error_code = error.get("error_code", error_code)
            error = error.get("message") or error.get("reason")
        public["error"] = public_error_text(
            error,
            (
                "Processing failed. Retry or contact support with the job ID."
                if public.get("status") == "failed"
                else None
            ),
        )
        public["error_code"] = public_error_code(error_code)
        return public

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
        return self.error_code, self.error

    @property
    def url(self) -> str:
        """Shortcut: the result URL (only available once succeeded)."""
        if not self.result_url:
            raise ValueError(
                f"Job has no result_url (status={self.status!r}); it may not have succeeded yet"
            )
        return self.result_url


class JobList(_Outcome):
    """Keyset-paginated list of async jobs (``GET /api/v1/jobs``).

    Each item carries the same fields as :class:`Job`, including its documented
    display fields. Pass :attr:`next_cursor` back to ``jobs.list(cursor=...)``
    to fetch the next page (``None`` when exhausted).
    """

    jobs: list[Job] = Field(default_factory=list)
    next_cursor: Optional[str] = None


# ---------------------------------------------------------------------------
# Video render
# ---------------------------------------------------------------------------


class VideoOptions(_Outcome):
    """Video generation options for ``renders.create_video``.

    Attributes:
        duration_seconds: Clip length; unsupported values return ``400``.
        audio: Whether to generate audio (default off).
        motion: Animation style, ``ambient`` (default) or ``showcase``.
    """

    duration_seconds: int
    audio: bool = False
    motion: Optional[str] = None

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


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


class WebhookDelivery(_Outcome):
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

    @model_validator(mode="after")
    def hide_delivery_diagnostics(self) -> WebhookDelivery:
        if self.last_error is not None:
            self.last_error = public_error_text(
                self.last_error,
                "Delivery failed. Retry it or contact support with the delivery ID.",
            )
        return self


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
