class RateLimitExceeded(Exception):
    """
    Raised when an action exceeds its configured rate limit.
    """

    def __init__(self, message: str, *, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after