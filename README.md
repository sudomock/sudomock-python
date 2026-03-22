# SudoMock Python SDK

Official Python client for the [SudoMock](https://sudomock.com) Mockup Generator API.

Generate photorealistic product mockups from PSD templates or AI-powered rendering -- all from your Python code.

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

## AI Rendering (No PSD Required)

```python
from sudomock import SudoMock

client = SudoMock(api_key="sm_your_api_key")

# AI automatically detects the print area and applies perspective
render = client.ai.render(
    source_url="https://example.com/product-photo.jpg",
    artwork_url="https://example.com/your-design.png",
    product_type="t-shirt",  # optional hint
)
print(render.url)
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
| `client.mockups.list(limit=, offset=, search=)` | List mockup templates |
| `client.mockups.get(uuid)` | Get mockup details |
| `client.mockups.delete(uuid)` | Delete a mockup |

### Renders

| Method | Description |
|--------|-------------|
| `client.renders.create(mockup_uuid=, smart_objects=, export_options=, export_label=)` | Render a mockup |

### AI

| Method | Description |
|--------|-------------|
| `client.ai.render(source_url=, artwork_url=, product_type=, ...)` | AI-powered render |

### Account

| Method | Description |
|--------|-------------|
| `client.account.get()` | Get account info, credits, subscription |

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
        "fit": "fill",      # "fill", "fit", "stretch"
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
