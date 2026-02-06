# Generated manually to remove dead models and attempt tracking

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("authentication", "0006_add_email_verification_code"),
    ]

    operations = [
        # Remove attempts field from EmailVerificationCode
        migrations.RemoveField(
            model_name="emailverificationcode",
            name="attempts",
        ),
        # Delete dead models
        migrations.DeleteModel(
            name="EmailMagicLink",
        ),
        migrations.DeleteModel(
            name="PasskeyCredential",
        ),
        migrations.DeleteModel(
            name="UserSession",
        ),
        migrations.DeleteModel(
            name="CrossDeviceSession",
        ),
        migrations.DeleteModel(
            name="RecoveryCode",
        ),
    ]