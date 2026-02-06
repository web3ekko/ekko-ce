from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "app",
            "0015_groupsubscription_owner_unique_and_alertinstance_source_subscription",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="alertinstance",
            name="disabled_by_subscription",
            field=models.BooleanField(
                default=False,
                help_text="True if this alert was disabled by its GroupSubscription (not a user override).",
            ),
        ),
    ]

