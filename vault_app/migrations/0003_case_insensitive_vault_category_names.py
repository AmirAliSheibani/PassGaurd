from django.db import migrations, models
from django.db.models import Count
from django.db.models.functions import Lower


def ensure_case_insensitive_names_are_unique(apps, schema_editor):
    """Keep existing user-owned names intact; ask for manual cleanup on collisions."""
    database = schema_editor.connection.alias
    checks = (
        (apps.get_model("vault_app", "Vault"), "vault"),
        (apps.get_model("vault_app", "Category"), "category"),
    )
    for model, label in checks:
        duplicates = (
            model.objects.using(database)
            .annotate(normalized_name=Lower("name"))
            .values("user_id", "normalized_name")
            .annotate(total=Count("pk"))
            .filter(total__gt=1)
        )
        if duplicates.exists():
            raise RuntimeError(
                f"Cannot add case-insensitive {label} name uniqueness: existing records "
                "owned by the same user have names that differ only by case. Resolve "
                "those records, then rerun migrations."
            )


class Migration(migrations.Migration):
    dependencies = [
        ("vault_app", "0002_alter_vault_slug"),
    ]

    operations = [
        migrations.RunPython(
            ensure_case_insensitive_names_are_unique,
            migrations.RunPython.noop,
        ),
        migrations.RemoveConstraint(
            model_name="vault",
            name="unique_user_vault_name",
        ),
        migrations.RemoveConstraint(
            model_name="category",
            name="unique_user_category_name",
        ),
        migrations.AddConstraint(
            model_name="vault",
            constraint=models.UniqueConstraint(
                Lower("name"),
                "user",
                name="unique_user_vault_name_ci",
            ),
        ),
        migrations.AddConstraint(
            model_name="category",
            constraint=models.UniqueConstraint(
                Lower("name"),
                "user",
                name="unique_user_category_name_ci",
            ),
        ),
    ]
