"""
0063_auditlog_add_branch's own ADD COLUMN is guarded by an unqualified
`SELECT 1 FROM information_schema.columns WHERE table_name =
'hrms_audit_logs' AND column_name = 'branch'` — not filtered by
table_schema. information_schema.columns lists every schema's tables
system-wide, so as soon as ANY ONE tenant (tenant_royalhrms) has this
column, that check wrongly reads as "already exists" for every OTHER
tenant being migrated, and 0063 silently skips adding the column for them.

Then 0065_fix_audit_log_branch_not_null runs its own (equally unqualified)
"IF EXISTS -> ALTER COLUMN branch DROP NOT NULL", which fails outright
with "column branch does not exist" for any tenant schema that never
actually got the column — breaking provisioning of every new company
created after tenant_royalhrms (see apps/tenants/services.py
provision_company / manage.py create_company).

0063 and 0065_fix are both already-applied, already-committed migrations
(can't edit them — see CLAUDE.md). `run_before` slots this migration in
between them in the dependency graph instead, so it can add the column
correctly (scoped to the CURRENT schema only) before 0065_fix's ALTER ever
runs against a schema that doesn't have it yet. Also see
0072_fix_audit_log_branch_column_cross_schema_guard, which repairs the
same class of drift for schemas where the column already existed but was
never actually made nullable (e.g. tenant_royalhrms itself).
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0063_auditlog_add_branch"),
    ]

    run_before = [
        ("accounts", "0065_fix_audit_log_branch_not_null"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = current_schema()
                          AND table_name = 'hrms_audit_logs'
                          AND column_name = 'branch'
                    ) THEN
                        ALTER TABLE hrms_audit_logs ADD COLUMN branch varchar(100) NULL DEFAULT '';
                    END IF;
                END $$;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
