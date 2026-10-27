from django.db import migrations, models
from django.db.models import Count
from django.db.models.functions import Lower


def ensure_case_insensitive_service_names_are_unique(apps, schema_editor):
    """Check current data before replacing exact-case uniqueness with CI uniqueness."""
    Credential = apps.get_model("credential_app", "Credential")
    database = schema_editor.connection.alias
    duplicates = (
        Credential.objects.using(database)
        .annotate(normalized_service_name=Lower("service_name"))
        .values("vault_id", "normalized_service_name")
        .annotate(total=Count("pk"))
        .filter(total__gt=1)
    )
    if duplicates.exists():
        raise RuntimeError(
            "Cannot add case-insensitive credential name uniqueness: a vault contains "
            "service names that differ only by case. Rename/remove those entries, then "
            "rerun migrations. No records have been changed by this check."
        )


class Migration(migrations.Migration):
    dependencies = [
        ("credential_app", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            ensure_case_insensitive_service_names_are_unique,
            migrations.RunPython.noop,
        ),
        migrations.RemoveConstraint(
            model_name="credential",
            name="unique_service_per_vault",
        ),
        migrations.AddConstraint(
            model_name="credential",
            constraint=models.UniqueConstraint(
                Lower("service_name"),
                "vault",
                name="unique_service_per_vault_ci",
            ),
        ),
    ]
