from django.core.cache import cache

from .exceptions import RateLimitExceeded

class RateLimiter:
    """
    Lightweight application-level rate limiter backed by Django cache.

    The limiter is intentionally independent from HTTP/View logic.
    """
    KEY_PREFIX = 'rate_limit'

    @classmethod
    def built_key(cls, *, action:str, identifier:str) -> str:
        return f'{cls.KEY_PREFIX}/{action}/{identifier}'


    @classmethod
    def check(cls, *, action:str, identifier:str, limit:int, window:int) -> None:
        key = cls.built_key(action=action, identifier=identifier)

        current_count = cache.get(key, 0)

        if current_count >= limit:
            ttl = c


