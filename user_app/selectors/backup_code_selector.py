from django.contrib.auth import get_user_model
from django.db.models import QuerySet

from user_app.models import BackupCode

User = get_user_model()


class BackupCodeSelector:
    """Read-only recovery-code queries.

    ``get_active_codes`` uses row locks and must be evaluated from inside an
    atomic transaction (the BackupCodeService provides that transaction).
    """

    @classmethod
    def get_codes(cls, *, user: User) -> QuerySet[BackupCode]:
        return BackupCode.objects.filter(user_id=user.pk)

    @classmethod
    def get_active_codes(cls, *, user: User) -> QuerySet[BackupCode]:
        return (
            BackupCode.objects.select_for_update()
            .filter(user_id=user.pk, is_used=False)
            .only("id", "code_hash", "is_used", "used_at")
            .order_by("id")
        )

    @classmethod
    def has_active_codes(cls, *, user: User) -> bool:
        return BackupCode.objects.filter(user_id=user.pk, is_used=False).exists()

    @classmethod
    def codes_count(cls, *, user: User) -> int:
        return BackupCode.objects.filter(user_id=user.pk).count()

    @classmethod
    def remaining_count(cls, *, user: User) -> int:
        """Count unused backup codes that can still be redeemed."""
        return BackupCode.objects.filter(user_id=user.pk, is_used=False).count()
