from django.contrib.auth import get_user_model

from user_app.models import BackupCode

User = get_user_model()

class BackupCodeSelector:

    @classmethod
    def get_active_codes(cls, *, user: User):
        return BackupCode.objects.filter(
            user=user,
            is_used=False
        ).only(
            'id',
            'code_hash',
        )


    @classmethod
    def has_active_codes(cls, *, user: User) -> bool:
        return BackupCode.objects.filter(user=user, is_used=False).exists()


    @classmethod
    def count_active_codes(cls, *, user: User) -> int:
        return BackupCode.objects.filter(user=user, is_used=True).count()