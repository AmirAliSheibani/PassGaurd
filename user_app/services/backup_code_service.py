from django.contrib.auth.hashers import make_password, check_password
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

from common.security.password.password_generator import PasswordGenerator
from user_app.models import BackupCode

User = get_user_model()

class BackupCodeService:
    """
    Handles generation, verification, and regeneration of
    one-time account recovery codes.

    Backup codes are never stored in a plaintext.
    Only password hashes are stored.
    """

    BACKUP_CODE_COUNT = 10
    CODE_LENGTH = 12

    @classmethod
    def _remove_invalid_codes(cls, *, user: User) -> None:
        """
        Removes invalid existing backup codes for a user.

        THIS METHOD IS INTERNAL.
        """
        BackupCode.objects.filter(user=user).delete()


    @classmethod
    def _normalize(cls, code: str) -> str:
        """
        Normalize a backup code string.
        """
        code = code.strip()

        if not code.isdigit():
            return ""

        if len(code) != cls.CODE_LENGTH:
            return ""

        return code


    @classmethod
    @transaction.atomic
    def generate(cls, *, user:User) -> list[str]:
        """
        Generate a new set of backup codes for a user.

        Existing backup codes are invalidated before generating new ones.

        The plaintext codes are returned exactly once to the caller.
        """
        cls._remove_invalid_codes(user=user)

        plaintext_codes = [
            PasswordGenerator.generate_numeric(length=cls.CODE_LENGTH)     # ['856974123587', '159735425178', ...]
            for _ in range(cls.BACKUP_CODE_COUNT)
        ]

        BackupCode.objects.bulk_create(
            [
                BackupCode(
                    user=user,
                    code_hash=make_password(code)
                )
                for code in plaintext_codes
            ]
        )

        return plaintext_codes


    @classmethod
    @transaction.atomic
    def verify(cls, *, user:User, code: str) -> bool:
        """
        Verify and consume a backup code.
        """
        normalized_code = cls._normalize(code=code)
        if not normalized_code:
            return False

        active_backup_codes = (
            BackupCode.objects.filter(
                user=user,
                is_used=False
            ).only(
                "id",
                "code_hash"
            )
        )

        for backup_code in active_backup_codes:
            if check_password(normalized_code, backup_code.code_hash):
                backup_code.is_used = True
                backup_code.used_at = timezone.now()

                backup_code.save(
                    update_fields=["is_used", "used_at"]
                )
                return True

        return False


    @classmethod
    @transaction.atomic
    def regenerate(cls, *, user: User) -> list[str]:
        """
        Invalidate all existing backup codes and generate
        a completely new recovery set.

        The caller must already be authenticated and authorized
        to perform this operation.
        """
        return cls.generate(user=user)

