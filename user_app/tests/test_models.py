from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

User = get_user_model()


class CustomUserConstraintTests(TestCase):
    def test_username_uniqueness_is_case_insensitive(self):
        User.objects.create_user(username="PassGuard", password="test-password")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user(
                    username="passguard",
                    password="another-test-password",
                )
