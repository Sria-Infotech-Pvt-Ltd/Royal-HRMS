# Step 2 of removing roles: drop the role tables and columns (the access was already moved by 0195).

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0195_move_role_access_to_org_chart"),
    ]

    operations = [
        migrations.RemoveField(model_name="approvalworkflowrule", name="l1_approver_role"),
        migrations.RemoveField(model_name="approvalworkflowrule", name="l2_approver_role"),
        migrations.RemoveField(model_name="position", name="default_role"),
        migrations.RemoveIndex(model_name="user", name="user_role_active_idx"),
        migrations.RemoveField(model_name="user", name="role"),
        migrations.DeleteModel(name="RolePermission"),
        migrations.DeleteModel(name="Role"),
    ]
