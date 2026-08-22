"""
Seed wfh.view / wfh.create / wfh.approve permissions, granted to the same
roles that currently hold the equivalent leave.* permission (verified
against live data, not the original — since drifted — seed migration), and
seed the 'wfh' ApprovalWorkflowRule by copying whichever roles the existing
'leave' rule already uses for L1/L2 — deliberate mirroring of leave's
routing per product decision, and avoids hardcoding a role name that could
drift the same way 'reporting_manager'/'hr_manager' already did in
0013_seed_leave_approval_workflow.
"""
from django.db import migrations

PERMISSIONS = [
    ('wfh', 'view',    'wfh.view'),
    ('wfh', 'create',  'wfh.create'),
    ('wfh', 'approve', 'wfh.approve'),
]

# Codename this permission mirrors -> which new wfh permission gets the same roles.
MIRROR_OF = {
    'wfh.view':    'leave.view',
    'wfh.create':  'leave.create',
    'wfh.approve': 'leave.approve',
}


def seed_forward(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')
    ApprovalWorkflowRule = apps.get_model('accounts', 'ApprovalWorkflowRule')

    perm_objs = {}
    for module, action, codename in PERMISSIONS:
        perm, _ = Permission.objects.get_or_create(
            codename=codename, defaults={'module': module, 'action': action},
        )
        perm_objs[codename] = perm

    for wfh_codename, mirror_codename in MIRROR_OF.items():
        mirror_perm = Permission.objects.filter(codename=mirror_codename).first()
        if not mirror_perm:
            continue
        role_ids = RolePermission.objects.filter(permission=mirror_perm).values_list('role_id', flat=True)
        for role in Role.objects.filter(id__in=list(role_ids)):
            RolePermission.objects.get_or_create(role=role, permission=perm_objs[wfh_codename])

    leave_rule = ApprovalWorkflowRule.objects.filter(workflow_type='leave').first()
    if leave_rule:
        ApprovalWorkflowRule.objects.update_or_create(
            workflow_type='wfh',
            defaults={
                'l1_approver_role': leave_rule.l1_approver_role,
                'l2_approver_role': leave_rule.l2_approver_role,
            },
        )


def seed_reverse(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    ApprovalWorkflowRule = apps.get_model('accounts', 'ApprovalWorkflowRule')
    Permission.objects.filter(codename__in=list(MIRROR_OF.keys())).delete()
    ApprovalWorkflowRule.objects.filter(workflow_type='wfh').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0087_alter_approvalworkflowrule_workflow_type_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
