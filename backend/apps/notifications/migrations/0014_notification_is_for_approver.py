from django.db import migrations, models

# Notices that were sent to an approver before the column existed: found by their title, which is how they were written.
APPROVER_TITLES = (
    'New Leave Request', 'Leave Awaiting Approval', 'Regularization Request Pending', 'New Expense Pending Approval',
    'Separation Request Pending Your Approval', 'Face ID registration awaiting review',
)


def mark_existing(apps, schema_editor):
    apps.get_model('notifications', 'Notification').objects.filter(title__in=APPROVER_TITLES).update(is_for_approver=True)


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0013_hr_help_notification_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='is_for_approver',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(mark_existing, migrations.RunPython.noop),
    ]
