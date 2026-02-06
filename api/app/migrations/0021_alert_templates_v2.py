from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    """
    Introduce vNext AlertTemplate + AlertTemplateVersion while keeping the existing
    `alert_templates` table name.

    This migration uses SeparateDatabaseAndState so we can:
    - upgrade the Django model state to the new vNext schema, and
    - add only the new required DB columns/tables, without attempting to fully
      drop legacy columns on `alert_templates` (safe for dev; avoids large SQL diffs).
    """

    dependencies = [
        ("app", "0020_add_billing_and_developer_models"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            # Django model state (authoritative for new code).
            state_operations=[
                migrations.DeleteModel(name="AlertTemplate"),
                migrations.CreateModel(
                    name="AlertTemplate",
                    fields=[
                        ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                        ("fingerprint", models.CharField(max_length=80, db_index=True, help_text="sha256:... semantic fingerprint")),
                        ("name", models.CharField(max_length=255)),
                        ("description", models.TextField(blank=True)),
                        ("target_kind", models.CharField(max_length=32, default="wallet")),
                        ("is_public", models.BooleanField(default=False)),
                        ("is_verified", models.BooleanField(default=False)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "created_by",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="created_alert_templates",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={"db_table": "alert_templates"},
                ),
                migrations.CreateModel(
                    name="AlertTemplateVersion",
                    fields=[
                        ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                        (
                            "template",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="versions",
                                to="app.alerttemplate",
                            ),
                        ),
                        ("template_version", models.IntegerField()),
                        ("template_spec", models.JSONField(help_text="AlertTemplate JSON (schema_version=alert_template_v2)")),
                        ("spec_hash", models.CharField(max_length=80, help_text="sha256:... canonical template spec hash")),
                        ("executable_id", models.UUIDField(help_text="Deterministic UUIDv5 for the pinned executable")),
                        ("executable", models.JSONField(help_text="AlertExecutable JSON (schema_version=alert_executable_v1)")),
                        ("registry_snapshot_kind", models.CharField(max_length=64, default="datasource_catalog")),
                        ("registry_snapshot_version", models.CharField(max_length=64, default="v1")),
                        ("registry_snapshot_hash", models.CharField(max_length=80)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                    ],
                    options={
                        "db_table": "alert_template_versions",
                        "unique_together": {("template", "template_version")},
                    },
                ),
                migrations.AddField(
                    model_name="alertinstance",
                    name="template_version",
                    field=models.IntegerField(
                        blank=True,
                        null=True,
                        help_text="Pinned template_version for executable-backed alerts (vNext).",
                    ),
                ),
            ],
            # Database operations (minimal physical changes).
            database_operations=[
                migrations.AddField(
                    model_name="alerttemplate",
                    name="fingerprint",
                    field=models.CharField(
                        max_length=80,
                        db_index=True,
                        default="sha256:" + "0" * 64,
                        help_text="sha256:... semantic fingerprint",
                    ),
                    preserve_default=False,
                ),
                migrations.AddField(
                    model_name="alerttemplate",
                    name="target_kind",
                    field=models.CharField(max_length=32, default="wallet"),
                    preserve_default=False,
                ),
                migrations.CreateModel(
                    name="AlertTemplateVersion",
                    fields=[
                        ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                        (
                            "template",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="versions",
                                to="app.alerttemplate",
                            ),
                        ),
                        ("template_version", models.IntegerField()),
                        ("template_spec", models.JSONField(help_text="AlertTemplate JSON (schema_version=alert_template_v2)")),
                        ("spec_hash", models.CharField(max_length=80, help_text="sha256:... canonical template spec hash")),
                        ("executable_id", models.UUIDField(help_text="Deterministic UUIDv5 for the pinned executable")),
                        ("executable", models.JSONField(help_text="AlertExecutable JSON (schema_version=alert_executable_v1)")),
                        ("registry_snapshot_kind", models.CharField(max_length=64, default="datasource_catalog")),
                        ("registry_snapshot_version", models.CharField(max_length=64, default="v1")),
                        ("registry_snapshot_hash", models.CharField(max_length=80)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                    ],
                    options={
                        "db_table": "alert_template_versions",
                        "unique_together": {("template", "template_version")},
                    },
                ),
                migrations.AddField(
                    model_name="alertinstance",
                    name="template_version",
                    field=models.IntegerField(
                        blank=True,
                        null=True,
                        help_text="Pinned template_version for executable-backed alerts (vNext).",
                    ),
                ),
                migrations.AddIndex(
                    model_name="alerttemplate",
                    index=models.Index(fields=["created_by"], name="at2_created_by_idx"),
                ),
                migrations.AddIndex(
                    model_name="alerttemplate",
                    index=models.Index(fields=["is_public", "is_verified"], name="at2_visibility_idx"),
                ),
                migrations.AddIndex(
                    model_name="alerttemplate",
                    index=models.Index(fields=["fingerprint"], name="at2_fingerprint_idx"),
                ),
                migrations.AddIndex(
                    model_name="alerttemplateversion",
                    index=models.Index(fields=["template", "template_version"], name="atv_template_ver_idx"),
                ),
                migrations.AddIndex(
                    model_name="alerttemplateversion",
                    index=models.Index(fields=["registry_snapshot_hash"], name="atv_snapshot_hash_idx"),
                ),
                migrations.AddIndex(
                    model_name="alertinstance",
                    index=models.Index(fields=["template"], name="ai_template_idx"),
                ),
            ],
        )
    ]

