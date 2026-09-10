# Part of the "Branch" -> "Company Code" wording change (label/display-name
# only — the role's name/codename, can_manage_branch flag, and every
# permission it holds are untouched; see the accompanying PR for the wider
# rename). Matched by can_manage_branch=True (this codebase's own convention
# for finding this role regardless of name drift — see migration 0076's
# note), not by `name='branch_admin'`, and scoped to the exact known seeded
# display_name so a company that already renamed this role themselves isn't
# silently overwritten.
from django.db import migrations

OLD_DISPLAY_NAME = 'Branch Admin'
NEW_DISPLAY_NAME = 'Company Code Admin'


def rename_forward(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Role.objects.using(schema_editor.connection.alias).filter(
        can_manage_branch=True, display_name=OLD_DISPLAY_NAME,
    ).update(display_name=NEW_DISPLAY_NAME)


def rename_backward(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Role.objects.using(schema_editor.connection.alias).filter(
        can_manage_branch=True, display_name=NEW_DISPLAY_NAME,
    ).update(display_name=OLD_DISPLAY_NAME)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0134_position_default_role"),
    ]

    operations = [
        migrations.RunPython(rename_forward, rename_backward),
    ]
