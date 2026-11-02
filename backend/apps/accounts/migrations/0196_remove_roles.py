# Step 2 of removing roles: drop the role tables and columns (the access was already moved by 0195).

from django.db import migrations


def remove_legacy_role_schema_if_present(apps, schema_editor):
    connection = schema_editor.connection
    tables = set(connection.introspection.table_names())

    def remove_field_if_present(model_name, field_name):
        model = apps.get_model('accounts', model_name)
        table_name = model._meta.db_table
        if table_name not in tables:
            return

        field = model._meta.get_field(field_name)
        with connection.cursor() as cursor:
            columns = {
                column.name
                for column in connection.introspection.get_table_description(cursor, table_name)
            }
        if field.column in columns:
            schema_editor.remove_field(model, field)


    user_model = apps.get_model('accounts', 'User')
    user_table = user_model._meta.db_table
    if user_table in tables:
        with connection.cursor() as cursor:
            indexes = connection.introspection.get_constraints(cursor, user_table)
        role_index = next(
            (index for index in user_model._meta.indexes if index.name == 'user_role_active_idx'),
            None,
        )
        if role_index and 'user_role_active_idx' in indexes:
            schema_editor.remove_index(user_model, role_index)

    remove_field_if_present('ApprovalWorkflowRule', 'l1_approver_role')
    remove_field_if_present('ApprovalWorkflowRule', 'l2_approver_role')
    remove_field_if_present('Position', 'default_role')
    remove_field_if_present('User', 'role')

    for model_name in ('RolePermission', 'Role'):
        model = apps.get_model('accounts', model_name)
        if model._meta.db_table in tables:
            schema_editor.delete_model(model)
            tables.remove(model._meta.db_table)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0195_move_role_access_to_org_chart"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    remove_legacy_role_schema_if_present,
                    migrations.RunPython.noop,
                ),
            ],
            state_operations=[
                migrations.RemoveField(model_name="approvalworkflowrule", name="l1_approver_role"),
                migrations.RemoveField(model_name="approvalworkflowrule", name="l2_approver_role"),
                migrations.RemoveField(model_name="position", name="default_role"),
                migrations.RemoveIndex(model_name="user", name="user_role_active_idx"),
                migrations.RemoveField(model_name="user", name="role"),
                migrations.DeleteModel(name="RolePermission"),
                migrations.DeleteModel(name="Role"),
            ],
        ),
    ]
