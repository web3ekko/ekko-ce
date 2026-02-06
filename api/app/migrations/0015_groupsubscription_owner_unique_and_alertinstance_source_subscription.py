from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0014_add_alerttemplate_ir_v1_spec"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="groupsubscription",
            unique_together={("owner", "alert_group", "target_group")},
        ),
        migrations.AddField(
            model_name="alertinstance",
            name="source_subscription",
            field=models.ForeignKey(
                blank=True,
                help_text="If set, this alert was created/managed by a GroupSubscription",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="alert_instances",
                to="app.groupsubscription",
            ),
        ),
    ]

