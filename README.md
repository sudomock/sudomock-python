# SudoMock Python SDK

Official Python client for the [SudoMock](https://sudomock.com) Mockup Generator API.

Generate photorealistic product mockups from PSD templates or SudoAI 2D mockups -- all from your Python code.

[![PyPI](https://img.shields.io/pypi/v/sudomock)](https://pypi.org/project/sudomock/)
[![Python](https://img.shields.io/pypi/pyversions/sudomock)](https://pypi.org/project/sudomock/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI](https://github.com/sudomock/sudomock-python/actions/workflows/ci.yml/badge.svg)](https://github.com/sudomock/sudomock-python/actions)

## Installation

```bash
pip install sudomock
```

## Quick Start

```python
from sudomock import SudoMock

# 1. Create a client (or set SUDOMOCK_API_KEY env var)
client = SudoMock(api_key="sm_your_api_key")

# 2. List your mockup templates
mockups = client.mockups.list(limit=10)
for m in mockups.mockups:
    print(f"{m.name} ({m.uuid})")

# 3. Render a mockup with your artwork
render = client.renders.create(
    mockup_uuid=mockups.mockups[0].uuid,
    smart_objects=[{
        "uuid": mockups.mockups[0].smart_objects[0].uuid,
        "asset": {"url": "https://example.com/your-design.png"},
    }],
)
print(render.url)  # https://cdn.sudomock.com/renders/.../render.webp
```

## Async Usage

```python
import asyncio
from sudomock import AsyncSudoMock

async def main():
    async with AsyncSudoMock(api_key="sm_your_api_key") as client:
        mockups = await client.mockups.list()
        render = await client.renders.create(
            mockup_uuid=mockups.mockups[0].uuid,
            smart_objects=[{
                "uuid": mockups.mockups[0].smart_objects[0].uuid,
                "asset": {"url": "https://example.com/design.png"},
            }],
        )
        print(render.url)

asyncio.run(main())
```

## SudoAI 2D Rendering

Render artwork onto a **SudoAI 2D mockup** -- a flat product photo whose print
areas were defined in the dashboard editor. List your 2D mockups, then render
into their print areas (costs 5 credits per render).

```python
from sudomock import SudoMock

client = SudoMock(api_key="sm_your_api_key")

# Find a 2D mockup and its print areas
two_d = client.ai.list()
mockup = two_d.mockups[0]

render = client.ai.render(
    mockup_uuid=mockup.mockup_id,
    print_areas=[{
        "uuid": "print-area-uuid",                 # from the 2D mockup
        "artwork_url": "https://example.com/your-design.png",
        # or a flat color: "color": "#FF0000"
    }],
)
print(render.url)

# Get / delete a 2D mockup
client.ai.get(mockup.mockup_id)
client.ai.delete(mockup.mockup_id)
```

## Async Rendering (Server-Side Queue)

Submit long-running renders to the server-side queue and poll for the result.
This is independent of `AsyncSudoMock` -- `is_async` controls *server* queueing,
while `AsyncSudoMock` only controls how *your* process performs HTTP I/O. Either
client can submit async jobs.

```python
from sudomock import SudoMock

client = SudoMock(api_key="sm_your_api_key")

# Submit -> returns a JobAccepted (HTTP 202), does not block on the render
job = client.renders.create(
    mockup_uuid="...",
    smart_objects=[{"uuid": "...", "asset": {"url": "https://example.com/d.png"}}],
    is_async=True,
)
print(job.render_uuid, job.status_url)

# Poll until terminal (succeeded / failed)
result = client.jobs.wait(job.render_uuid)        # or client.jobs.get(uuid) once
if result.succeeded:
    print(result.url)        # result_url
else:
    print("failed:", result.error)
```

## Video Rendering

Animate a mockup into an AI video. Video renders are always async (return a
`JobAccepted`). The first video render on a free plan is granted once for the
account's lifetime. `duration_seconds` must be a value allowed by the chosen
model (otherwise the API returns `422`).

```python
job = client.renders.create_video(
    mockup_uuid="...",
    smart_objects=[{"uuid": "...", "asset": {"url": "https://example.com/d.png"}}],
    duration_seconds=5,
    audio=False,
    motion="ambient",               # optional; "ambient" (default) or "showcase"
    advanced_model="veo-3.1-fast",  # optional; otherwise auto-selected by tier
)
video = client.jobs.wait(job.render_uuid)
print(video.url)

# Raw-image mode: animate a public image URL directly (no mockup render step)
job = client.renders.create_video(
    image_url="https://example.com/product.jpg",
    duration_seconds=5,
)
```

## PSD Upload

Upload a PSD by URL and parse it into a mockup template. PSD uploads are **free**
(zero credits) and support `is_async`.

```python
mockup = client.psd.upload(url="https://example.com/template.psd", name="My PSD")
print(mockup.uuid)

# Async variant:
job = client.psd.upload(url="https://example.com/template.psd", is_async=True)
mockup = client.jobs.wait(job.render_uuid)
```

## Webhooks

Manage outbound webhook endpoints (authenticated with your `x-api-key`) and
verify inbound HMAC-signed deliveries.

```python
# Register an endpoint
ep = client.webhook_endpoints.create(
    url="https://your-app.com/webhooks/sudomock",
    events=["render.succeeded", "render.failed"],
)
print(ep.secret)  # store this -- it signs deliveries

# List / update / rotate / test / replay
client.webhook_endpoints.list()
client.webhook_endpoints.update(ep.id, enabled=False)
client.webhook_endpoints.rotate_secret(ep.id)
client.webhook_endpoints.test(ep.id)
deliveries = client.webhook_endpoints.deliveries(ep.id)
client.webhook_endpoints.replay_delivery(ep.id, deliveries.deliveries[0].id)

# Cross-endpoint deliveries feed + bulk replay of all failed deliveries
client.webhook_endpoints.events(limit=100)
client.webhook_endpoints.replay_failed(ep.id)
```

Verify an inbound delivery in your handler (use the **raw** request body).
SudoMock sends the signature and timestamp in two separate headers:

```python
from sudomock import verify_webhook_signature
from sudomock.exceptions import WebhookVerificationError

signature = request.headers["X-SudoMock-Signature"]  # hex HMAC-SHA256 digest
timestamp = request.headers["X-SudoMock-Timestamp"]  # unix timestamp
try:
    verify_webhook_signature(secret, signature, timestamp, raw_body)
except WebhookVerificationError:
    ...  # reject: missing header / replayed / bad signature
```

## Error Handling

```python
from sudomock import SudoMock
from sudomock.exceptions import (
    AuthenticationError,
    InsufficientCreditsError,
    RateLimitError,
    NotFoundError,
    ValidationError,
    ServerError,
    SudoMockError,  # base class for all errors
)

client = SudoMock(api_key="sm_your_api_key")

try:
    render = client.renders.create(
        mockup_uuid="...",
        smart_objects=[...],
    )
except AuthenticationError:
    print("Invalid API key")
except InsufficientCreditsError as e:
    print(f"Out of credits. Resets at: {e.credits_reset_at}")
except RateLimitError as e:
    print(f"Rate limited. Retry after: {e.retry_after}s")
except NotFoundError:
    print("Mockup not found")
except ValidationError:
    print("Invalid request parameters")
except ServerError:
    print("Server error, will be retried automatically")
except SudoMockError as e:
    print(f"Unexpected error: {e.message} (HTTP {e.status_code})")
```

## Account & Credits

```python
from sudomock import SudoMock

client = SudoMock(api_key="sm_your_api_key")
account = client.account.get()

print(f"Plan: {account.subscription.plan}")
print(f"Credits remaining: {account.usage.credits_remaining}")
print(f"Credits limit: {account.usage.credits_limit}")
print(f"Period ends: {account.subscription.current_period_end}")
```

## Configuration

```python
from sudomock import SudoMock

client = SudoMock(
    api_key="sm_your_api_key",           # or SUDOMOCK_API_KEY env var
    base_url="https://api.sudomock.com", # default
    timeout=30.0,                         # default request timeout (seconds)
    render_timeout=120.0,                 # render request timeout (seconds)
    max_retries=3,                        # retry on 429/5xx (exponential backoff)
)
```

## API Reference

### Mockups

| Method | Description |
|--------|-------------|
| `client.mockups.list(limit=, offset=, name=, created_after=, created_before=, sort=, order=)` | List mockup templates (filter by `name`) |
| `client.mockups.get(uuid)` | Get mockup details |
| `client.mockups.update(uuid, name=)` | Rename a mockup |
| `client.mockups.delete(uuid)` | Delete a mockup |

> Bulk delete (`DELETE /mockups/all`) is dashboard-only (Bearer/JWT auth) and is intentionally not exposed in this api-key SDK.

### Renders

| Method | Description |
|--------|-------------|
| `client.renders.create(mockup_uuid=, smart_objects=, export_options=, export_label=, is_async=False)` | Render a mockup (sync `Render`, or `JobAccepted` when `is_async=True`) |
| `client.renders.create_video(mockup_uuid=, smart_objects=, image_url=, duration_seconds=, audio=False, motion=None, advanced_model=None, webhook=None, ...)` | AI video render (always async, returns `JobAccepted`). Render mode (`mockup_uuid`+`smart_objects`) or raw-image mode (`image_url`) |

### Jobs

| Method | Description |
|--------|-------------|
| `client.jobs.list(kind=, mockup_uuid=, limit=, cursor=)` | List your async jobs (keyset-paginated, newest first) |
| `client.jobs.get(render_uuid)` | Get async job status (`queued`/`running`/`succeeded`/`failed`) |
| `client.jobs.wait(render_uuid, poll_interval=2.0, timeout=300.0)` | Poll until the job reaches a terminal state |

### PSD

| Method | Description |
|--------|-------------|
| `client.psd.upload(url=, name=None, is_async=False)` | Upload a PSD by URL (free; sync `Mockup` or `JobAccepted`) |

### SudoAI 2D Mockups

| Method | Description |
|--------|-------------|
| `client.ai.render(mockup_uuid=, print_areas=, export_options=)` | Render artwork onto a 2D mockup (5 credits) |
| `client.ai.list(limit=, offset=)` | List your 2D mockups |
| `client.ai.get(mockup_id)` | Get a 2D mockup |
| `client.ai.delete(mockup_id)` | Delete a 2D mockup |

### Account

| Method | Description |
|--------|-------------|
| `client.account.get()` | Get account info, credits, subscription |

### Packages (public)

| Method | Description |
|--------|-------------|
| `client.packages.plans()` | List active subscription plans (no auth) |
| `client.packages.pricing()` | List public pricing (no auth) |

### Webhook Endpoints

| Method | Description |
|--------|-------------|
| `client.webhook_endpoints.list()` | List registered endpoints |
| `client.webhook_endpoints.create(url=, events=, description=None)` | Register an endpoint (empty `events` = all) |
| `client.webhook_endpoints.get(uuid)` | Get an endpoint |
| `client.webhook_endpoints.update(uuid, url=, events=, description=, enabled=)` | Update an endpoint |
| `client.webhook_endpoints.delete(uuid)` | Delete an endpoint |
| `client.webhook_endpoints.rotate_secret(uuid)` | Rotate the signing secret |
| `client.webhook_endpoints.test(uuid)` | Send a synthetic test delivery |
| `client.webhook_endpoints.events(status=, event_type=, limit=)` | Deliveries feed across all endpoints |
| `client.webhook_endpoints.deliveries(uuid)` | List delivery attempts for one endpoint |
| `client.webhook_endpoints.replay_delivery(uuid, delivery_id)` | Replay one failed delivery |
| `client.webhook_endpoints.replay_failed(uuid)` | Replay all failed/dead deliveries |
| `verify_webhook_signature(secret, signature, timestamp, raw_body)` | Verify an inbound HMAC signature (split headers) |

### Export Options

```python
export_options = {
    "image_format": "webp",  # "webp", "png", "jpg"
    "image_size": 1920,       # max dimension in pixels
    "quality": 95,            # 1-100 (for webp/jpg)
}
```

### Smart Object Configuration

```python
smart_objects = [{
    "uuid": "smart-object-uuid",
    "asset": {
        "url": "https://example.com/design.png",
        "fit": "fill",      # "fill" (default), "contain", "cover"
        "rotate": 0,         # degrees
        "position": {"top": 100, "left": 100},
        "size": {"width": 800, "height": 600},
    },
    "color": {
        "hex": "#FFFFFF",
        "blending_mode": "multiply",
    },
}]
```

## Requirements

- Python 3.9+
- [httpx](https://www.python-httpx.org/) for HTTP
- [Pydantic v2](https://docs.pydantic.dev/) for response models
- [tenacity](https://tenacity.readthedocs.io/) for retry logic

## License

MIT -- see [LICENSE](LICENSE).

## MCP Server

SudoMock also offers an official [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server, enabling AI assistants like Claude, Cursor, and VS Code Copilot to generate mockups directly.

- **npm package:** [@sudomock/mcp](https://www.npmjs.com/package/@sudomock/mcp)
- **Remote server:** `mcp.sudomock.com` (HTTP transport, no Node.js required)
- **Documentation:** [sudomock.com/docs/mcp](https://sudomock.com/docs/mcp)

## Links

- [SudoMock Website](https://sudomock.com)
- [API Documentation](https://docs.sudomock.com)
- [Dashboard](https://app.sudomock.com)
- [MCP Server](https://github.com/sudomock/sudomock-mcp-server)
