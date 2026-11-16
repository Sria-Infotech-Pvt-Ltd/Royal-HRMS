"""
Seed the default approval rule for weekly timesheets: the reporting manager decides (L1), with the employee's HR partner
as the fallback (L2) for a manager's own sheet or someone with no manager. `get_or_create`, so a rule an admin has
already configured is never overwritten. Admins change it in the existing approval-workflow settings.
"""
from django.db import migrations


def seed_rule(apps, schema_editor):
    ApprovalWorkflowRule = apps.get_model('accounts', 'ApprovalWorkflowRule')
    ApprovalWorkflowRule.objects.get_or_create(
        workflow_type='timesheet',
        defaults={'l1_approver_kind': 'reporting_manager', 'l2_approver_kind': 'hr'},
    )


def remove_rule(apps, schema_editor):
    # Only the untouched default is removed; a rule an admin changed is left in place.
    ApprovalWorkflowRule = apps.get_model('accounts', 'ApprovalWorkflowRule')
    ApprovalWorkflowRule.objects.filter(
        workflow_type='timesheet', l1_approver_kind='reporting_manager', l2_approver_kind='hr', updated_by__isnull=True,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0223_timesheet_workflow_type'),
    ]

    operations = [
        migrations.RunPython(seed_rule, remove_rule),
    ]
