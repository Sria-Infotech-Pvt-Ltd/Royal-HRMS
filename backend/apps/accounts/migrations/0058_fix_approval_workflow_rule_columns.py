"""
Fix hrms_approval_workflow_rules.l1_approver_role / l2_approver_role.

0026_approval_matrix_reporting_manager.py has always declared these as plain
CharFields (choices 'reporting_manager' / 'hr_manager' / 'admin') — no
migration in this history ever made them ForeignKeys. But this database's
physical columns are l1_approver_role_id / l2_approver_role_id, real bigint
foreign keys to hrms_roles.id — the same class of drift as the aadhaar/uan
columns (0052) and the can_manage_branch column (0049/0053 --fake): the
physical table was built from a different, since-diverged branch history
that modeled the approver as an actual Role FK before this branch settled on
a fixed set of string choices instead.

Every read of this table (ApprovalWorkflowCacheService.get_rule, the Approval
Matrix tab, leave/expense/attendance-correction approval-chain resolution —
anywhere _resolve_approval_chain or _resolve_rule_approver runs) has been
crashing with "column ... l1_approver_role does not exist" because Django's
ORM, following the current model, only knows how to ask for that column name.

Rather than just resetting existing rows to the model's bare default, this
maps each row's old Role FK to the equivalent choice string (by role name
prefix) so whatever was actually configured — e.g. "Manager approves L1,
then HR approves L2" — survives the column swap instead of silently
reverting to "reporting_manager" for everyone.

Split into separate non-atomic steps (rather than one transaction) because
Postgres refuses an ALTER TABLE ... DROP COLUMN on this table in the same
transaction as the preceding UPDATEs that touch its foreign-keyed columns
("cannot ALTER TABLE because it has pending trigger events") — each step
here commits before the next runs.
"""
from django.db import migrations

ADD_COLUMNS_SQL = """
ALTER TABLE hrms_approval_workflow_rules ADD COLUMN l1_approver_role varchar(20);
ALTER TABLE hrms_approval_workflow_rules ADD COLUMN l2_approver_role varchar(20);
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
# Best-effort only — the original Role FK relationship can't be reconstructed
# from a choice string, so reversing just recreates nullable FK columns with
# no data rather than trying to guess role ids back from strings.
DROP_OLD_COLUMNS_REVERSE_SQL = """
ALTER TABLE hrms_approval_workflow_rules ADD COLUMN l1_approver_role_id bigint;
ALTER TABLE hrms_approval_workflow_rules ADD COLUMN l2_approver_role_id bigint;
"""


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('accounts', '0057_backfill_onboarding_approved_template'),
    ]

    operations = [
        migrations.RunSQL(sql=ADD_COLUMNS_SQL, reverse_sql=ADD_COLUMNS_REVERSE_SQL),
        migrations.RunSQL(sql=BACKFILL_SQL, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(sql=CONSTRAIN_COLUMNS_SQL, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(sql=DROP_OLD_COLUMNS_SQL, reverse_sql=DROP_OLD_COLUMNS_REVERSE_SQL),
    ]
