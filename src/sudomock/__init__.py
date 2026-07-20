"""SudoMock Python SDK -- official client for the SudoMock Mockup Generator API.

Quick start::

    from sudomock import SudoMock

    client = SudoMock(api_key="sm_xxx")
    mockups = client.mockups.list()
    render = client.renders.create(
        mockup_uuid=mockups.mockups[0].uuid,
        smart_objects=[{
            "uuid": mockups.mockups[0].smart_objects[0].uuid,
            "asset": {"url": "https://example.com/design.png"},
        }],
    )
    print(render.url)

For async usage::

    from sudomock import AsyncSudoMock

    async with AsyncSudoMock(api_key="sm_xxx") as client:
        mockups = await client.mockups.list()
"""

from __future__ import annotations

import importlib.metadata

from .async_client import AsyncSudoMock
from .client import SudoMock
from .exceptions import (
    AuthenticationError,
    InsufficientCreditsError,
    JobFailedError,
    JobTimeoutError,
    NotFoundError,
    RateLimitError,
    ServerError,
    SudoMockError,
    ValidationError,
    WebhookVerificationError,
)
from .models import (
    Account,
    AccountInfo,
    AIRender,
    ApiKeyInfo,
    Job,
    JobAccepted,
    JobList,
    Mockup,
    MockupList,
    Plan,
    PlanList,
    PrintFile,
    Quad,
    Render,
    Size,
    SmartObject,
    Subscription,
    TwoDMockup,
    TwoDMockupList,
    TwoDPrintAreasUpdate,
    Usage,
    VideoOptions,
    WebhookDelivery,
    WebhookDeliveryList,
    WebhookEndpoint,
    WebhookEndpointList,
    WebhookSecret,
)
from .webhooks import verify_webhook_signature

try:
    __version__ = importlib.metadata.version("sudomock")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0-dev"

__all__ = [
    # Clients
    "SudoMock",
    "AsyncSudoMock",
    # Models
    "Account",
    "AccountInfo",
    "AIRender",
    "ApiKeyInfo",
    "Job",
    "JobAccepted",
    "JobList",
    "Mockup",
    "MockupList",
    "Plan",
    "PlanList",
    "PrintFile",
    "Quad",
    "Render",
    "Size",
    "SmartObject",
    "Subscription",
    "TwoDMockup",
    "TwoDMockupList",
    "TwoDPrintAreasUpdate",
    "Usage",
    "VideoOptions",
    "WebhookDelivery",
    "WebhookDeliveryList",
    "WebhookEndpoint",
    "WebhookEndpointList",
    "WebhookSecret",
    # Webhooks
    "verify_webhook_signature",
    # Exceptions
    "SudoMockError",
    "AuthenticationError",
    "InsufficientCreditsError",
    "JobFailedError",
    "JobTimeoutError",
    "NotFoundError",
    "RateLimitError",
    "ServerError",
    "ValidationError",
    "WebhookVerificationError",
    # Meta
    "__version__",
]
