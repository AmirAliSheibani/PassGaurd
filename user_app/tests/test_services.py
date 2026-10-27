from django.contrib.auth import get_user_model
from django.test import TestCase

from user_app.services.user_services import UserService

User = get_user_model()


class UserServiceTests(TestCase):
    def test_register_normalizes_whitespace_and_hashes_password(self):
        user = UserService.register(
            username="  passguard  ",
            password="VeryStrongPassword123!",
        )

        self.assertEqual(user.username, "passguard")
        self.assertTrue(user.check_password("VeryStrongPassword123!"))

    def test_register_rejects_case_insensitive_duplicate_username(self):
        User.objects.create_user(username="PassGuard", password="test-password")

        with self.assertRaisesRegex(ValueError, "already exists"):
            UserService.register(
                username="passguard",
                password="AnotherStrongPassword123!",
            )

    def test_register_rejects_missing_username_or_password(self):
        with self.assertRaises(ValueError):
            UserService.register(username="   ", password="valid-password")

        with self.assertRaises(ValueError):
            UserService.register(username="valid-user", password="")
