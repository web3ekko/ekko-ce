# Generated manually to fix authentication log method field length

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0008_fix_mfa_authenticator_type_length'),
    ]

    operations = [
        migrations.AlterField(
            model_name='authenticationlog',
            name='method',
            field=models.CharField(max_length=50),
        ),
    ]