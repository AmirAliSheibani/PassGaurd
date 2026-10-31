"""Rate-limited master-password verification for sensitive operations."""

from common.security.rate_limit.exceptions import RateLimitExceeded
from common.security.rate_limit.limiter import RateLimiter


class InvalidMasterPassword(Exception):
    """Raised when the authenticated user's master password is incorrect."""


class ReauthenticationService:
    """Verify a master password without storing or logging the plaintext."""

    IP_LIMIT = 10
    IP_WINDOW = 300
    USER_FAILURE_LIMIT = 5
    USER_FAILURE_WINDOW = 300

    @classmethod
    def verify_master_password(
        cls,
        *,
        user,
        password: str,
        action: str,
        ip_address: str = "unknown",
    ) -> None:
        user_identifier = str(user.pk)
        RateLimiter.consume(
            action=f"reauth:{action}:ip",
            identifier=ip_address or "unknown",
            limit=cls.IP_LIMIT,
            window=cls.IP_WINDOW,
        )
        RateLimiter.check(
            action=f"reauth:{action}:user",
            identifier=user_identifier,
            limit=cls.USER_FAILURE_LIMIT,
        )

        # Treat missing/non-string values as failed attempts too. This keeps
        # callers outside Django forms from bypassing the user failure limit.
        if not isinstance(password, str) or not password or not user.check_password(password):
            RateLimiter.record_failure(
                action=f"reauth:{action}:user",
                identifier=user_identifier,
                window=cls.USER_FAILURE_WINDOW,
            )
            raise InvalidMasterPassword

        RateLimiter.reset(
            action=f"reauth:{action}:user",
            identifier=user_identifier,
        )
