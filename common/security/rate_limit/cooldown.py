import hashlib
from django.core.cache import caches

from.exceptions import CooldownActive

class CooldownService:
    """
    Handles temporary cooldown for security-sensitive actions.
    """

    cache = caches['ratelimit']
    KEY_PREFIX = 'passguard:cooldown'

    @classmethod
    def _build_key(cls, *, action: str, identifier: str) -> str:
        identifier_hash = hashlib.sha256(identifier.encode("utf-8")).hexdigest()

        return f'{cls.KEY_PREFIX}:{action}:{identifier_hash}'


    @classmethod
    def enforce(cls, *, action: str, identifier: str, duration: int) -> None:
        """
        start a cooldown if none currently exists.
        """
        if duration < 1:
            raise ValueError("Cooldown duration must be greater than zero.")

        key = cls._build_key(action=action, identifier=identifier)

        created = cls.cache.add(key, True, timeout=duration)

        if not created:
            raise CooldownActive(f"Action '{action}' is currently on cooldown.")


    @classmethod
    def clear(cls, *, action: str, identifier: str) -> None:
        key = cls._build_key(action=action, identifier=identifier)
        cls.cache.delete(key)
