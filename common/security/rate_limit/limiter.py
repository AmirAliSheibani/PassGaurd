import hashlib

from django.core.cache import caches

from .exceptions import RateLimitExceeded


class RateLimiter:
    """
    Fixed-window rate limiter backed by Django's Redis cache.

    The limiter uses atomic cache increments where supported
    by the configured backend.
    """

    cache = caches["security"]


    @classmethod
    def _build_key(cls, *, action: str, identifier: str) -> str:
        """
        Build a privacy-safe cache key.

        User-controlled identifiers are hashed so that sensitive
        values such as usernames are not stored directly in Redis keys.
        """

        identifier_hash = hashlib.sha256(
            identifier.encode("utf-8")
        ).hexdigest()

        return f"rate-limit:{action}:{identifier_hash}"

    @classmethod
    def _increment(cls, *, action: str, identifier: str, window: int) -> int:
        """
        Automatically increment the counter for the current window.
        """
        key = cls._build_key(action=action, identifier=identifier)
        created = cls.cache.add(key, 1, timeout=window)
        if created:
            return 1
        try:
            return cls.cache.incr(key)
        except ValueError:
            created = cls.cache.add(key, 1, timeout=window)
            if created:
                return 1

            return cls.cache.incr(key)


    @classmethod
    def consume(cls, *, action: str, identifier: str, limit:int, window: int) -> int:
        """
        Consume one request from the rate-limit window.
        """
        if limit < 1:
            raise ValueError("Rate limit must be greater than zero.")

        if window < 1:
            raise ValueError("Rate-limit window must be greater than zero.")

        count = cls._increment(action=action, identifier=identifier, window=window)
        if count > limit:
            raise RateLimitExceeded(f"Rate limit exceeded for action '{action}'.")

        return count



    @classmethod
    def check(cls, *, action: str, identifier: str, limit: int) -> None:
        """
        Check whether the current counter is already at the limit.

        This method does not consume an attempt.
        It is useful for counters that should only record failures.
        """


        key = cls._build_key(
            action=action,
            identifier=identifier,
        )
        count = cls.cache.get(key, 0)
        if count >= limit:
            raise RateLimitExceeded(f"Rate limit exceeded for action '{action}'.")


    @classmethod
    def record_failure(cls, *, action: str, identifier: str, window: int) -> int:
        """
        Record one failed attempt.
        """
        if window < 1:
            raise ValueError("Rate-limit window must be greater than zero.")

        return cls._increment(action=action, identifier=identifier, window=window)


    @classmethod
    def reset(cls, *, action: str, identifier: str, ) -> None:
        """
        Reset an action's current rate-limit window.
        """

        key = cls._build_key(
            action=action,
            identifier=identifier,
        )

        cls.cache.delete(key)

