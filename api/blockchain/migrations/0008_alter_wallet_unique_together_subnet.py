from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        (
            "blockchain",
            "0007_alter_walletgroupmembership_unique_together_and_more",
        ),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="wallet",
            unique_together={("blockchain", "subnet", "address")},
        ),
    ]

