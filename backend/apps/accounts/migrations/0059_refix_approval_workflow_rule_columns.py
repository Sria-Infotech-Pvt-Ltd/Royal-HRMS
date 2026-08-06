"""
Re-fix hrms_approval_workflow_rules.l1_approver_role / l2_approver_role.

0058_fix_approval_workflow_rule_columns already did this exact conversion
(FK columns -> plain CharFields), and was verified working. Since then, this
shared Neon dev database's migration history picked up an extra row:

    accounts | 0049_approval_workflow_role_fk | applied 2026-08-05 10:30:49

There is no file named 0049_approval_workflow_role_fk.py anywhere in this
repo's history, any local branch, or any stash — `git log --all` and
`git branch -a` both come up empty. The only explanation is a different,
uncommitted local checkout (this project has ~15 active branches sharing one
Neon database) ran `manage.py migrate` with a local-only migration that
re-added the FK-style l1_approver_role_id/l2_approver_role_id columns and
dropped the string columns 0058 had put in place, without ever committing
that file. Since Django's migration graph is built from files on disk, that
ghost row doesn't show up in `showmigrations` and doesn't error — it just
silently undid 0058's schema fix while the row itself is dangling.

0058 is already marked applied in django_migrations, so a plain `migrate`
won't re-run it even though its effect has been reverted at the database
level. This migration reapplies the same fix as a fresh operation. The old
role FK ids are still intact (verified: l1_approver_role_id=9 -> role
"manager__team_lead", l2_approver_role_id=7 -> role "hr" on all 3 rows), so
the same name-prefix backfill mapping from 0058 is reused.

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
        ('accounts', '0058_fix_approval_workflow_rule_columns'),
    ]

    operations = [
        migrations.RunSQL(sql=ADD_COLUMNS_SQL, reverse_sql=ADD_COLUMNS_REVERSE_SQL),
        migrations.RunSQL(sql=BACKFILL_SQL, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(sql=CONSTRAIN_COLUMNS_SQL, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(sql=DROP_OLD_COLUMNS_SQL, reverse_sql=DROP_OLD_COLUMNS_REVERSE_SQL),
    ]
