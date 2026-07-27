from django.db import models

from user_app.models import CustomUser


# Create your models here.


class Vault(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="vaults")
    name = models.CharField(max_length=100)
    description = models.TextField()
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Vault"
        verbose_name_plural = 'Vaults'
        ordering = ['-created_at']

        constraints = [
            models.UniqueConstraint(
                fields=['user', 'name'], name='unique_user_vault_name'
            ),
        ]
        indexes = [
            models.Index(
                fields=['user', '-created_at'],
            )
        ]

    def __str__(self):
        return f"{self.user.username}-{self.name}"


    def save(self, *args, **kwargs):
        self.name = self.name.capitalize()
        super(Vault, self).save(*args, **kwargs)


class Category(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7, default="#6B7280")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = 'Categories'
        ordering = ['name']

        constraints = [
            models.UniqueConstraint(
                fields=['user', 'name'], name='unique_user_category_name'
            )
        ]

    def __str__(self):
        return f"{self.user.username}-{self.name}"






