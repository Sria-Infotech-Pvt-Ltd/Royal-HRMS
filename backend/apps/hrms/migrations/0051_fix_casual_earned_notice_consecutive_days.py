from django.db import migrations


def fix_notice_and_consecutive_day_rules(apps, schema_editor):
    """UAT-028 — Casual Leave's own policy_note has always promised 'Max 3
    consecutive days. Apply 1 day in advance.' but maximum_consecutive_days/
    minimum_notice_period were left at the model default (0 = unlimited/no
    notice), so the server accepted requests the written policy says it
    shouldn't. Same gap for Earned Leave's 'Min 3 days notice' note. Only
    touches rows still at the un-configured default (0) so an admin who
    already set a deliberate value here is never overwritten."""
    LeavePolicy = apps.get_model('hrms', 'LeavePolicy')
    LeavePolicy.objects.filter(leave_type='casual', maximum_consecutive_days=0).update(maximum_consecutive_days=3)
    LeavePolicy.objects.filter(leave_type='casual', minimum_notice_period=0).update(minimum_notice_period=1)
    LeavePolicy.objects.filter(leave_type='earned', minimum_notice_period=0).update(minimum_notice_period=3)


class Migration(migrations.Migration):
    dependencies = [
        ('hrms', '0050_merge_20261028_1458'),
    ]

    operations = [
        migrations.RunPython(fix_notice_and_consecutive_day_rules, migrations.RunPython.noop),
    ]
