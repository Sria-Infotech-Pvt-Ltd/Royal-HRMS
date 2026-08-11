from django.db import migrations


def seed_leave_workflow(apps, schema_editor):
    """
    Ensure the leave ApprovalWorkflowRule exists and enforces a two-level chain:
      L1 = reporting_manager (employee's direct manager)
      L2 = hr_manager        (employee's assigned HR)
    Uses update_or_create so re-running is idempotent.
    """
    ApprovalWorkflowRule = apps.get_model('accounts', 'ApprovalWorkflowRule')
    ApprovalWorkflowRule.objects.update_or_create(
        workflow_type='leave',
        defaults={
            'l1_approver_role': 'reporting_manager',
            'l2_approver_role': 'hr_manager',
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('hrms', '0012_holiday_is_optional'),
        ('accounts', '0042_clean_employee_role_permissions'),
    ]

    # accounts/0049 later converts l1_approver_role/l2_approver_role from
    # CharField to ForeignKey(Role); this seed assigns raw strings and must
    # run while the fields are still CharFields. Without this, a fresh
    # migrate can schedule 0049 first and crash here. Exception to the
    # no-edits-to-applied-migrations rule, approved 2026-08-11 — additive
    # only (no change to operations), so it has no effect on databases
    # where this migration has already run.
    run_before = [
        ('accounts', '0049_approval_workflow_role_fk'),
    ]

    operations = [
        migrations.RunPython(seed_leave_workflow, migrations.RunPython.noop),
    ]
