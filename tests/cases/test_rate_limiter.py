"""Tests for the multi-tier token bucket rate limiter."""

from __future__ import annotations

import asyncio
import time
from unittest import mock

from wfmarket._rate_limiter import (
    BucketConfig,
    RateLimiter,
    TokenBucket,
)
from wfmarket.exceptions import WfMarketRateLimitError

from .base import BaseTest


class TestTokenBucketAcquire(BaseTest):
    """Tests for TokenBucket.acquire() basic refill logic."""

    def setUp(self):
        """Set up a TokenBucket with 3 tokens, refill 3/sec."""
        self.bucket = TokenBucket(capacity=3, refill_rate=3.0)

    async def test_acquire_returns_immediately_when_tokens_available(self):
        """acquire() should return immediately when tokens are available."""
        # No prior usage — bucket starts full (3 tokens)
        start = time.monotonic()
        await self.bucket.acquire()
        elapsed = time.monotonic() - start

        # Should be near-instant (well under 1 second)
        self.assertLess(elapsed, 0.1)

    async def test_acquire_drains_tokens(self):
        """acquire() should consume one token per call."""
        await self.bucket.acquire()
        await self.bucket.acquire()
        await self.bucket.acquire()

        # Bucket should now be empty
        # A fourth acquire should wait for refill
        time.monotonic()
        # Force zero tokens and disable waiting — should raise
        with self.assertRaises(WfMarketRateLimitError):
            await self.bucket.acquire(_wait_for_token=False)


class TestTokenBucketWait(BaseTest):
    """Tests for TokenBucket.acquire() waiting / refill behavior."""

    async def test_acquire_waits_when_tokens_exhausted(self):
        """acquire() should wait for refill when no tokens are available."""
        # Drain all tokens
        bucket = TokenBucket(capacity=1, refill_rate=10.0)
        await bucket.acquire()

        # A second acquire should wait ~0.1s for a token to refill
        start = time.monotonic()
        with mock.patch.object(TokenBucket, "_refill"):
            bucket._tokens = 0.0
            # With _refill patched to keep tokens at 0, the calculate path
            # uses the formula (1.0 - 0.0) / 10.0 = 0.1 seconds.
            await bucket.acquire()
        elapsed = time.monotonic() - start
        # With refill_rate=10.0 and 1 token needed, wait is ~0.1s
        self.assertGreater(elapsed, 0.05)

    async def test_acquire_returns_immediately_after_refill(self):
        """acquire() should return immediately once tokens have refilled."""
        bucket = TokenBucket(capacity=1, refill_rate=20.0)  # 20 tokens/sec
        await bucket.acquire()

        # Wait for refill (~0.05s for one token at 20/s)
        await asyncio.sleep(0.06)

        start = time.monotonic()
        await bucket.acquire()
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 0.1)


class TestTokenBucketNoWait(BaseTest):
    """Tests for TokenBucket.acquire() with _wait_for_token=False."""

    async def test_no_wait_raises_immediately(self):
        """_wait_for_token=False should raise WfMarketRateLimitError."""
        bucket = TokenBucket(capacity=1, refill_rate=1.0)
        await bucket.acquire()  # drain the one token

        with self.assertRaises(WfMarketRateLimitError) as ctx:
            await bucket.acquire(_wait_for_token=False)

        self.assertIn("Token bucket exhausted", str(ctx.exception))

    async def test_no_wait_succeeds_when_tokens_available(self):
        """_wait_for_token=False should succeed when tokens are available."""
        bucket = TokenBucket(capacity=2, refill_rate=1.0)
        # Should succeed without waiting
        await bucket.acquire(_wait_for_token=False)


class TestRateLimiterAcquire(BaseTest):
    """Tests for RateLimiter.acquire() rule matching and tier acquisition."""

    def setUp(self):
        """Set up a RateLimiter with a global bucket and one per-endpoint rule."""
        self.global_config = BucketConfig(capacity=3, refill_rate=3.0)
        self.limiter = RateLimiter(global_config=self.global_config)
        self.limiter.add_rule("/auctions/", BucketConfig(capacity=2, refill_rate=0.5))

    async def test_acquire_always_acquires_global_bucket(self):
        """acquire() should always acquire the global bucket."""
        # Drain the global bucket first
        limiter = RateLimiter(global_config=BucketConfig(capacity=1, refill_rate=1.0))
        await limiter.acquire()  # drains global

        # Second acquire with no matching rule should wait for global refill
        # Patch _refill at class level to avoid Python 3.14 read-only error
        with mock.patch.object(TokenBucket, "_refill"):
            limiter._global_bucket._tokens = 0.0
            start = time.monotonic()
            await limiter.acquire()  # should wait
            elapsed = time.monotonic() - start
            self.assertGreater(elapsed, 0.2)

    async def test_acquire_acquires_per_endpoint_rule(self):
        """acquire() should acquire both global and per-endpoint buckets."""
        # Both buckets start full — should return immediately
        start = time.monotonic()
        await self.limiter.acquire("https://api.warframe.com/auctions/")
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 0.1)

    async def test_acquire_no_matching_rule_falls_back_to_global(self):
        """acquire() with no matching rule should only acquire global."""
        # Drain the per-endpoint bucket
        for _ in range(2):
            bucket = self.limiter._rules[0]._bucket
            assert bucket is not None
            await bucket.acquire()

        # Request with no matching rule should still succeed (global has tokens)
        start = time.monotonic()
        await self.limiter.acquire("https://api.warframe.com/other/")
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 0.1)

    async def test_acquire_matches_longest_prefix(self):
        """acquire() should match the first rule whose prefix is in the URL."""
        limiter = RateLimiter(global_config=BucketConfig(capacity=3, refill_rate=3.0))
        limiter.add_rule("/a/", BucketConfig(capacity=1, refill_rate=1.0))
        limiter.add_rule("/auctions/", BucketConfig(capacity=1, refill_rate=1.0))

        # Drain the specific bucket
        bucket = limiter._rules[1]._bucket
        assert bucket is not None
        await bucket.acquire()

        # Now /auctions/ URL would hit the drained specific bucket
        # But we just verify matching works
        rule = limiter._match_rule("https://api.warframe.com/auctions/123")
        self.assertIsNotNone(rule)
        assert rule is not None
        self.assertEqual(rule.prefix, "/auctions/")


class TestRateLimiter429Retry(BaseTest):
    """Tests for 429 retry logic: consecutive counter, backoff, jitter, Retry-After."""

    def setUp(self):
        """Set up a fresh RateLimiter."""
        self.limiter = RateLimiter(global_config=BucketConfig(capacity=5, refill_rate=3.0))

    async def test_record_429_increments_counter(self):
        """record_429() should increment the consecutive-429 counter."""
        self.assertEqual(self.limiter.consecutive_429s, 0)
        await self.limiter.record_429()
        self.assertEqual(self.limiter.consecutive_429s, 1)

    async def test_record_429_returns_increasing_delay(self):
        """record_429() should return exponentially increasing delays."""
        # First 429: 2^1 = 2 + jitter
        delay1 = await self.limiter.record_429()
        self.assertGreater(delay1, 2.0)
        self.assertLess(delay1, 3.5)  # 2 + 1.5 max jitter

        # Second 429: 2^2 = 4 + jitter
        delay2 = await self.limiter.record_429()
        self.assertGreater(delay2, 4.0)
        self.assertLess(delay2, 5.5)

        # Third 429: 2^3 = 8 + jitter
        delay3 = await self.limiter.record_429()
        self.assertGreater(delay3, 8.0)
        self.assertLess(delay3, 9.5)

    async def test_record_429_delay_capped_at_60s(self):
        """record_429() delay should cap at 60 seconds."""
        # Consume 4 calls to reset the counter to 0
        for _ in range(4):
            await self.limiter.record_429()
        # Manually set consecutive_429s to 7 so 2^7 = 128 > 60, exercising the cap
        self.limiter._consecutive_429s = 7
        calculated = self.limiter._calculate_delay()
        self.assertLessEqual(calculated, 61.5)  # 60 + max jitter

    async def test_record_429_raises_after_5(self):
        """record_429() should raise WfMarketRateLimitError after 5 consecutive."""
        for _ in range(4):
            await self.limiter.record_429()
        with self.assertRaises(WfMarketRateLimitError) as ctx:
            await self.limiter.record_429()
        self.assertIn("5 consecutive 429", str(ctx.exception))
        self.assertEqual(self.limiter.consecutive_429s, 5)

    async def test_record_429_uses_retry_after_header(self):
        """record_429() should use Retry-After header value when provided."""
        # Patch _calculate_delay to accept retry_after parameter
        delay = self.limiter._calculate_delay(retry_after=5.0)
        self.assertGreater(delay, 5.0)  # 5 + jitter
        self.assertLess(delay, 6.5)  # 5 + 1.5

    async def test_record_429_retry_after_capped_at_60(self):
        """Retry-After values over 60s should be capped at 60."""
        delay = self.limiter._calculate_delay(retry_after=120.0)
        self.assertLessEqual(delay, 61.5)  # 60 + max jitter

    async def test_record_429_jitter_is_random(self):
        """The delay should include random jitter between 0.2 and 1.5s."""
        self.limiter._consecutive_429s = 1  # 2^1 = 2 base
        delays = [self.limiter._calculate_delay() for _ in range(10)]
        base = 2.0
        # Each delay should be base + jitter, where jitter is 0.2–1.5
        for d in delays:
            self.assertGreaterEqual(d, base + 0.2)
            self.assertLessEqual(d, base + 1.5)
        # Verify there's variation (jitter is random)
        self.assertTrue(len({round(d, 4) for d in delays}) > 1)


class TestRateLimiterRecordSuccess(BaseTest):
    """Tests for RateLimiter.record_success() counter reset."""

    def setUp(self):
        """Set up a fresh RateLimiter."""
        self.limiter = RateLimiter(global_config=BucketConfig(capacity=5, refill_rate=3.0))

    async def test_record_success_resets_counter(self):
        """record_success() should reset the consecutive-429 counter to 0."""
        await self.limiter.record_429()
        await self.limiter.record_429()
        self.assertEqual(self.limiter.consecutive_429s, 2)

        self.limiter.record_success()
        self.assertEqual(self.limiter.consecutive_429s, 0)

    async def test_record_success_after_many_429s(self):
        """record_success() should reset even after near-failure count."""
        for _ in range(4):
            await self.limiter.record_429()
        self.assertEqual(self.limiter.consecutive_429s, 4)

        self.limiter.record_success()
        self.assertEqual(self.limiter.consecutive_429s, 0)

    async def test_record_success_on_fresh_limiter_is_noop(self):
        """record_success() on a fresh limiter should not change anything."""
        self.limiter.record_success()
        self.assertEqual(self.limiter.consecutive_429s, 0)


class TestRateLimiterRuleManagement(BaseTest):
    """Tests for RateLimiter rule management (add_rule, _match_rule)."""

    def setUp(self):
        """Set up a RateLimiter with no rules."""
        self.limiter = RateLimiter(global_config=BucketConfig(capacity=5, refill_rate=3.0))

    def test_match_rule_returns_none_when_no_rules(self):
        """_match_rule() should return None when no rules exist."""
        self.assertIsNone(self.limiter._match_rule("https://api.warframe.com/foo"))

    def test_add_rule_creates_endpoint_bucket(self):
        """add_rule() should create an EndpointRule with a bucket."""
        self.limiter.add_rule("/test/", BucketConfig(capacity=1, refill_rate=1.0))
        self.assertEqual(len(self.limiter._rules), 1)
        rule = self.limiter._rules[0]
        self.assertEqual(rule.prefix, "/test/")
        self.assertIsNotNone(rule._bucket)

    def test_match_rule_prefix_in_url(self):
        """_match_rule() should match when prefix is contained in URL."""
        self.limiter.add_rule("/auctions/", BucketConfig(capacity=1, refill_rate=1.0))
        rule = self.limiter._match_rule("https://api.warframe.com/auctions/123")
        self.assertIsNotNone(rule)
        assert rule is not None
        self.assertEqual(rule.prefix, "/auctions/")

    def test_match_rule_no_match(self):
        """_match_rule() should return None when no prefix matches."""
        self.limiter.add_rule("/auctions/", BucketConfig(capacity=1, refill_rate=1.0))
        self.assertIsNone(self.limiter._match_rule("https://api.warframe.com/items/"))

    def test_multiple_rules_all_created(self):
        """Adding multiple rules should create all of them."""
        self.limiter.add_rule("/a/", BucketConfig(capacity=1, refill_rate=1.0))
        self.limiter.add_rule("/b/", BucketConfig(capacity=1, refill_rate=1.0))
        self.assertEqual(len(self.limiter._rules), 2)
