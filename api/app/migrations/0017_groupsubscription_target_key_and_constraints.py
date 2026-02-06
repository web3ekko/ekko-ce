import inspect

from django.db import migrations, models
import django.db.models.deletion


def _check_constraint_kwargs(condition):
    params = inspect.signature(models.CheckConstraint).parameters
    if "condition" in params:
        return {"condition": condition}
    return {"check": condition}


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0016_alertinstance_disabled_by_subscription"),
    ]

    operations = [
        migrations.AddField(
            model_name="groupsubscription",
            name="target_key",
            field=models.CharField(
                blank=True,
                help_text="Optional single target key (e.g., 'ETH:mainnet:0x123...') when not targeting a group",
                max_length=255,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="groupsubscription",
            name="target_group",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="subscribed_to_alerts",
                to="app.genericgroup",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="groupsubscription",
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name="groupsubscription",
            constraint=models.CheckConstraint(
                **_check_constraint_kwargs(
                    (models.Q(target_group__isnull=False, target_key__isnull=True))
                    | (models.Q(target_group__isnull=True, target_key__isnull=False))
                ),
                name="groupsubscription_exactly_one_target",
            ),
        ),
        migrations.AddConstraint(
            model_name="groupsubscription",
            constraint=models.CheckConstraint(
                **_check_constraint_kwargs(
                    models.Q(target_key__isnull=True) | ~models.Q(target_key="")
                ),
                name="groupsubscription_target_key_not_blank",
            ),
        ),
        migrations.AddConstraint(
            model_name="groupsubscription",
            constraint=models.UniqueConstraint(
                condition=models.Q(target_group__isnull=False),
                fields=("owner", "alert_group", "target_group"),
                name="unique_groupsubscription_owner_alert_group_target_group",
            ),
        ),
        migrations.AddConstraint(
            model_name="groupsubscription",
            constraint=models.UniqueConstraint(
                condition=models.Q(target_key__isnull=False),
                fields=("owner", "alert_group", "target_key"),
                name="unique_groupsubscription_owner_alert_group_target_key",
            ),
        ),
    ]
