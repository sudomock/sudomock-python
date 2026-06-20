"""Pydantic v2 response models for the SudoMock API.

All models use ``model_config = {"extra": "allow"}`` so that new fields
added to the API do not break existing SDK versions.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TCH003 - Pydantic needs this at runtime
from typing import Any, Optional

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
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False


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
    """A single rendered output file."""

    export_path: str
    smart_object_uuid: str

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
# AI render
# ---------------------------------------------------------------------------


class AIRender(_Base):
    """Result of an AI render request."""

    print_files: list[PrintFile] = Field(default_factory=list)
    # AI renders may include extra metadata (segment info, etc.)

    @property
    def url(self) -> str:
        """Shortcut: URL of the first print file."""
        if not self.print_files:
            raise ValueError("AI render contains no print files")
        return self.print_files[0].url


# ---------------------------------------------------------------------------
# Async jobs (is_async renders / uploads / video)
# ---------------------------------------------------------------------------


class JobAccepted(_Base):
    """Acknowledgement returned by a ``202 Accepted`` async submission.

    Returned by ``renders.create(..., is_async=True)``, ``psd.upload(...,
    is_async=True)`` and ``renders.create_video(...)``. Poll for completion
    with :meth:`jobs.get` (or :meth:`jobs.wait` / ``wait_for_job``) using
    :attr:`render_uuid`.
    """

    render_uuid: str
    kind: Optional[str] = None
    status: Optional[str] = None
    status_url: Optional[str] = None


class Job(_Base):
    """Status of an async job from ``GET /api/v1/jobs/{render_uuid}``.

    The terminal states are ``"succeeded"`` and ``"failed"``; ``"queued"``
    and ``"running"`` are non-terminal.
    """

    state: str
    result_url: Optional[str] = None
    mockup_uuid: Optional[str] = None
    cost: Optional[float] = None
    credits: Optional[int] = None
    model: Optional[str] = None
    error: Optional[str] = None
    payg: Optional[bool] = None

    # Terminal-state helpers ------------------------------------------------

    @property
    def is_terminal(self) -> bool:
        """True once the job has reached a terminal state."""
        return self.state in ("succeeded", "failed")

    @property
    def succeeded(self) -> bool:
        """True if the job finished successfully."""
        return self.state == "succeeded"

    @property
    def failed(self) -> bool:
        """True if the job failed."""
        return self.state == "failed"

    @property
    def url(self) -> str:
        """Shortcut: the result URL (only available once succeeded)."""
        if not self.result_url:
            raise ValueError(
                f"Job has no result_url (state={self.state!r}); "
                "it may not have succeeded yet"
            )
        return self.result_url


# ---------------------------------------------------------------------------
# Video render
# ---------------------------------------------------------------------------


class VideoOptions(_Base):
    """Video generation options for ``renders.create_video``.

    Attributes:
        duration_seconds: Clip length; must be in the chosen model's allowed
            set or the API returns ``422``.
        audio: Whether to generate audio (default off).
        advanced_model: Optional model override (otherwise auto-selected by
            tier). When omitted the API picks the default for your plan.
    """

    duration_seconds: int
    audio: bool = False
    advanced_model: Optional[str] = None


# ---------------------------------------------------------------------------
# Webhook endpoints
# ---------------------------------------------------------------------------


class WebhookEndpoint(_Base):
    """A registered outbound webhook endpoint."""

    uuid: str
    url: str
    events: list[str] = Field(default_factory=list)
    enabled: bool = True
    secret: Optional[str] = None
    created_at: Optional[datetime] = None


class WebhookEndpointList(_Base):
    """List of registered webhook endpoints."""

    webhook_endpoints: list[WebhookEndpoint] = Field(default_factory=list)


class WebhookSecret(_Base):
    """Result of rotating a webhook signing secret."""

    secret: str


class WebhookDelivery(_Base):
    """A single delivery attempt for a webhook endpoint."""

    uuid: str
    event_type: Optional[str] = None
    status: Optional[str] = None
    response_status: Optional[int] = None
    created_at: Optional[datetime] = None


class WebhookDeliveryList(_Base):
    """List of delivery attempts for a webhook endpoint."""

    deliveries: list[WebhookDelivery] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Generic API envelope
# ---------------------------------------------------------------------------


class ApiResponse(_Base):
    """Generic ``{success, data}`` wrapper returned by all endpoints."""

    success: bool
    data: Optional[dict[str, Any]] = None
