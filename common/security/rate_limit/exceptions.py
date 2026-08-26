class RateLimitExceeded(Exception):
    """
    Raised when a security-sensitive action exceeds its rate limit.
    """

    pass


class CooldownActive(Exception):
    """
    Raised when an action is still inside its cooldown period.
    """

    pass