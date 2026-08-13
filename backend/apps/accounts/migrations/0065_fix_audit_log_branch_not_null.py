from django.db import migrations


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
        migrations.RunSQL(
            sql="""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'hrms_audit_logs' AND column_name = 'branch'
                    ) THEN
                        ALTER TABLE hrms_audit_logs ALTER COLUMN branch DROP NOT NULL;
                    END IF;
                END $$;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
