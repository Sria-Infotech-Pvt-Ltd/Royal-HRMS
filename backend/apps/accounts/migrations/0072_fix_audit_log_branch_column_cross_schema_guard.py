"""
0063_auditlog_add_branch and 0065_fix_audit_log_branch_not_null both guard
their DDL with:

    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'hrms_audit_logs' AND column_name = 'branch'

— unqualified by table_schema. information_schema.columns is NOT filtered
by the connection's search_path; it lists every schema's tables
system-wide. In this multi-tenant database (one schema per company, see
apps/tenants/), that means as soon as ANY ONE tenant's
hrms_audit_logs.branch column exists (tenant_royalhrms's does), both
guards misfire for EVERY OTHER tenant being migrated:

  - 0063 thinks its own tenant's column already exists → skips ADD COLUMN.
  - 0065_fix then runs `ALTER COLUMN branch DROP NOT NULL` on a column that
    was just skipped above → fails with "column branch does not exist".

This is what broke provisioning every new tenant created after
tenant_royalhrms already carried this column (see apps/tenants/services.py
provision_company, and manage.py create_company which calls it).

Also: tenant_royalhrms itself never actually got its NOT NULL constraint
dropped by 0065_fix — checked directly, still NOT NULL there — a separate
symptom of the same cross-schema guard always matching "some tenant has
this column" regardless of which schema is actually being migrated.

Fix: redo both operations here, this time scoped to
`table_schema = current_schema()` so each schema's migration is evaluated
against its OWN state, independent of every other tenant's schema.
"""
from django.db import migrations


def fix_cross_schema_drift(apps, schema_editor):
    # Postgres-multi-tenant-schema-only drift fix (see module docstring) —
    # no meaning on SQLite (no schema concept, no tenant provisioning path).
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = 'hrms_audit_logs'
                      AND column_name = 'branch'
                ) THEN
                    ALTER TABLE hrms_audit_logs ADD COLUMN branch varchar(100) NULL DEFAULT '';
                ELSIF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = 'hrms_audit_logs'
                      AND column_name = 'branch'
                      AND is_nullable = 'NO'
                ) THEN
                    ALTER TABLE hrms_audit_logs ALTER COLUMN branch DROP NOT NULL;
                END IF;
            END $$;
        """)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0071_merge_20260814_1214"),
    ]

    operations = [
        migrations.RunPython(fix_cross_schema_drift, migrations.RunPython.noop),
    ]
