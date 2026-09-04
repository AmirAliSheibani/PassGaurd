from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.test import TestCase

from user_app.models import BackupCode
from user_app.services.backup_code_service import BackupCodeService
from user_app.selectors.backup_code_selector import BackupCodeSelector


User = get_user_model()


class BackupCodeServiceTests(TestCase):
    """
    Tests generation, verification, consumption, and regeneration of recovery codes.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="test-user",
            password="MasterPassword123!",
        )

    def test_generate_creates_expected_number_of_codes(self):
        codes = BackupCodeService.generate(
            user=self.user,
        )

        self.assertEqual(
            len(codes),
            BackupCodeService.BACKUP_CODE_COUNT,
        )

        self.assertEqual(
            BackupCodeSelector.codes_count(user=self.user),
            BackupCodeService.BACKUP_CODE_COUNT,
        )

    def test_generated_codes_have_expected_format(self):
        codes = BackupCodeService.generate(
            user=self.user,
        )

        self.assertEqual(
            len(set(codes)),
            BackupCodeService.BACKUP_CODE_COUNT,
        )

        for code in codes:
            self.assertEqual(
                len(code),
                BackupCodeService.CODE_LENGTH,
            )

            self.assertTrue(
                code.isdigit(),
            )

    def test_plaintext_codes_are_not_stored(self):
        codes = BackupCodeService.generate(
            user=self.user,
        )

        stored_codes = BackupCodeSelector.get_codes(user=self.user)

        for backup_code in stored_codes:
            self.assertNotIn(
                backup_code.code_hash,
                codes,
            )

    def test_generated_hash_matches_original_code(self):
        codes = BackupCodeService.generate(
            user=self.user,
        )

        stored_codes = list(
            BackupCodeSelector.get_codes(user=self.user)
        )

        self.assertTrue(
            any(
                check_password(
                    code,
                    backup_code.code_hash,
                )
                for code in codes
                for backup_code in stored_codes
            )
        )

    def test_valid_code_is_verified_and_consumed(self):
        codes = BackupCodeService.generate(
            user=self.user,
        )

        code = codes[0]

        result = BackupCodeService.verify(
            user=self.user,
            code=code,
        )

        self.assertTrue(result)

        self.assertTrue(
            BackupCode.objects.filter(
                user=self.user,
                is_used=True,
            ).exists()
        )

    def test_consumed_code_cannot_be_used_again(self):
        codes = BackupCodeService.generate(
            user=self.user,
        )

        code = codes[0]

        first_result = BackupCodeService.verify(
            user=self.user,
            code=code,
        )

        second_result = BackupCodeService.verify(
            user=self.user,
            code=code,
        )

        self.assertTrue(first_result)
        self.assertFalse(second_result)

    def test_invalid_code_is_rejected(self):
        BackupCodeService.generate(
            user=self.user,
        )

        result = BackupCodeService.verify(
            user=self.user,
            code="000000000000",
        )

        self.assertFalse(result)

    def test_regenerate_replaces_previous_codes(self):
        old_codes = BackupCodeService.generate(
            user=self.user,
        )

        new_codes = BackupCodeService.regenerate(
            user=self.user,
        )

        self.assertEqual(
            len(new_codes),
            BackupCodeService.BACKUP_CODE_COUNT,
        )

        self.assertTrue(
            set(old_codes).isdisjoint(new_codes),
        )

        self.assertEqual(
            BackupCodeSelector.get_codes(user=self.user),
            BackupCodeService.BACKUP_CODE_COUNT,
        )

        for old_code in old_codes:
            self.assertFalse(
                BackupCodeService.verify(
                    user=self.user,
                    code=old_code,
                )
            )