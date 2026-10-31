from django.contrib.auth import get_user_model
from django.test import TestCase

from user_app.selectors.user_selector import UserSelector

User = get_user_model()


class UserSelectorTests(TestCase):
    def test_get_by_id_returns_none_for_missing_user(self):
        self.assertIsNone(UserSelector.get_by_id(user_id=999999))

    def test_get_by_id_if_active_excludes_inactive_users(self):
        active = User.objects.create_user(username="active", password="Strong-Password-123!")
        inactive = User.objects.create_user(username="inactive", password="Strong-Password-123!")
        inactive.is_active = False
        inactive.save(update_fields=["is_active"])

        self.assertEqual(UserSelector.get_by_id_if_active(user_id=active.pk), active)
        self.assertIsNone(UserSelector.get_by_id_if_active(user_id=inactive.pk))
