from django.core.cache import caches
from django.test import SimpleTestCase

from common.security.rate_limit.cooldown import CooldownService
from common.security.rate_limit.exceptions import CooldownActive


class CooldownServiceTests(SimpleTestCase):
    """
    Tests temporary cooldown behavior for sensitive actions.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cache = caches["security"]

    def setUp(self):
        self.cache.clear()

    def tearDown(self):
        self.cache.clear()

    def test_first_acquire_succeeds(self):
        CooldownService.acquire(
            action="backup-code-regeneration",
            identifier="user-1",
            duration=300,
        )

    def test_second_acquire_is_blocked(self):
        CooldownService.acquire(
            action="backup-code-regeneration",
            identifier="user-1",
            duration=300,
        )

        with self.assertRaises(CooldownActive):
            CooldownService.acquire(
                action="backup-code-regeneration",
                identifier="user-1",
                duration=300,
            )

    def test_different_identifiers_have_independent_cooldowns(self):
        CooldownService.acquire(
            action="backup-code-regeneration",
            identifier="user-1",
            duration=300,
        )

        CooldownService.acquire(
            action="backup-code-regeneration",
            identifier="user-2",
            duration=300,
        )

    def test_clear_allows_action_again(self):
        CooldownService.acquire(
            action="backup-code-regeneration",
            identifier="user-1",
            duration=300,
        )

        CooldownService.clear(
            action="backup-code-regeneration",
            identifier="user-1",
        )

        CooldownService.acquire(
            action="backup-code-regeneration",
            identifier="user-1",
            duration=300,
        )

    def test_invalid_duration_is_rejected(self):
        with self.assertRaises(ValueError):
            CooldownService.acquire(
                action="backup-code-regeneration",
                identifier="user-1",
                duration=0,
            )