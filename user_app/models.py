from django.db import models
from django.contrib.auth.models import AbstractUser
# Create your models here.


class CustomUser(AbstractUser):
    """
    Custom user model for PassGuard.

    The user model Only handles authentication
    and account-level information.
    """
    recovery_setup_completed = models.BooleanField(
        default=False,
        help_text='Indicates whether the user recovery setup was completed.'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "-created_at"
        ]

    def __str__(self):
        return self.username

