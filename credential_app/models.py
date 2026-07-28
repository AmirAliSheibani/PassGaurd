from django.contrib.auth.models import User
from django.db import models

from vault_app.models import Vault, Category


# Create your models here.

class Credential(models.Model):
    vault = models.ForeignKey(Vault, on_delete=models.CASCADE, related_name='credentials')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='credentials')
    service_name = models.CharField(max_length=100)
    service_url = models.URLField(null=True, blank=True)
    login_username = models.CharField(max_length=100)
    login_email = models.EmailField(null=True, blank=True)
    password_ciphertext = models.CharField(max_length=100)
    is_favorite = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["vault", "service_name"],
                name="unique_service_per_vault",
            )
        ]

        indexes = [
            models.Index(
                fields=["vault", "service_name"]
            )
        ]


    def __str__(self):
        return f"{self.vault.user} - {self.service_name}"

