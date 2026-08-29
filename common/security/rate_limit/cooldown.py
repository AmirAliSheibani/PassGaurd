import hashlib
from django.core.cache import caches

from.exceptions import CooldownActive

class CooldownService:
    """
    Handles temporary cooldown for security-sensitive actions.
    """

    cache = caches["security"]

    @classmethod
    def _build_key(cls, *, action: str, identifier: str) -> str:
        identifier_hash = hashlib.sha256(identifier.encode("utf-8")).hexdigest()

        return f"cooldown:{action}:{identifier_hash}"

    @classmethod
    def acquire(cls, *, action: str, identifier: str, duration: int) -> None:
        if duration < 1:
            raise ValueError("cooldown duration must be greater than 0")

        key = cls._build_key(action=action, identifier=identifier)

        acquired = cls.cache.add(key, True, timeout=duration)
        if not acquired:
            raise CooldownActive(f"Action '{action}' is currently on cooldown.")\


    @classmethod
    def clear(cls, *, action: str, identifier: str) -> None:
        key = cls._build_key(action=action, identifier=identifier)
        cls.cache.delete(key)

