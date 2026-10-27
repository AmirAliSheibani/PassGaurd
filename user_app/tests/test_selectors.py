from django.contrib.auth import get_user_model
from django.test import TestCase

from user_app.selectors.user_selector import UserSelector

User = get_user_model()


class UserSelectorTests(TestCase):
    def setUp(self):
        self.active_user = User.objects.create_user(
            username="active-user",
            password="test-password",
        )
        self.inactive_user = User.objects.create_user(
            username="inactive-user",
            password="test-password",
            is_active=False,
        )

    def test_get_by_id_returns_none_for_missing_user(self):
        self.assertIsNone(UserSelector.get_by_id(user_id=999999))

    def test_get_by_username_is_case_insensitive(self):
        self.assertEqual(
            UserSelector.get_by_username(username="ACTIVE-USER"),
            self.active_user,
        )

    def test_get_by_id_if_active_excludes_inactive_accounts(self):
        self.assertEqual(
            UserSelector.get_by_id_if_active(user_id=self.active_user.pk),
            self.active_user,
        )
        self.assertIsNone(
            UserSelector.get_by_id_if_active(user_id=self.inactive_user.pk)
        )

    def test_get_by_username_if_active_excludes_inactive_accounts(self):
        self.assertEqual(
            UserSelector.get_by_username_if_active(username="ACTIVE-USER"),
            self.active_user,
        )
        self.assertIsNone(
            UserSelector.get_by_username_if_active(username="INACTIVE-USER")
        )

    def test_exists_by_username_is_case_insensitive(self):
        self.assertTrue(UserSelector.exists_by_username(username="ACTIVE-USER"))
        self.assertFalse(UserSelector.exists_by_username(username="missing-user"))
