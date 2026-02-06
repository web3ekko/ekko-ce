from __future__ import annotations

from django.db import migrations


LEGACY_COLUMNS = [
    # v1 authoring / classification fields
    "event_type",
    "sub_event",
    "nl_template",
    "spec_blueprint",
    "variables",
    # v1 analytics/versioning fields
    "usage_count",
    "version",
    # historical v1/vNext fields that are not part of AlertTemplate v2
    "template_type",
    "source",
    "scope_chain",
    "scope_network",
    "semantic_fingerprint",
    "spec_hash",  # legacy spec hash (v1). v2 hash lives on AlertTemplateVersion.
    "ir_v1_spec",
    "validation_schema",
]


def drop_legacy_columns(apps, schema_editor) -> None:
    """
    The vNext AlertTemplate v2 model reuses the `alert_templates` table name.

    Earlier iterations of the app stored v1 authoring fields on the same table
    with NOT NULL constraints. The v2 model no longer includes those columns,
    so we must remove them to avoid insert failures (e.g., event_type is NOT NULL).
    """

    vendor = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        for col in LEGACY_COLUMNS:
            if vendor == "postgresql":
                cursor.execute(f'ALTER TABLE "alert_templates" DROP COLUMN IF EXISTS "{col}";')
                continue

            if vendor == "sqlite":
                # SQLite doesn't support IF EXISTS on DROP COLUMN; ignore missing columns.
                try:
                    cursor.execute(f'ALTER TABLE "alert_templates" DROP COLUMN "{col}";')
                except Exception as exc:  # pragma: no cover - vendor-specific
                    msg = str(exc).lower()
                    if "no such column" in msg or "does not exist" in msg:
                        continue
                    raise
                continue

            # Best-effort for other DBs.
            try:
                cursor.execute(f'ALTER TABLE "alert_templates" DROP COLUMN "{col}";')
            except Exception:
                continue


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0021_alert_templates_v2"),
    ]

    operations = [
        migrations.RunPython(drop_legacy_columns, reverse_code=migrations.RunPython.noop),
    ]

