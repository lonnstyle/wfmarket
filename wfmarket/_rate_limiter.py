"""Multi-tier token bucket rate limiter for wfmarket."""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field

from wfmarket.exceptions import WfMarketRateLimitError


@dataclass
class BucketConfig:
    """Configuration for a single token bucket.

    Args:
        capacity: Maximum number of tokens the bucket can hold.
        refill_rate: Number of tokens added per second.
    """

    capacity: int
    refill_rate: float


@dataclass
class EndpointRule:
    """Rule that maps a URL prefix to a bucket configuration.

    Args:
        prefix: URL path prefix (e.g. ``/auctions/``).
        config: The bucket configuration for this prefix.
        _bucket: The actual :class:`TokenBucket` instance (internal use).
    """

    prefix: str
    config: BucketConfig
    _bucket: TokenBucket | None = field(default=None, repr=False)


class TokenBucket:
    """A single token bucket that refills over time.

    Tokens are consumed by calling :meth:`acquire`.  When the bucket is
    empty the caller is delayed until tokens refill — unless the caller
    has explicitly disabled waiting (``_wait_for_token = False``), in
    which case a :class:`~wfmarket.exceptions.WfMarketRateLimitError` is
    raised immediately.

    Args:
        capacity: Maximum number of tokens.
        refill_rate: Tokens added per second.
    """

    __slots__ = ("_last_refill", "_lock", "_tokens", "capacity", "refill_rate")

    def __init__(self, capacity: int, refill_rate: float) -> None:
        self.capacity = capacity
        self.refill_rate = refill_rate
        self._tokens = float(capacity)  # start full
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _refill(self) -> None:
        """Refill tokens based on elapsed time since last refill.

        This method is *not* thread-safe.  Callers must hold ``self._lock``.
        """
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(
            self.capacity,
            self._tokens + elapsed * self.refill_rate,
        )
        self._last_refill = now

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def acquire(self, _wait_for_token: bool = True) -> None:
        """Acquire one token from this bucket.

        If a token is immediately available the method returns without
        delay.  Otherwise the coroutine sleeps until a token is
        refilled — unless ``_wait_for_token`` is ``False``, in which
        case a :class:`~wfmarket.exceptions.WfMarketRateLimitError` is
        raised immediately.

        Args:
            _wait_for_token: When ``False`` raise instead of waiting.
                             Internal use only — not part of the public API.
        """
        async with self._lock:
            self._refill()

            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return

            if not _wait_for_token:
                raise WfMarketRateLimitError(
                    f"Token bucket exhausted (capacity={self.capacity}, refill_rate={self.refill_rate}/s)"
                )

        # Wait outside the lock so other coroutines can proceed.
        wait_time = (1.0 - self._tokens) / self.refill_rate
        await asyncio.sleep(wait_time)

        # Re-acquire and consume (lock ensures we don't race).
        async with self._lock:
            self._refill()
            self._tokens -= 1.0


class RateLimiter:
    """Multi-tier token bucket rate limiter.

    Architecture
    ------------
    Two tiers of buckets protect against excessive requests:

    1. **Global tier**: Shared across all requests to ``api.warframe.market``.
       Default: 3 requests/second, bucket size 5.

    2. **Per-endpoint tier**: Individual buckets for URL prefix groups with
       stricter limits. Example: ``/auctions/`` at 15 requests/minute.

    Tokens are consumed on request dispatch (before the HTTP call). Each
    request must acquire one token from each applicable tier. If any tier
    has no available tokens the request is delayed until tokens refill.

    429 Retry
    ---------
    When a 429 response is received:

    * Obey ``Retry-After`` header (fallback 10 s).
    * Add jitter of 0.2–1.5 s (random).
    * Delay = ``2 ** consecutive_429s`` seconds, capped at 60 s.
    * After 5 consecutive 429s a :class:`WfMarketRateLimitError` is raised.

    Manages a **global** bucket and an optional set of **per-endpoint**
    buckets. The singleton instance is exposed as
    ``wfmarket._rate_limiter.rate_limiter``.

    Args:
        global_config: Configuration for the global bucket.
    """

    def __init__(self, global_config: BucketConfig) -> None:
        self._global_bucket = TokenBucket(
            capacity=global_config.capacity,
            refill_rate=global_config.refill_rate,
        )
        self._rules: list[EndpointRule] = []
        self._consecutive_429s: int = 0

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------

    def add_rule(self, prefix: str, config: BucketConfig) -> None:
        """Add a per-endpoint rule.

        Args:
            prefix: URL path prefix to match (e.g. ``/auctions/``).
            config: Bucket configuration for this prefix.
        """
        rule = EndpointRule(prefix=prefix, config=config)
        rule._bucket = TokenBucket(
            capacity=config.capacity,
            refill_rate=config.refill_rate,
        )
        self._rules.append(rule)

    def _match_rule(self, url: str) -> EndpointRule | None:
        """Return the first ``EndpointRule`` whose prefix matches *url*.

        Args:
            url: Full request URL.

        Returns:
            Matching rule or ``None`` if no rule matches.
        """
        for rule in self._rules:
            if rule.prefix in url:
                return rule
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def acquire(self, url: str = "") -> None:
        """Acquire tokens from all applicable tiers for a request.

        The global bucket is always acquired.  If a per-endpoint rule
        matches *url* the corresponding bucket is also acquired.

        Args:
            url: The request URL (used to match per-endpoint rules).
        """
        await self._global_bucket.acquire()

        rule = self._match_rule(url)
        if rule is not None and rule._bucket is not None:
            await rule._bucket.acquire()

    async def record_429(self) -> float:
        """Record a 429 response and calculate the next delay.

        Increments the consecutive-429 counter.  Returns the delay in
        seconds for the caller to wait before retrying.  After 5
        consecutive 429s a :class:`~wfmarket.exceptions.WfMarketRateLimitError`
        is raised.

        Returns:
            Delay in seconds.
        """
        self._consecutive_429s += 1

        if self._consecutive_429s >= 5:
            raise WfMarketRateLimitError("Rate limit exceeded: 5 consecutive 429 responses")

        return self._calculate_delay()

    def record_success(self) -> None:
        """Record a successful (non-429) response, resetting the counter."""
        self._consecutive_429s = 0

    def _calculate_delay(self, retry_after: float | None = None) -> float:
        """Calculate the delay before the next retry.

        Uses ``2 ** consecutive_429s`` with a cap of 60 seconds, plus
        jitter of 0.2–1.5 seconds.  If *retry_after* is provided it
        overrides the exponential backoff value (still capped at 60 s).

        Args:
            retry_after: Value from the ``Retry-After`` header, if
                         present.

        Returns:
            Delay in seconds.
        """
        if retry_after is not None:
            delay = min(retry_after, 60.0)
        else:
            delay = min(2**self._consecutive_429s, 60.0)

        # Add jitter: random offset between 0.2 and 1.5 seconds.
        jitter = random.uniform(0.2, 1.5)
        return delay + jitter

    @property
    def consecutive_429s(self) -> int:
        """Current count of consecutive 429 responses."""
        return self._consecutive_429s


# Singleton instance — shared state across all requests.
# This is the single point of rate-limiting state.
rate_limiter = RateLimiter(global_config=BucketConfig(capacity=5, refill_rate=3.0))
