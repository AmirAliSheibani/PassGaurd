from django.contrib.auth.models import UserManager
from django.db import transaction
from django.contrib.auth import get_user_model

User = get_user_model()

class UserService:
    """
    Handle user related business logic.
    """

    @classmethod
    @transaction.atomic
    def register(cls, *, username: str, password: str) -> User:
        """
        Create a new user account.

        Password hashing is handled by Django's
        built-in user manager.
        """
        user = User.objects.create_user(username=username, password=password)
        return user


    @classmethod
    @transaction.atomic
    def change_password(cls, *, user: User, new_password: str) -> User:
        """
        Change user master password.
        """
        user.set_password(new_password)
        user.save(update_fields=["password"])
        return user


    @classmethod
    @transaction.atomic
    def mark_recovery_setup_completed(cls, *, user: User) -> User:
        """
        Mark recovery setup as completed.
        """
        user.recovery_setup_completed = True
        user.save(update_fields=["recovery_setup_completed"])
        return user


    @classmethod
    @transaction.atomic
    def delete_user(cls, *, user: User) -> None:
        """
        Permanently delete a user account.
        """
        user.delete()


