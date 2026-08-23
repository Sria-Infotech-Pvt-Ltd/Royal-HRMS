from django.db import migrations

# 0047_role_add_can_manage_team added the flag with default=False and never
# backfilled it onto the pre-existing 'manager' role. Every downstream
# consumer that resolves "who is the L1/manager approver" — most importantly
# 0049_approval_workflow_role_fk's _find_manager_role(), which sets
# ApprovalWorkflowRule.l1_approver_role for leave/expense/attendance-correction
# workflows — filters on can_manage_team=True and silently found nothing,
# leaving l1_approver_role NULL for every company provisioned since. The
# practical effect: every request meant to stop at the employee's manager for
# L1 approval instead skips straight to L2 (HR), and no one shows up in the
# "Reporting Manager" / "Reporting Approver" pickers on the employee profile
# (ManagerListView filters on the same flag). Backfilling this here fixes
# both already-provisioned tenants and — since ApprovalWorkflowRule.
# l1_approver_role is only resolved once, at that earlier migration's RunPython
# step — any tenant provisioned before this migration needs its
# ApprovalWorkflowRule rows re-pointed too, done below.


def fix_manager_role(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    updated = Role.objects.filter(name='manager', can_manage_team=False).update(can_manage_team=True)
    if not updated:
        return

    ApprovalWorkflowRule = apps.get_model('accounts', 'ApprovalWorkflowRule')
    manager_role = Role.objects.filter(name='manager', is_active=True).order_by('id').first()
    if not manager_role:
        return
    fixed_types = list(
        ApprovalWorkflowRule.objects
        .filter(l1_approver_role__isnull=True)
        .values_list('workflow_type', flat=True)
    )
    ApprovalWorkflowRule.objects.filter(l1_approver_role__isnull=True).update(l1_approver_role=manager_role)

    # ApprovalWorkflowCacheService caches each rule for 6h (core/cache_service.py)
    # and is only invalidated by the settings-UI update path — a raw migration
    # write like this one never touches it, so without this an already-running
    # server keeps resolving l1_approver_role from the stale cached object
    # (still None) for up to 6h after this migration deploys.
    from core.cache_service import ApprovalWorkflowCacheService
    for workflow_type in fixed_types:
        ApprovalWorkflowCacheService.invalidate(workflow_type)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0089_alter_employeecodesettings_prefix'),
    ]

    operations = [
        migrations.RunPython(fix_manager_role, noop),
    ]
