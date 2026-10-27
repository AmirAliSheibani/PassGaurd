from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from common.security.password.password_generator import PasswordGenerator
from common.security.rate_limit.cooldown import CooldownService
from common.security.rate_limit.policies import BackupCodeRegenerationPolicy
from user_app.models import BackupCode
from user_app.selectors.backup_code_selector import BackupCodeSelector

User = get_user_model()


class BackupCodeService:
    """Generate, verify, consume, and regenerate one-time recovery codes.

    Plaintext codes are only returned at generation time. Their database values
    are password hashes, and account-row locks serialize generation and use for
    a single user when the database supports SELECT FOR UPDATE.
    """

    BACKUP_CODE_COUNT = 10
    CODE_LENGTH = 12

    @classmethod
    def _remove_invalid_codes(cls, *, user: User) -> None:
        BackupCodeSelector.get_codes(user=user).delete()

    @classmethod
    def _normalize(cls, code: str) -> str:
        if not isinstance(code, str):
            return ""
        normalized = code.strip()
        if not normalized.isascii() or not normalized.isdigit():
            return ""
        if len(normalized) != cls.CODE_LENGTH:
            return ""
        return normalized

    @classmethod
    @transaction.atomic
    def generate(cls, *, user: User) -> list[str]:
        """Replace the recovery set and return its plaintext values once."""
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        if not locked_user.is_active:
            raise ValueError("Inactive accounts cannot generate recovery codes.")
        cls._remove_invalid_codes(user=locked_user)
        plaintext_codes = [
            PasswordGenerator.generate_numeric(length=cls.CODE_LENGTH)
            for _ in range(cls.BACKUP_CODE_COUNT)
        ]
        BackupCode.objects.bulk_create(
            [
                BackupCode(user=locked_user, code_hash=make_password(code))
                for code in plaintext_codes
            ]
        )
        return plaintext_codes

    @classmethod
    @transaction.atomic
    def verify(cls, *, user: User, code: str) -> bool:
        """Verify and atomically consume a matching active recovery code."""
        normalized_code = cls._normalize(code)
        if not normalized_code:
            return False

        locked_user = User.objects.select_for_update().get(pk=user.pk)
        if not locked_user.is_active:
            return False
        active_codes = BackupCodeSelector.get_active_codes(user=locked_user)
        for backup_code in active_codes:
            if check_password(normalized_code, backup_code.code_hash):
                backup_code.is_used = True
                backup_code.used_at = timezone.now()
                backup_code.save(update_fields=["is_used", "used_at"])
                return True
        return False

    @classmethod
    @transaction.atomic
    def regenerate(cls, *, user: User) -> list[str]:
        """Regenerate all codes subject to a per-user cooldown.

        The view must authenticate and authorize the request before calling this
        service. The cache cooldown is cleared if database generation fails.
        """
        identifier = str(user.pk)
        CooldownService.acquire(
            action="backup-code-regeneration",
            identifier=identifier,
            duration=BackupCodeRegenerationPolicy.COOLDOWN_SECONDS,
        )
        try:
            return cls.generate(user=user)
        except Exception:
            CooldownService.clear(
                action="backup-code-regeneration",
                identifier=identifier,
            )
            raise
