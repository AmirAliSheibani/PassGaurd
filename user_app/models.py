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


class BackupCode(models.Model):
    """
    One-time recovery codes for account recovery.

    The actual code is never stored.
    Only its hashed value is stored in the database.
    """

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="backup_codes")
    code_hash = models.CharField(max_length=255)
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Backup Code"
        verbose_name_plural = "Backup Codes"

        ordering = [
            "-created_at"
        ]

        indexes = [
            models.Index(
                fields=[
                    "user",
                    "is_used",
                ]
            )
        ]

    def __str__(self):
        status = "used" if self.is_used else "active"

        return (
            f"{self.user.username} - "
            f"Backup Code ({status})"
        )