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

    operations = [
        migrations.RunPython(seed_leave_workflow, migrations.RunPython.noop),
    ]
