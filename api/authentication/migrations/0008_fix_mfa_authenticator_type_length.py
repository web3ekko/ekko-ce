# Generated manually to fix django-allauth MFA authenticator type field length

from django.db import migrations


def forwards_fix_mfa_authenticator_type_length(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("ALTER TABLE mfa_authenticator ALTER COLUMN type TYPE VARCHAR(50);")


def backwards_fix_mfa_authenticator_type_length(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("ALTER TABLE mfa_authenticator ALTER COLUMN type TYPE VARCHAR(20);")


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0007_remove_dead_models'),
        ('mfa', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            code=forwards_fix_mfa_authenticator_type_length,
            reverse_code=backwards_fix_mfa_authenticator_type_length,
        ),
    ]
