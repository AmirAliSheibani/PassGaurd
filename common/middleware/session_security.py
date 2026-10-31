"""Enforce inactivity and absolute lifetime limits for PassGuard sessions."""

import math

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from common.security.session import (
    AUTH_SESSION_LAST_ACTIVITY_AT,
    AUTH_SESSION_MODE,
    AUTH_SESSION_STARTED_AT,
    RECOVERY_SESSION_LAST_ACTIVITY_AT,
    RECOVERY_SESSION_STARTED_AT,
    SESSION_MODE_BACKUP_SETUP,
    SESSION_MODE_NORMAL,
    start_authenticated_session,
)


class SessionSecurityMiddleware:
    """Apply server-enforced idle and absolute expirations.

    Normal authenticated sessions expire after 10 minutes of inactivity or
    60 minutes from login, whichever comes first. The recovery-code setup
    phase has a 10-minute absolute lifetime. Anonymous recovery authorization
    is also limited to 10 minutes.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def _now() -> float:
        return timezone.now().timestamp()

    @staticmethod
    def _as_timestamp(value):
        try:
            timestamp = float(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if not math.isfinite(timestamp):
            return None
        return timestamp

    def __call__(self, request):
        expired_response = self._expire_if_required(request)
        if expired_response is not None:
            return expired_response

        response = self.get_response(request)
        self._refresh_session_state(request)
        return response

    def _expire_if_required(self, request):
        now = self._now()
        session = request.session

        if request.user.is_authenticated:
            mode = session.get(AUTH_SESSION_MODE)
            started_at = self._as_timestamp(session.get(AUTH_SESSION_STARTED_AT))
            last_activity_at = self._as_timestamp(
                session.get(AUTH_SESSION_LAST_ACTIVITY_AT)
            )

            # Existing sessions created before this middleware was enabled,
            # and test/client-created sessions, start their tracked lifetime
            # on their first request through this middleware.
            raw_started_at = session.get(AUTH_SESSION_STARTED_AT)
            raw_last_activity_at = session.get(AUTH_SESSION_LAST_ACTIVITY_AT)

            # Fully untracked sessions may be legacy sessions created before
            # this middleware was deployed. A partially-present or malformed
            # lifetime must be invalidated, never silently reset.
            if raw_started_at is None and raw_last_activity_at is None:
                if mode not in {SESSION_MODE_NORMAL, SESSION_MODE_BACKUP_SETUP}:
                    mode = (
                        SESSION_MODE_BACKUP_SETUP
                        if session.get("backup_code_setup_pending")
                        else SESSION_MODE_NORMAL
                    )
                start_authenticated_session(request, mode=mode)
                return None

            pending_setup = session.get("backup_code_setup_pending") is True
            mode_is_valid = mode in {SESSION_MODE_NORMAL, SESSION_MODE_BACKUP_SETUP}
            setup_state_is_valid = (
                (mode == SESSION_MODE_BACKUP_SETUP and pending_setup)
                or (mode == SESSION_MODE_NORMAL and not pending_setup)
            )

            if (
                not mode_is_valid
                or not setup_state_is_valid
                or started_at is None
                or last_activity_at is None
                or started_at > now + 60
                or last_activity_at > now + 60
                or last_activity_at < started_at
            ):
                logout(request)
                messages.warning(
                    request,
                    "Your PassGuard session is invalid. Please sign in again.",
                )
                return redirect(reverse("user_app:login"))

            idle_timeout = int(
                getattr(settings, "PASSGUARD_SESSION_IDLE_TIMEOUT", 600)
            )
            absolute_timeout = int(
                getattr(
                    settings,
                    "PASSGUARD_SETUP_SESSION_MAX_AGE"
                    if mode == SESSION_MODE_BACKUP_SETUP
                    else "PASSGUARD_SESSION_MAX_AGE",
                    600 if mode == SESSION_MODE_BACKUP_SETUP else 3600,
                )
            )

            if (
                now - last_activity_at >= idle_timeout
                or now - started_at >= absolute_timeout
            ):
                logout(request)
                messages.warning(
                    request,
                    "Your PassGuard session expired. Please sign in again.",
                )
                return redirect(reverse("user_app:login"))

            session[AUTH_SESSION_LAST_ACTIVITY_AT] = now
            session.set_expiry(0)
            return None

        # Backup-code verification grants a short-lived anonymous recovery
        # session. It must not silently become a normal authenticated session.
        if "recovery_user_id" in session:
            recovery_user_id = session.get("recovery_user_id")
            try:
                valid_recovery_user_id = (
                    not isinstance(recovery_user_id, bool)
                    and int(recovery_user_id) > 0
                    and str(int(recovery_user_id)) == str(recovery_user_id)
                )
            except (TypeError, ValueError, OverflowError):
                valid_recovery_user_id = False

            if not valid_recovery_user_id:
                session.flush()
                return redirect(reverse("user_app:recovery"))

            started_at = self._as_timestamp(
                session.get(RECOVERY_SESSION_STARTED_AT)
            )
            last_activity_at = self._as_timestamp(
                session.get(RECOVERY_SESSION_LAST_ACTIVITY_AT)
            )
            recovery_timeout = int(
                getattr(settings, "PASSGUARD_RECOVERY_SESSION_MAX_AGE", 600)
            )

            # A recovery session without timestamps is legacy or malformed;
            # invalidate it rather than extending its authorization window.
            if (
                started_at is None
                or last_activity_at is None
                or started_at > now + 60
                or last_activity_at > now + 60
                or last_activity_at < started_at
            ):
                session.flush()
                return redirect(reverse("user_app:recovery"))

            if (
                now - started_at >= recovery_timeout
                or now - last_activity_at >= recovery_timeout
            ):
                session.flush()
                messages.warning(
                    request,
                    "Your recovery session expired. Please start recovery again.",
                )
                return redirect(reverse("user_app:recovery"))

            session[RECOVERY_SESSION_LAST_ACTIVITY_AT] = now
            session.set_expiry(0)

        return None

    def _refresh_session_state(self, request):
        """Initialize sessions created by login() during the current request."""
        if not request.user.is_authenticated:
            return

        session = request.session
        if not session.get(AUTH_SESSION_STARTED_AT):
            mode = (
                SESSION_MODE_BACKUP_SETUP
                if session.get("backup_code_setup_pending")
                else SESSION_MODE_NORMAL
            )
            start_authenticated_session(request, mode=mode)
            return

        # Keep browser-close semantics even when views modify the session.
        session.set_expiry(0)
