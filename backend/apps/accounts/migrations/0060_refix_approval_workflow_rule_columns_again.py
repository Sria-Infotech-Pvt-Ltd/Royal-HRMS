"""
Re-fix hrms_approval_workflow_rules.l1_approver_role / l2_approver_role — 3rd time.

0058 and 0059 already did this exact conversion (FK columns -> plain
CharFields) and were each verified working, but the ghost migration
accounts.0049_approval_workflow_role_fk (no corresponding file anywhere in
this repo's history/branches/stash) has now reapplied itself TWICE against
this shared Neon dev database — once at 2026-08-05 10:30:49 (undoing 0058),
again at 2026-08-05 11:54:55 (undoing 0059, 35 minutes after it was applied).
Some other, uncommitted local checkout is periodically running `manage.py
migrate` against this same shared database (other unrecognized migrations —
attendance.0025/0026, payroll.0011/0012 — landed in the same window), and
every time it does, this table's columns flip back to the FK style.

0058 and 0059 are already marked applied in django_migrations, so a plain
`migrate` won't re-run either of them even though their effect keeps getting
reverted at the database level. This migration reapplies the same fix again.
The old role FK ids are still intact (verified: l1_approver_role_id=9 -> role
"manager__team_lead", l2_approver_role_id=7 -> role "hr" on all 3 rows), so
the same name-prefix backfill mapping from 0058/0059 is reused.

This is a stopgap, not a real fix — if whatever is running migrate against
this shared database keeps doing so, this will break a fourth time. The
actual fix is for that other checkout to stop running migrate against the
shared Neon instance, or for its migration to be reconciled into this
branch's history properly.

Split into separate non-atomic steps for the same reason as 0058: Postgres
refuses ALTER TABLE ... DROP COLUMN in the same transaction as the preceding
UPDATEs that touch the table's foreign-keyed columns.
"""
from django.db import migrations

ADD_COLUMNS_SQL = """
ALTER TABLE hrms_approval_workflow_rules ADD COLUMN IF NOT EXISTS l1_approver_role varchar(20);
ALTER TABLE hrms_approval_workflow_rules ADD COLUMN IF NOT EXISTS l2_approver_role varchar(20);
"""
ADD_COLUMNS_REVERSE_SQL = """
ALTER TABLE hrms_approval_workflow_rules DROP COLUMN IF EXISTS l1_approver_role;
ALTER TABLE hrms_approval_workflow_rules DROP COLUMN IF EXISTS l2_approver_role;
"""

BACKFILL_SQL = """
UPDATE hrms_approval_workflow_rules t
SET l1_approver_role = CASE
    WHEN r.name ILIKE 'manager%%'                    THEN 'reporting_manager'
    WHEN r.name ILIKE 'hr%%'                          THEN 'hr_manager'
    WHEN r.name IN ('system_admin', 'admin')          THEN 'admin'
    ELSE 'reporting_manager'
END
FROM hrms_roles r
WHERE r.id = t.l1_approver_role_id;

UPDATE hrms_approval_workflow_rules t
SET l2_approver_role = CASE
    WHEN r.name ILIKE 'manager%%'                    THEN 'reporting_manager'
    WHEN r.name ILIKE 'hr%%'                          THEN 'hr_manager'
    WHEN r.name IN ('system_admin', 'admin')          THEN 'admin'
    ELSE ''
END
FROM hrms_roles r
WHERE r.id = t.l2_approver_role_id;

UPDATE hrms_approval_workflow_rules SET l1_approver_role = 'reporting_manager' WHERE l1_approver_role IS NULL;
UPDATE hrms_approval_workflow_rules SET l2_approver_role = ''                  WHERE l2_approver_role IS NULL;
"""

CONSTRAIN_COLUMNS_SQL = """
ALTER TABLE hrms_approval_workflow_rules ALTER COLUMN l1_approver_role SET NOT NULL;
ALTER TABLE hrms_approval_workflow_rules ALTER COLUMN l1_approver_role SET DEFAULT 'reporting_manager';
ALTER TABLE hrms_approval_workflow_rules ALTER COLUMN l2_approver_role SET NOT NULL;
ALTER TABLE hrms_approval_workflow_rules ALTER COLUMN l2_approver_role SET DEFAULT '';
"""

DROP_OLD_COLUMNS_SQL = """
ALTER TABLE hrms_approval_workflow_rules DROP CONSTRAINT IF EXISTS hrms_approval_workfl_l1_approver_role_id_920595ef_fk_hrms_role;
ALTER TABLE hrms_approval_workflow_rules DROP CONSTRAINT IF EXISTS hrms_approval_workfl_l2_approver_role_id_b1709865_fk_hrms_role;
ALTER TABLE hrms_approval_workflow_rules DROP COLUMN IF EXISTS l1_approver_role_id;
ALTER TABLE hrms_approval_workflow_rules DROP COLUMN IF EXISTS l2_approver_role_id;
"""
DROP_OLD_COLUMNS_REVERSE_SQL = """
ALTER TABLE hrms_approval_workflow_rules ADD COLUMN l1_approver_role_id bigint;
ALTER TABLE hrms_approval_workflow_rules ADD COLUMN l2_approver_role_id bigint;
"""


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('accounts', '0059_refix_approval_workflow_rule_columns'),
    ]

    operations = [
        migrations.RunSQL(sql=ADD_COLUMNS_SQL, reverse_sql=ADD_COLUMNS_REVERSE_SQL),
        migrations.RunSQL(sql=BACKFILL_SQL, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(sql=CONSTRAIN_COLUMNS_SQL, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(sql=DROP_OLD_COLUMNS_SQL, reverse_sql=DROP_OLD_COLUMNS_REVERSE_SQL),
    ]
