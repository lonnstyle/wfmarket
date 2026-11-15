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

- **Global bucket**: 3 requests/second across all generic API endpoints
- **Per-endpoint bucket**: Separate tokens for endpoints with stricter limits (e.g., `/auction/search` is 15 requests/minute, subject to change)

Per-endpoint requests are also counted against the global bucket — you cannot exceed 3 req/s overall even if fewer requests hit the restricted endpoint. Token counts and refill rates are configured in the client. New endpoints inherit sensible defaults from the global bucket unless they have documented stricter limits.

## Caching

Manifest endpoints are cached locally to avoid redundant calls. Cache lives in `.wfmarket_cache/` in the project root. Cache invalidation is driven by comparing collection hashes from `/v2/versions` against stored hashes, and optionally by checking the `updatedAt` timestamp (ISO format string).

Cached manifests:

- `/v2/items`
- `/v2/riven/weapons`
- `/v2/riven/attributes`
- `/v2/liches`
- `/v2/sisters`
- `/v2/missions`
- `/v2/npcs`
- `/v2/locations`

## Authentication

Current auth uses JWT. OAuth 2.0 is planned but not yet implemented.

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

## Agent skills

### Issue tracker

Issues are tracked in GitHub Issues via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout: `GLOSSARY.md` at root, `docs/adr/` for architecture decisions. See `docs/agents/domain.md`.

### TDD

Test-driven development (red → green loop). See `.agents/skills/tdd/SKILL.md`.

### TDD extra

Supplement to TDD for test environment modes: local dev site vs CI/cassette. See `.agents/skills/tdd-extra/SKILL.md`.

### Pydantic schemas

Pydantic V2 data model patterns for response/request models. See `.agents/skills/pydantic-schemas/SKILL.md`.

### Rate limiting

Multi-tier token bucket rate limiter (global + per-endpoint) implemented from scratch. See `.agents/skills/rate-limiting/SKILL.md`.
