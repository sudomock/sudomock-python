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
# Generic API envelope
# ---------------------------------------------------------------------------


class ApiResponse(_Base):
    """Generic ``{success, data}`` wrapper returned by all endpoints."""

    success: bool
    data: Optional[dict[str, Any]] = None
