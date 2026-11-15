# wfmarket

> **W**ar**F**rame **M**arket **A**PI **R**esource **K**it for **E**xchange and **T**rade

A lightweight, asynchronous Python API wrapper for Warframe.Market with built-in schema validation, multi-tier rate limiting, and JWT authentication.

## Features

- **Multi-version support**: Full coverage of API v2 (primary)
- **WebSocket real-time updates**: Planned — discriminated union message dispatch (TODO)
- **Schema validation**: Pydantic models for request/response validation and type safety
- **Rate limiting**: Self-implemented multi-tier global token bucket algorithm to respect API limits
- **Singleton client**: Single shared instance ensures rate limit state is consistent across all requests
- **Local caching**: Manifest data (e.g. items, riven weapons) is cached locally to eliminate redundant API calls
- **HTTP client**: Powered by httpx for modern, async-first HTTP operations
- **TDD workflow**: Built with unittest + VCR.py for deterministic, record-and-replay testing

## API Coverage

| API Version | Status | Endpoints |
|-------------|--------|-----------|
| v2 | **Primary** | Listings, Orders, Stats, User endpoints |
| v1 | Not implemented | Legacy endpoints — not yet supported |
| WebSocket | **TODO** | Real-time listing updates, order events |

## Architecture

### Client Singleton

The `Client` instance is exposed directly on import as `wfmarket.client`. A single shared instance ensures the global token bucket rate limiter maintains consistent state across the application.

### Rate Limiting

A multi-tier token bucket algorithm handles Warframe.Market's rate limits:

- **Global tier**: Shared across all requests (bucket size & refill rate)
- **Per-endpoint tier**: Individual buckets for endpoints with stricter limits
- Tokens are consumed on request dispatch and refilled at a configured rate

### Caching

Manifest endpoints are cached locally using a file-based cache (`.wfmarket_cache/`). Cache invalidation is driven by comparing collection hashes from `/v2/versions` against stored hashes.

**Cached manifests:**

- `/v2/items`
- `/v2/riven/weapons`
- `/v2/riven/attributes`
- `/v2/liches`
- `/v2/sisters`
- `/v2/missions`
- `/v2/npcs`
- `/v2/locations`

### Schema Validation

All API responses are validated against Pydantic models. Invalid or unexpected responses raise structured exceptions defined in `wfmarket.exceptions`.

## Testing

The project follows a TDD workflow using `unittest` and `VCR.py` for HTTP recording. VCR cassettes are stored in `tests/cassettes/` and capture real API responses for deterministic test runs without hitting Warframe.Market during CI.

## Project Structure

Planned layout (implementation in progress):

```
src/wfmarket/
├── __init__.py      # Package exports
├── client.py        # Singleton Client class with rate limiter & cache
├── exceptions.py    # Custom exception hierarchy
├── schemas/         # Pydantic models for v1, v2, WS messages
├── rate_limit.py    # Multi-tier token bucket implementation
├── cache.py         # Local manifest caching layer
└── ws/              # WebSocket client and message handlers
tests/
├── cassettes/       # VCR.py recorded fixtures
├── test_client.py
└── test_*.py
```

## License

See [LICENSE](LICENSE) for details.
