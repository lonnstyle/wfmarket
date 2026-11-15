---
name: rate-limiting
description: "Implement the self-implemented, multi-tier token bucket rate limiter decorator for the wfmarket async API client. Use when building rate-limited API methods, configuring per-endpoint limits, or testing rate limiting behavior."
---

Implement a self-implemented, multi-tier token bucket rate limiter for the Warframe.Market API wrapper. No external rate-limiting libraries — everything built from scratch using standard library + httpx.

## Architecture Overview

The rate limiter uses a **multi-tier token bucket** algorithm with two tiers:

1. **Global tier**: Shared across all requests to `api.warframe.market`. Default: 3 requests/second, bucket size 5, refill rate 3 tokens/second.
2. **Per-endpoint tier**: Individual buckets for URL prefix groups with stricter limits. Examples: `auctions/` at 15 requests/minute (bucket size 15, refill rate 0.25 tokens/second).

Tokens consumed on request dispatch (before HTTP call). Each request must acquire one token from each applicable tier. If any tier has no available tokens, the request is delayed until tokens refill.

### Design principles

- **Singleton**: Rate limiter state lives on the `Client` instance. Never instantiate separately.
- **No external deps**: Pure Python using `asyncio.Lock` for concurrency safety and `time.monotonic()` for time tracking.
- **Async-first**: All I/O is async. Limiter uses `async/await`.
- **Fail open, fail loudly**: If limiter crashes internally, log a warning and let the request proceed. If a request would be rate-limited, raise `WfMarketRateLimitError`.
- **Transparent**: Limiter sits between caller and httpx. Methods don't need to know about it — applied via a decorator or middleware pattern.

## Token Bucket Implementation

### `class TokenBucket`

```python
from __future__ import annotations
import time
import asyncio
from dataclasses import dataclass, field

@dataclass(frozen=True)
class BucketConfig:
    """Immutable configuration for a single token bucket."""
    max_tokens: int          # Bucket capacity
    refill_rate: float       # Tokens added per second

class TokenBucket:
    """
    A single token bucket with async-safe token acquisition.

    Uses `asyncio.Lock` to prevent concurrent state corruption and
    `time.monotonic()` for drift-free time tracking.
    """

    def __init__(self, config: BucketConfig) -> None:
        self._config = config
        self._tokens = float(config.max_tokens)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        """Refill tokens based on elapsed time. Must be called with lock held."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(
            float(self._config.max_tokens),
            self._tokens + elapsed * self._config.refill_rate,
        )
        self._last_refill = now

    async def acquire(self, tokens: int = 1) -> None:
        """
        Acquire tokens, awaiting until they are available.

        Raises `WfMarketRateLimitError` if the config allows zero refill.
        """
        async with self._lock:
            while True:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                # Calculate wait time for enough tokens
                deficit = tokens - self._tokens
                wait_time = deficit / self._config.refill_rate if self._config.refill_rate > 0 else 0
                if self._config.refill_rate == 0:
                    from wfmarket.exceptions import WfMarketRateLimitError
                    raise WfMarketRateLimitError(
                        f"Endpoint rate limit exceeded: no refill rate configured"
                    )
                # Release lock while waiting
                self._lock.release()
                try:
                    await asyncio.sleep(wait_time)
                finally:
                    await self._lock.acquire()
```

### `class RateLimiter`

```python
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from wfmarket.exceptions import WfMarketRateLimitError


@dataclass
class EndpointRule:
    """A rate limit rule tied to a URL prefix pattern."""
    pattern: str                # URL path prefix, e.g. "auctions/"
    config: BucketConfig

    def matches(self, path: str) -> bool:
        """Check if a URL path starts with this rule's pattern."""
        return path.startswith(self.pattern)


class RateLimiter:
    """
    Multi-tier token bucket rate limiter for the wfmarket client.

    Maintains a global bucket shared by all requests and per-endpoint
    buckets keyed by URL prefix patterns.

    Usage (on the Client class):

        self._rate_limiter = RateLimiter()
        self._rate_limiter.global_config = BucketConfig(max_tokens=5, refill_rate=3.0)
        self._rate_limiter.add_endpoint_rule(
            EndpointRule("auctions/", BucketConfig(max_tokens=15, refill_rate=0.25))
        )
    """

    def __init__(self) -> None:
        self._global_bucket = TokenBucket(BucketConfig(max_tokens=5, refill_rate=3.0))
        self._endpoint_rules: list[EndpointRule] = []

    def add_endpoint_rule(self, rule: EndpointRule) -> None:
        """Register a per-endpoint rate limit rule."""
        self._endpoint_rules.append(rule)

    def _find_bucket(self, path: str) -> TokenBucket | None:
        """Find the matching endpoint bucket for a given URL path."""
        for rule in self._endpoint_rules:
            if rule.matches(path):
                return TokenBucket(rule.config)  # We need per-rule bucket instances
        return None

    async def limit(self, path: str) -> None:
        """
        Acquire tokens from all applicable tiers for the given path.

        Raises `WfMarketRateLimitError` if tokens cannot be acquired.
        """
        await self._global_bucket.acquire()
        # Per-endpoint bucket lookup requires mutable per-rule storage
        # See design note: we store buckets on EndpointRule or in a separate dict
        for rule in self._endpoint_rules:
            if rule.matches(path):
                await rule._bucket.acquire()  # rule._bucket is a TokenBucket instance
```

### Key design notes

1. **Per-rule bucket instances**: Each `EndpointRule` should own its own `TokenBucket` instance, not create one on-the-fly. Add a `_bucket` field to `EndpointRule` initialized in `add_endpoint_rule`.

2. **Decorator pattern**: Use an async decorator to wrap client methods:

```python
def rate_limited(self, path: str) -> Callable[[Callable], Callable]:
    """Decorator that applies rate limiting to an endpoint method."""
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            await self._rate_limiter.limit(path)
            return await func(*args, **kwargs)
        return wrapper
    return decorator
```

3. **Usage in Client methods**:

```python
@self.rate_limited("listings/")
async def get_listings(self) -> List[Listing]:
    response = await self._http.get("/api/warframe-market/listings/")
    # ...
```

## Exception

`WfMarketRateLimitError` is defined in `wfmarket/exceptions.py`. It inherits from `WfMarketError` (base class). Import it from `wfmarket.exceptions`.

## Testing

1. Write tests first in `tests/cases/test_rate_limiter.py` using `unittest`.
2. No HTTP calls needed — test the limiter logic in isolation with `time.monotonic()` mocking if needed.
3. Record cassettes in `tests/cassettes/` for integration-level tests that exercise the decorator on real client methods.

## Reference: AGENTS.md

The `AGENTS.md` file at the project root documents this rate limiting architecture. Always cross-reference it when implementing changes.
