from django.core.cache import caches
from django.test import SimpleTestCase

from common.security.rate_limit.exceptions import RateLimitExceeded
from common.security.rate_limit.limiter import RateLimiter


class RateLimiterTests(SimpleTestCase):
    """
    Tests the fixed-window rate limiter using the configured security cache backend.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cache = caches['security']

    def setUp(self):
        self.cache.clear()

    def tearDown(self):
        self.cache.clear()

    def test_consume_allows_requests_until_limit(self):
        for _ in range(3):
            count = RateLimiter.consume(
                action="test",
                identifier="user-1",
                limit=3,
                window=60
            )

            self.assertLessEqual(count, 3)

    def test_consume_blocks_request_after_limit(self):
        for _ in range(3):
            RateLimiter.consume(
                action="test",
                identifier="user-1",
                limit=3,
                window=60
            )

        with self.assertRaises(RateLimitExceeded):
            RateLimiter.consume(
                action="test",
                identifier="user-1",
                limit=3,
                window=60
            )

    def test_different_identifiers_have_independent_counters(self):
        for _ in range(3):
            RateLimiter.consume(
                action="test",
                identifier="user-1",
                limit=3,
                window=60
            )

        count = RateLimiter.consume(
            action="test",
            identifier="user-2",
            limit=3,
            window=60
        )

        self.assertEqual(count, 1)

    def test_check_blocks_when_limit_has_been_reached(self):
        for _ in range(3):
            RateLimiter.record_failure(
                action="test",
                identifier="user-1",
                window=60
            )

        with self.assertRaises(RateLimitExceeded):
            RateLimiter.check(
                action="test",
                identifier="user-1",
                limit=3
            )

    def test_reset_clears_rate_limit(self):
        RateLimiter.record_failure(
            action="test",
            identifier="user-1",
            window=60
        )

        RateLimiter.reset(
            action="test",
            identifier="user-1",
        )

        RateLimiter.check(
            action="test",
            identifier="user-1",
            limit=1,
        )

