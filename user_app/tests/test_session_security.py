from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.messages.storage.fallback import FallbackStorage
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from common.middleware.session_security import SessionSecurityMiddleware
from common.security.session import (
    AUTH_SESSION_LAST_ACTIVITY_AT,
    AUTH_SESSION_MODE,
    AUTH_SESSION_STARTED_AT,
    RECOVERY_SESSION_LAST_ACTIVITY_AT,
    RECOVERY_SESSION_STARTED_AT,
    SESSION_MODE_BACKUP_SETUP,
    SESSION_MODE_NORMAL,
    start_authenticated_session,
    start_recovery_session,
)

User = get_user_model()


@override_settings(
    PASSGUARD_SESSION_IDLE_TIMEOUT=600,
    PASSGUARD_SESSION_MAX_AGE=3600,
    PASSGUARD_SETUP_SESSION_MAX_AGE=600,
    PASSGUARD_RECOVERY_SESSION_MAX_AGE=600,
)
class SessionSecurityMiddlewareTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="session-user",
            password="Strong-Test-Password-123!",
        )

    def make_request(self, *, user=None, path="/"):
        request = RequestFactory().get(path)
        request.user = self.user if user is None else user
        # No session row is persisted unless save() is called by the client.
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        return request

    def test_active_request_refreshes_idle_timestamp_but_not_absolute_start(self):
        now = timezone.now()
        request = self.make_request()
        started_at = (now - timedelta(minutes=20)).timestamp()
        previous_activity = (now - timedelta(minutes=2)).timestamp()
        request.session[AUTH_SESSION_STARTED_AT] = started_at
        request.session[AUTH_SESSION_LAST_ACTIVITY_AT] = previous_activity
        request.session[AUTH_SESSION_MODE] = SESSION_MODE_NORMAL

        middleware = SessionSecurityMiddleware(lambda _request: HttpResponse("ok"))
        with patch("common.middleware.session_security.timezone.now", return_value=now):
            response = middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(request.session[AUTH_SESSION_STARTED_AT], started_at)
        self.assertEqual(request.session[AUTH_SESSION_LAST_ACTIVITY_AT], now.timestamp())
        self.assertTrue(request.session.get_expire_at_browser_close())

    def test_idle_timeout_logs_user_out_after_ten_minutes(self):
        now = timezone.now()
        request = self.make_request()
        request.session[AUTH_SESSION_STARTED_AT] = (now - timedelta(minutes=5)).timestamp()
        request.session[AUTH_SESSION_LAST_ACTIVITY_AT] = (now - timedelta(minutes=10)).timestamp()
        request.session[AUTH_SESSION_MODE] = SESSION_MODE_NORMAL
        downstream_called = []

        middleware = SessionSecurityMiddleware(
            lambda _request: downstream_called.append(True) or HttpResponse("ok")
        )
        with patch("common.middleware.session_security.timezone.now", return_value=now):
            response = middleware(request)

        self.assertEqual(response.status_code, 302)
        self.assertFalse(downstream_called)
        self.assertIsInstance(request.user, AnonymousUser)
        self.assertEqual(dict(request.session.items()), {})

    def test_absolute_timeout_logs_user_out_even_when_active(self):
        now = timezone.now()
        request = self.make_request()
        request.session[AUTH_SESSION_STARTED_AT] = (now - timedelta(hours=1)).timestamp()
        request.session[AUTH_SESSION_LAST_ACTIVITY_AT] = (now - timedelta(seconds=1)).timestamp()
        request.session[AUTH_SESSION_MODE] = SESSION_MODE_NORMAL

        middleware = SessionSecurityMiddleware(lambda _request: HttpResponse("ok"))
        with patch("common.middleware.session_security.timezone.now", return_value=now):
            response = middleware(request)

        self.assertEqual(response.status_code, 302)
        self.assertIsInstance(request.user, AnonymousUser)

    def test_backup_setup_has_ten_minute_absolute_lifetime(self):
        now = timezone.now()
        request = self.make_request()
        request.session[AUTH_SESSION_STARTED_AT] = (now - timedelta(minutes=10)).timestamp()
        request.session[AUTH_SESSION_LAST_ACTIVITY_AT] = (now - timedelta(seconds=2)).timestamp()
        request.session[AUTH_SESSION_MODE] = SESSION_MODE_BACKUP_SETUP
        request.session["backup_code_setup_pending"] = True

        middleware = SessionSecurityMiddleware(lambda _request: HttpResponse("ok"))
        with patch("common.middleware.session_security.timezone.now", return_value=now):
            response = middleware(request)

        self.assertEqual(response.status_code, 302)
        self.assertIsInstance(request.user, AnonymousUser)

    def test_valid_recovery_session_is_allowed_and_refreshes_idle_timestamp(self):
        now = timezone.now()
        request = self.make_request(
            user=AnonymousUser(),
            path="/recovery/reset-password/",
        )
        started_at = (now - timedelta(minutes=2)).timestamp()
        previous_activity = (now - timedelta(minutes=1)).timestamp()
        request.session["recovery_user_id"] = self.user.pk
        request.session[RECOVERY_SESSION_STARTED_AT] = started_at
        request.session[RECOVERY_SESSION_LAST_ACTIVITY_AT] = previous_activity
        downstream_called = []

        middleware = SessionSecurityMiddleware(
            lambda _request: downstream_called.append(True) or HttpResponse("ok")
        )
        with patch("common.middleware.session_security.timezone.now", return_value=now):
            response = middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(downstream_called)
        self.assertEqual(request.session[RECOVERY_SESSION_STARTED_AT], started_at)
        self.assertEqual(
            request.session[RECOVERY_SESSION_LAST_ACTIVITY_AT],
            now.timestamp(),
        )
        self.assertEqual(request.session["recovery_user_id"], self.user.pk)
        self.assertTrue(request.session.get_expire_at_browser_close())

    def test_recovery_session_expires_after_ten_minutes(self):
        now = timezone.now()
        request = self.make_request(user=AnonymousUser(), path="/recovery/reset-password/")
        request.session["recovery_user_id"] = self.user.pk
        request.session[RECOVERY_SESSION_STARTED_AT] = (now - timedelta(minutes=10)).timestamp()
        request.session[RECOVERY_SESSION_LAST_ACTIVITY_AT] = (now - timedelta(seconds=1)).timestamp()

        middleware = SessionSecurityMiddleware(lambda _request: HttpResponse("ok"))
        with patch("common.middleware.session_security.timezone.now", return_value=now):
            response = middleware(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(dict(request.session.items()), {})

    def test_partially_missing_or_non_finite_auth_timestamps_invalidate_session(self):
        now = timezone.now()
        for malformed_started_at in (float("nan"), float("inf"), "not-a-time"):
            with self.subTest(value=malformed_started_at):
                request = self.make_request()
                request.session[AUTH_SESSION_STARTED_AT] = malformed_started_at
                request.session[AUTH_SESSION_LAST_ACTIVITY_AT] = now.timestamp()
                request.session[AUTH_SESSION_MODE] = SESSION_MODE_NORMAL

                middleware = SessionSecurityMiddleware(lambda _request: HttpResponse("ok"))
                with patch("common.middleware.session_security.timezone.now", return_value=now):
                    response = middleware(request)

                self.assertEqual(response.status_code, 302)
                self.assertIsInstance(request.user, AnonymousUser)
                self.assertEqual(dict(request.session.items()), {})

    def test_one_missing_auth_timestamp_does_not_reset_session_lifetime(self):
        request = self.make_request()
        request.session[AUTH_SESSION_STARTED_AT] = timezone.now().timestamp()
        request.session[AUTH_SESSION_MODE] = SESSION_MODE_NORMAL

        middleware = SessionSecurityMiddleware(lambda _request: HttpResponse("ok"))
        response = middleware(request)

        self.assertEqual(response.status_code, 302)
        self.assertIsInstance(request.user, AnonymousUser)

    def test_backup_setup_helper_keeps_setup_state_consistent(self):
        request = self.make_request()
        start_authenticated_session(request, mode=SESSION_MODE_BACKUP_SETUP)

        self.assertTrue(request.session["backup_code_setup_pending"])

    def test_normal_session_clears_stale_backup_setup_state(self):
        request = self.make_request()
        request.session["backup_code_setup_pending"] = True
        request.session["backup_codes"] = ["one-time-code"]
        start_authenticated_session(request, mode=SESSION_MODE_NORMAL)

        self.assertNotIn("backup_code_setup_pending", request.session)
        self.assertNotIn("backup_codes", request.session)

    def test_setup_mode_with_missing_pending_flag_is_invalidated(self):
        now = timezone.now()
        request = self.make_request()
        request.session[AUTH_SESSION_STARTED_AT] = now.timestamp()
        request.session[AUTH_SESSION_LAST_ACTIVITY_AT] = now.timestamp()
        request.session[AUTH_SESSION_MODE] = SESSION_MODE_BACKUP_SETUP

        middleware = SessionSecurityMiddleware(lambda _request: HttpResponse("ok"))
        with patch("common.middleware.session_security.timezone.now", return_value=now):
            response = middleware(request)

        self.assertEqual(response.status_code, 302)
        self.assertIsInstance(request.user, AnonymousUser)
        self.assertEqual(dict(request.session.items()), {})

    def test_tracked_session_with_missing_mode_is_invalidated(self):
        now = timezone.now()
        request = self.make_request()
        request.session[AUTH_SESSION_STARTED_AT] = now.timestamp()
        request.session[AUTH_SESSION_LAST_ACTIVITY_AT] = now.timestamp()

        middleware = SessionSecurityMiddleware(lambda _request: HttpResponse("ok"))
        with patch("common.middleware.session_security.timezone.now", return_value=now):
            response = middleware(request)

        self.assertEqual(response.status_code, 302)
        self.assertIsInstance(request.user, AnonymousUser)
        self.assertEqual(dict(request.session.items()), {})

    def test_normal_session_with_stale_backup_setup_flag_is_invalidated(self):
        now = timezone.now()
        request = self.make_request()
        request.session[AUTH_SESSION_STARTED_AT] = now.timestamp()
        request.session[AUTH_SESSION_LAST_ACTIVITY_AT] = now.timestamp()
        request.session[AUTH_SESSION_MODE] = SESSION_MODE_NORMAL
        request.session["backup_code_setup_pending"] = True

        middleware = SessionSecurityMiddleware(lambda _request: HttpResponse("ok"))
        with patch("common.middleware.session_security.timezone.now", return_value=now):
            response = middleware(request)

        self.assertEqual(response.status_code, 302)
        self.assertIsInstance(request.user, AnonymousUser)
        self.assertEqual(dict(request.session.items()), {})

    def test_malformed_recovery_user_id_flushes_recovery_session(self):
        request = self.make_request(user=AnonymousUser(), path="/recovery/reset-password/")
        request.session["recovery_user_id"] = 0
        request.session[RECOVERY_SESSION_STARTED_AT] = timezone.now().timestamp()
        request.session[RECOVERY_SESSION_LAST_ACTIVITY_AT] = timezone.now().timestamp()

        middleware = SessionSecurityMiddleware(lambda _request: HttpResponse("ok"))
        response = middleware(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(dict(request.session.items()), {})

    def test_authenticated_session_helper_starts_new_browser_session(self):
        request = self.make_request()
        start_authenticated_session(request, mode=SESSION_MODE_NORMAL)

        self.assertTrue(request.session.get_expire_at_browser_close())
        self.assertEqual(request.session.get_expiry_age(), 600)
        self.assertIn(AUTH_SESSION_STARTED_AT, request.session)
        self.assertIn(AUTH_SESSION_LAST_ACTIVITY_AT, request.session)

    def test_recovery_helper_starts_new_short_lived_recovery_session(self):
        request = self.make_request(user=AnonymousUser(), path="/recovery/")
        request.session["stale_anonymous_state"] = "discard-me"
        start_recovery_session(request, user_id=self.user.pk)

        self.assertNotIn("stale_anonymous_state", request.session)

        self.assertEqual(request.session["recovery_user_id"], self.user.pk)
        self.assertIn(RECOVERY_SESSION_STARTED_AT, request.session)
        self.assertIn(RECOVERY_SESSION_LAST_ACTIVITY_AT, request.session)
        self.assertTrue(request.session.get_expire_at_browser_close())
        self.assertEqual(request.session.get_expiry_age(), 600)
