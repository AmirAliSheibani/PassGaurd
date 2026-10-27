from django.contrib.auth import get_user_model

User = get_user_model()


class UserSelector:
    """Read-only lookups for user accounts."""

    @classmethod
    def get_by_id(cls, *, user_id: int) -> User | None:
        """Return a user or ``None`` when the ID no longer exists."""
        return User.objects.filter(pk=user_id).first()

    @classmethod
    def get_by_username(cls, *, username: str) -> User | None:
        return User.objects.filter(username__iexact=username.strip()).first()

    @classmethod
    def get_by_id_if_active(cls, *, user_id: int) -> User | None:
        """Return only active accounts; inactive users are treated as missing."""
        return User.objects.filter(pk=user_id, is_active=True).first()

    @classmethod
    def get_by_username_if_active(cls, *, username: str) -> User | None:
        """Return an active account by case-insensitive username."""
        return User.objects.filter(
            username__iexact=username.strip(),
            is_active=True,
        ).first()

    @classmethod
    def exists_by_username(cls, *, username: str) -> bool:
        return User.objects.filter(username__iexact=username.strip()).exists()

    @classmethod
    def exist_by_username(cls, *, username: str) -> bool:
        """Backward-compatible alias; prefer ``exists_by_username``."""
        return cls.exists_by_username(username=username)
