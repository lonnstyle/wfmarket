# AGENTS.md

## Project Guidelines

This is a Python API wrapper for Warframe.Market built with httpx and Pydantic, following a TDD workflow using unittest and VCR.py.

## Tech Stack

- **HTTP client**: httpx (async)
- **Validation**: Pydantic v2
- **Testing**: unittest + VCR.py (record/playback)
- **Build tool**: PDM (see pyproject.toml)
- **Python requirement**: 3.10+

## Code Style

- Follow PEP 8 with 4-space indentation
- All public APIs must have type hints (use `from __future__ import annotations`)
- Package must expose `client: Client` and `Client` class in `__init__.py` with proper type annotations
- Pydantic models go in `src/wfmarket/schemas/`, organized by API version (`v1/`, `v2/`, `ws/`)
- Docstrings use Google style
- Private methods prefixed with `_`
- No bare `except:` clauses
- Use `async/await` consistently — all I/O is async

## Development Workflow (TDD)

1. Write a failing test first in the appropriate `tests/test_*.py` file
2. Record a VCR cassette for the test:
   ```bash
   VCR_RECORD_MODE=once pytest tests/test_feature.py -k test_something
   ```
3. Implement the code to make the test pass
4. Run the test again with playback mode to verify:
   ```bash
   pytest tests/test_feature.py -k test_something
   ```
5. Repeat

Cassettes live in `tests/cassettes/` and are committed to version control. Never hit the live API in tests unless recording a new cassette.

## Client Singleton Pattern

The `Client` class is a singleton. The instance is exposed directly as `wfmarket.client` on import, ensuring the global token bucket rate limiter shares state. Never instantiate `Client()` directly.

## Rate Limiting

The rate limiter uses a multi-tier token bucket:

- **Global bucket**: Shared across all endpoints
- **Per-endpoint bucket**: Separate tokens for endpoints with stricter limits

Token counts and refill rates are configured in the client. New endpoints inherit sensible defaults from the global bucket unless they have documented stricter limits.

## Caching

Manifest endpoints are cached locally to avoid redundant calls:

- `/api/py/items`
- `/api/py/markets`
- `/api/py/factions`

Cache lives in `.wfmarket_cache/` in the project root. Implement cache invalidation when manifests are known to change (e.g., after game updates).

## Exception Hierarchy

Custom exceptions in `src/wfmarket/exceptions.py`:

```
WfMarketError (base)
├── WfMarketHTTPError      # HTTP-level failures (timeout, connection)
├── WfMarketAPIError       # Non-2xx API responses
├── WfMarketValidationError # Pydantic validation failures
├── WfMarketRateLimitError # Rate limit exceeded
└── WfMarketCacheError     # Cache read/write failures
```

Always raise the most specific exception available. Never swallow exceptions silently.

## WebSocket

WebSocket support lives under `src/wfmarket/ws/`. Use `client.ws_connect()` as an async context manager:

```python
async with client.ws_connect() as ws:
    async for msg in ws.iter_messages():
        # msg is a validated Pydantic model
        ...
```

WS message models go in `src/wfmarket/schemas/ws/`.

## Adding New Endpoints

1. Add VCR test(s) with `VCR_RECORD_MODE=once`
2. Define Pydantic response models in the appropriate `schemas/` subfolder
3. Implement the method on `Client` with full type hints
4. Add the endpoint to the rate limiter if it has documented limits
5. Run `pytest` to confirm all tests pass

## CI Notes

- Tests must pass with cassette playback only (no live API calls)
- Ensure Python 3.10 compatibility
- All dependencies are pinned in pyproject.toml
