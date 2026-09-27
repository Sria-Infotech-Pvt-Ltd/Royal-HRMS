from django.db import migrations


def drop_not_null(apps, schema_editor):
    # Postgres-only schema-drift fix (see module docstring) — SQLite never
    # picked up that drift (0063_auditlog_add_branch's sqlite branch already
    # adds the column matching the model field's blank=True, no null=True),
    # so there's nothing to fix there.
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'hrms_audit_logs' AND column_name = 'branch'
                ) THEN
                    ALTER TABLE hrms_audit_logs ALTER COLUMN branch DROP NOT NULL;
                END IF;
            END $$;
        """)


class Migration(migrations.Migration):
    """
    `hrms_audit_logs.branch` exists on production with a NOT NULL constraint
    but was never part of any Django migration or model field — the
    AuditLog model (see 0001_initial.py) has no `branch` field, and no view
    anywhere in the codebase passes `branch=` to AuditLog.objects.create().
    Classic schema drift: added directly against the DB at some point,
    never cleaned up. It blocks every AuditLog insert with no branch kwarg,
    including the login audit log write in accounts/views.py, which made
    every login 500.

    No-op if the column doesn't exist or is already nullable on a given
    environment (e.g. local dev DBs that never picked up the drift).
    """

    dependencies = [
        ("accounts", "0064_merge_20260812_1213"),
    ]

    operations = [
        migrations.RunPython(drop_not_null, migrations.RunPython.noop),
    ]
