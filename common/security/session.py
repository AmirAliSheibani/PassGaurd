"""Helpers for establishing short-lived PassGuard authentication sessions."""

from django.utils import timezone

AUTH_SESSION_STARTED_AT = "_passguard_auth_started_at"
AUTH_SESSION_LAST_ACTIVITY_AT = "_passguard_auth_last_activity_at"
AUTH_SESSION_MODE = "_passguard_auth_mode"

RECOVERY_SESSION_STARTED_AT = "_passguard_recovery_started_at"
RECOVERY_SESSION_LAST_ACTIVITY_AT = "_passguard_recovery_last_activity_at"

SESSION_MODE_NORMAL = "normal"
SESSION_MODE_BACKUP_SETUP = "backup_setup"


def _timestamp() -> float:
    return timezone.now().timestamp()


def start_authenticated_session(request, *, mode: str = SESSION_MODE_NORMAL) -> None:
    """Start a fresh authenticated session lifetime after login or re-auth."""
    if mode not in {SESSION_MODE_NORMAL, SESSION_MODE_BACKUP_SETUP}:
        raise ValueError("Unsupported authenticated session mode.")

    now = _timestamp()
    session = request.session

    # Do not carry temporary account-recovery state into an authenticated session.
    session.pop("recovery_user_id", None)
    session.pop(RECOVERY_SESSION_STARTED_AT, None)
    session.pop(RECOVERY_SESSION_LAST_ACTIVITY_AT, None)

    session[AUTH_SESSION_STARTED_AT] = now
    session[AUTH_SESSION_LAST_ACTIVITY_AT] = now
    session[AUTH_SESSION_MODE] = mode

    if mode == SESSION_MODE_BACKUP_SETUP:
        session["backup_code_setup_pending"] = True
    else:
        session.pop("backup_code_setup_pending", None)
        session.pop("backup_codes", None)

    # A browser-session cookie is deliberate. Server-side timestamps enforce
    # idle and absolute expiration even when the browser restores a session.
    session.set_expiry(0)


def start_recovery_session(request, *, user_id: int) -> None:
    """Create a short-lived anonymous recovery authorization session."""
    now = _timestamp()
    session = request.session

    # Recovery is a privilege transition. Rotate the session identifier and
    # discard unrelated anonymous state before granting temporary access.
    session.flush()
    session["recovery_user_id"] = int(user_id)
    session[RECOVERY_SESSION_STARTED_AT] = now
    session[RECOVERY_SESSION_LAST_ACTIVITY_AT] = now
    session.set_expiry(0)


def complete_backup_code_setup_session(request) -> None:
    """End the temporary setup window and start the normal 1-hour session."""
    request.session.pop("backup_codes", None)
    request.session.pop("backup_code_setup_pending", None)
    start_authenticated_session(request, mode=SESSION_MODE_NORMAL)
