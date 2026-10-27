from django.db import migrations, models
from django.db.models import Count
from django.db.models.functions import Lower


def ensure_case_insensitive_usernames_are_unique(apps, schema_editor):
    """Refuse a potentially destructive index migration if legacy collisions exist."""
    User = apps.get_model("user_app", "CustomUser")
    database = schema_editor.connection.alias
    duplicates = (
        User.objects.using(database)
        .annotate(normalized_username=Lower("username"))
        .values("normalized_username")
        .annotate(total=Count("pk"))
        .filter(total__gt=1)
    )
    if duplicates.exists():
        raise RuntimeError(
            "Cannot add case-insensitive username uniqueness: existing users have "
            "usernames that differ only by case. Resolve those accounts, then rerun migrations."
        )


class Migration(migrations.Migration):
    dependencies = [
        ("user_app", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            ensure_case_insensitive_usernames_are_unique,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="customuser",
            constraint=models.UniqueConstraint(
                Lower("username"),
                name="unique_username_case_insensitive",
            ),
        ),
    ]
