import hashlib

from django.core.cache import caches

from .exceptions import RateLimitExceeded


class RateLimiter:
    """
    Fixed-window rate limiter backed by Django's Redis cache.

    The limiter uses atomic cache increments where supported
    by the configured backend.
    """

    cache = caches["ratelimit"]

    KEY_PREFIX = "passguard:rate-limit"

    @classmethod
    def _build_key(
        cls,
        *,
        action: str,
        identifier: str,
    ) -> str:
        """
        Build a privacy-safe cache key.

        User-controlled identifiers are hashed so that sensitive
        values such as usernames are not stored directly in Redis keys.
        """

        identifier_hash = hashlib.sha256(
            identifier.encode("utf-8")
        ).hexdigest()

        return (
            f"{cls.KEY_PREFIX}:"
            f"{action}:"
            f"{identifier_hash}"
        )

    @classmethod
    def check(
        cls,
        *,
        action: str,
        identifier: str,
        limit: int,
        window: int,
    ) -> None:
        """
        Consume one attempt from the current fixed window.

        Raises:
            RateLimitExceeded:
                If the configured limit has been reached.
        """

        if limit < 1:
            raise ValueError("Rate limit must be greater than zero.")

        if window < 1:
            raise ValueError("Rate-limit window must be greater than zero.")

        key = cls._build_key(
            action=action,
            identifier=identifier,
        )

        created = cls.cache.add(
            key,
            1,
            timeout=window,
        )

        if created:
            return

        try:
            current_count = cls.cache.incr(key)
        except ValueError:
            # The key may have expired between add() and incr().
            # Start a fresh window.
            created = cls.cache.add(
                key,
                1,
                timeout=window,
            )

            if created:
                return

            current_count = cls.cache.incr(key)

        if current_count > limit:
            raise RateLimitExceeded(
                f"Rate limit exceeded for action '{action}'."
            )

    @classmethod
    def reset(
        cls,
        *,
        action: str,
        identifier: str,
    ) -> None:
        """
        Reset an action's current rate-limit window.
        """

        key = cls._build_key(
            action=action,
            identifier=identifier,
        )

        cls.cache.delete(key)