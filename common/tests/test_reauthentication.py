from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from common.security.reauthentication import (
    InvalidMasterPassword,
    ReauthenticationService,
)


class ReauthenticationServiceTests(SimpleTestCase):
    @patch("common.security.reauthentication.RateLimiter.reset")
    @patch("common.security.reauthentication.RateLimiter.check")
    @patch("common.security.reauthentication.RateLimiter.consume")
    def test_correct_password_consumes_ip_limit_and_resets_failures(
        self, mock_consume, mock_check, mock_reset
    ):
        user = SimpleNamespace(pk=10, check_password=lambda value: value == "correct")

        ReauthenticationService.verify_master_password(
            user=user,
            password="correct",
            action="bulk-delete",
            ip_address="127.0.0.1",
        )

        mock_consume.assert_called_once()
        mock_check.assert_called_once()
        mock_reset.assert_called_once()

    @patch("common.security.reauthentication.RateLimiter.record_failure")
    @patch("common.security.reauthentication.RateLimiter.check")
    @patch("common.security.reauthentication.RateLimiter.consume")
    def test_empty_password_is_counted_as_a_failed_attempt(
        self, mock_consume, mock_check, mock_record_failure
    ):
        user = SimpleNamespace(pk=10, check_password=lambda _value: False)

        with self.assertRaises(InvalidMasterPassword):
            ReauthenticationService.verify_master_password(
                user=user,
                password="",
                action="bulk-delete",
                ip_address="127.0.0.1",
            )

        mock_consume.assert_called_once()
        mock_check.assert_called_once()
        mock_record_failure.assert_called_once()
