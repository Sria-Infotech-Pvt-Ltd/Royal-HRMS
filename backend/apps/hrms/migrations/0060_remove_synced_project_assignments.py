from django.db import migrations


def remove_synced_assignments(apps, schema_editor):
    """Project assignments now live in AIRA HRMS only. Every row so far was synced from Project Budgeting, so they are
    all removed (their change events go with them). Timesheet lines keep their own copy of the project name."""
    apps.get_model('hrms', 'ProjectAssignmentEvent').objects.all().delete()
    apps.get_model('hrms', 'ProjectAssignment').objects.all().delete()
    apps.get_model('hrms', 'ProjectSyncLog').objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('hrms', '0059_sync_policy_note_numbers'),
    ]

    operations = [
        migrations.RunPython(remove_synced_assignments, migrations.RunPython.noop),
    ]
