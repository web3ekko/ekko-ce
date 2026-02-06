from __future__ import annotations

from django.db import migrations


MORE_LEGACY_COLUMNS = [
    # v1/v1.5 classification + scoping columns that were required by older codepaths.
    "alert_type",
    "scope_chain",
    "scope_network",
    "similarity_group",
]


def drop_more_legacy_columns(apps, schema_editor) -> None:
    vendor = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        for col in MORE_LEGACY_COLUMNS:
            if vendor == "postgresql":
                cursor.execute(f'ALTER TABLE "alert_templates" DROP COLUMN IF EXISTS "{col}";')
                continue
            if vendor == "sqlite":
                try:
                    cursor.execute(f'ALTER TABLE "alert_templates" DROP COLUMN "{col}";')
                except Exception as exc:  # pragma: no cover
                    msg = str(exc).lower()
                    if "no such column" in msg or "does not exist" in msg:
                        continue
                    raise
                continue
            try:
                cursor.execute(f'ALTER TABLE "alert_templates" DROP COLUMN "{col}";')
            except Exception:
                continue


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0022_drop_legacy_alert_template_columns"),
    ]

    operations = [
        migrations.RunPython(drop_more_legacy_columns, reverse_code=migrations.RunPython.noop),
    ]

