from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

User = get_user_model()


class UserService:
    """Business operations for account-level user state."""

    @classmethod
    @transaction.atomic
    def register(cls, *, username: str, password: str) -> User:
        """Create an account; Django's user manager hashes the password."""
        if not isinstance(username, str):
            raise ValueError("A username is required.")
        if not isinstance(password, str) or not password:
            raise ValueError("A non-empty master password is required.")

        normalized_username = " ".join(username.split())
        if not normalized_username:
            raise ValueError("A username is required.")

        try:
            normalized_username = User._meta.get_field("username").clean(
                normalized_username,
                None,
            )
        except ValidationError as exc:
            raise ValueError("The username contains unsupported characters or is too long.") from exc

        if User.objects.filter(username__iexact=normalized_username).exists():
            raise ValueError("A user with this username already exists.")

        try:
            password_validation.validate_password(
                password,
                user=User(username=normalized_username),
            )
        except ValidationError as exc:
            raise ValueError(" ".join(exc.messages)) from exc

        try:
            # A savepoint lets us translate a race against the case-insensitive
            # unique index without leaving the surrounding transaction broken.
            with transaction.atomic():
                return User.objects.create_user(
                    username=normalized_username,
                    password=password,
                )
        except IntegrityError as exc:
            if User.objects.filter(username__iexact=normalized_username).exists():
                raise ValueError("A user with this username already exists.") from exc
            raise

    @classmethod
    @transaction.atomic
    def change_password(cls, *, user: User, new_password: str) -> User:
        """Change the master password using Django's password hashing."""
        if not isinstance(new_password, str) or not new_password:
            raise ValueError("A non-empty master password is required.")
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        if not locked_user.is_active:
            raise ValueError("Inactive accounts cannot change the master password.")
        password_validation.validate_password(new_password, user=locked_user)
        locked_user.set_password(new_password)
        locked_user.save(update_fields=["password", "updated_at"])
        # Callers may log this same in-memory instance into the session immediately
        # after a recovery flow; keep its password hash in sync with the database.
        user.password = locked_user.password
        user.updated_at = locked_user.updated_at
        return user

    @classmethod
    @transaction.atomic
    def mark_recovery_setup_completed(cls, *, user: User) -> User:
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        if not locked_user.recovery_setup_completed:
            locked_user.recovery_setup_completed = True
            locked_user.save(update_fields=["recovery_setup_completed", "updated_at"])
        return locked_user

    @classmethod
    @transaction.atomic
    def delete_user(cls, *, user: User) -> None:
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        locked_user.delete()
