"""
Migrate ApprovalWorkflowRule.l1_approver_role / l2_approver_role from a
3-value CharField enum to a ForeignKey to Role.

Also removes the `resignation` and `loan` workflows which have no backend.

Steps
─────
1. Add temporary FK columns (nullable).
2. Populate them: map 'reporting_manager' → first role with can_manage_team=True,
   'hr_manager' → first role with the leave.approve permission.
3. Remove the old CharField columns.
4. Rename temp FK columns to the original field names.
5. Delete any resignation / loan rules and overrides from the DB.
"""
from django.db import migrations, models
import django.db.models.deletion


# ── helpers used in RunPython steps ──────────────────────────────────────────

def _find_manager_role(Role):
    return Role.objects.filter(can_manage_team=True, is_active=True).order_by('id').first()


def _find_hr_role(Role, RolePermission, Permission):
    perm = Permission.objects.filter(codename='leave.approve').first()
    if not perm:
        return None
    rp = (
        RolePermission.objects
        .filter(permission=perm, role__is_active=True)
        .select_related('role')
        .first()
    )
    return rp.role if rp else None


def populate_role_fks(apps, schema_editor):
    ApprovalWorkflowRule = apps.get_model('accounts', 'ApprovalWorkflowRule')
    Role                 = apps.get_model('accounts', 'Role')
    RolePermission       = apps.get_model('accounts', 'RolePermission')
    Permission           = apps.get_model('accounts', 'Permission')

    manager_role = _find_manager_role(Role)
    hr_role      = _find_hr_role(Role, RolePermission, Permission)

    for rule in ApprovalWorkflowRule.objects.all():
        old_l1 = rule.l1_approver_role_old
        old_l2 = rule.l2_approver_role_old

        if old_l1 in ('reporting_manager', 'rm', 'manager'):
            rule.l1_role_fk = manager_role
        else:
            rule.l1_role_fk = None

        if old_l2 in ('hr_manager', 'hr', 'hr_admin'):
            rule.l2_role_fk = hr_role
        elif old_l2 == 'reporting_manager':
            rule.l2_role_fk = manager_role
        else:
            rule.l2_role_fk = None

        rule.save(update_fields=['l1_role_fk', 'l2_role_fk'])


def delete_obsolete_workflows(apps, schema_editor):
    ApprovalWorkflowRule    = apps.get_model('accounts', 'ApprovalWorkflowRule')
    EmployeeApprovalOverride = apps.get_model('accounts', 'EmployeeApprovalOverride')
    obsolete = ['resignation', 'loan']
    ApprovalWorkflowRule.objects.filter(workflow_type__in=obsolete).delete()
    EmployeeApprovalOverride.objects.filter(workflow_type__in=obsolete).delete()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0048_add_uan_aadhar_to_employee_profile'),
    ]

    operations = [
        # ── Step 1: add temp FK columns ───────────────────────────────────────
        migrations.AddField(
            model_name='approvalworkflowrule',
            name='l1_role_fk',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+',
                to='accounts.role',
            ),
        ),
        migrations.AddField(
            model_name='approvalworkflowrule',
            name='l2_role_fk',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+',
                to='accounts.role',
            ),
        ),

        # ── Step 2: rename old fields to _old so populate step can read them ─
        migrations.RenameField(
            model_name='approvalworkflowrule',
            old_name='l1_approver_role',
            new_name='l1_approver_role_old',
        ),
        migrations.RenameField(
            model_name='approvalworkflowrule',
            old_name='l2_approver_role',
            new_name='l2_approver_role_old',
        ),

        # ── Step 3: populate FK columns from the old string values ────────────
        migrations.RunPython(populate_role_fks, reverse_code=noop),

        # ── Step 4: drop old CharField columns ───────────────────────────────
        migrations.RemoveField(
            model_name='approvalworkflowrule',
            name='l1_approver_role_old',
        ),
        migrations.RemoveField(
            model_name='approvalworkflowrule',
            name='l2_approver_role_old',
        ),

        # ── Step 5: rename temp FK columns to final names ─────────────────────
        migrations.RenameField(
            model_name='approvalworkflowrule',
            old_name='l1_role_fk',
            new_name='l1_approver_role',
        ),
        migrations.RenameField(
            model_name='approvalworkflowrule',
            old_name='l2_role_fk',
            new_name='l2_approver_role',
        ),

        # ── Step 6: update related_name on the FK to match the model ─────────
        migrations.AlterField(
            model_name='approvalworkflowrule',
            name='l1_approver_role',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='rules_as_l1',
                to='accounts.role',
            ),
        ),
        migrations.AlterField(
            model_name='approvalworkflowrule',
            name='l2_approver_role',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='rules_as_l2',
                to='accounts.role',
            ),
        ),

        # ── Step 7: remove resignation / loan workflow choices from model ─────
        migrations.AlterField(
            model_name='approvalworkflowrule',
            name='workflow_type',
            field=models.CharField(
                choices=[
                    ('leave', 'Leave Request'),
                    ('expense', 'Expense Claim'),
                    ('attendance_correction', 'Attendance Correction'),
                ],
                max_length=25,
                unique=True,
            ),
        ),
        migrations.AlterField(
            model_name='employeeapprovaloverride',
            name='workflow_type',
            field=models.CharField(
                choices=[
                    ('leave', 'Leave Request'),
                    ('expense', 'Expense Claim'),
                    ('attendance_correction', 'Attendance Correction'),
                ],
                max_length=25,
            ),
        ),

        # ── Step 8: delete resignation / loan rules and overrides ─────────────
        migrations.RunPython(delete_obsolete_workflows, reverse_code=noop),
    ]
