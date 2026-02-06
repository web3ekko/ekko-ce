from __future__ import annotations

from django.db import migrations


V2_COLUMNS = {
    # v2 model columns (apps/api/app/models/alert_templates.py)
    "id",
    "fingerprint",
    "name",
    "description",
    "target_kind",
    "is_public",
    "is_verified",
    "created_by_id",
    "created_at",
    "updated_at",
}


def cleanup_alert_templates_table_v2(apps, schema_editor) -> None:
    """
    Ensure the physical `alert_templates` table matches AlertTemplate v2.

    Background:
    - AlertTemplate v2 reuses the same table name as the legacy v1 model.
    - Earlier migrations attempted to DROP legacy columns on SQLite via
      `ALTER TABLE ... DROP COLUMN`, but SQLite rejects the operation when
      the column participates in an index/constraint.
    - The failure mode looks like "error in index ... after drop column",
      which we must treat as a real failure (not "column doesn't exist").

    This migration:
    - Detects any extra columns (anything not in V2_COLUMNS).
    - Drops any indexes that reference those columns (except PK autoindex).
    - Drops the columns themselves.
    """

    vendor = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        if vendor == "sqlite":
            cursor.execute("PRAGMA table_info('alert_templates');")
            existing_cols = [row[1] for row in cursor.fetchall()]
            extra_cols = [c for c in existing_cols if c not in V2_COLUMNS]

            if not extra_cols:
                return

            # Drop any indexes referencing extra columns to make DROP COLUMN succeed.
            cursor.execute("PRAGMA index_list('alert_templates');")
            index_names = [row[1] for row in cursor.fetchall()]
            for idx_name in index_names:
                if idx_name.startswith("sqlite_autoindex_"):
                    continue
                cursor.execute(f"PRAGMA index_info('{idx_name}');")
                idx_cols = [row[2] for row in cursor.fetchall()]
                if any(col in extra_cols for col in idx_cols):
                    cursor.execute(f'DROP INDEX IF EXISTS "{idx_name}";')

            for col in extra_cols:
                cursor.execute(f'ALTER TABLE "alert_templates" DROP COLUMN "{col}";')

            return

        # Postgres and other DBs: best-effort DROP COLUMN with IF EXISTS.
        # Postgres will cascade-drop dependent indexes/constraints automatically.
        for col in [
            "event_type",
            "sub_event",
            "nl_template",
            "spec_blueprint",
            "variables",
            "usage_count",
            "version",
            "template_type",
            "source",
            "scope_chain",
            "scope_network",
            "semantic_fingerprint",
            "spec_hash",
            "ir_v1_spec",
            "validation_schema",
            "alert_type",
            "similarity_group",
            "spec",
        ]:
            try:
                if vendor == "postgresql":
                    cursor.execute(f'ALTER TABLE "alert_templates" DROP COLUMN IF EXISTS "{col}" CASCADE;')
                else:
                    cursor.execute(f'ALTER TABLE "alert_templates" DROP COLUMN "{col}";')
            except Exception:
                continue


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0023_drop_more_legacy_alert_template_columns"),
    ]

    operations = [
        migrations.RunPython(cleanup_alert_templates_table_v2, reverse_code=migrations.RunPython.noop),
    ]

