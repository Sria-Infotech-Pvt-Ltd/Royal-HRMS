from django.db import migrations

from apps.hrms.services_leave_policy_note import sync_note_numbers


def sync_existing_notes(apps, schema_editor):
    """Notes written before the numbers followed the settings (e.g. "Max 3 consecutive days" while the setting is 5): bring the recognised
    phrases in line with the settings. Only the number (and day / days) inside those phrases changes."""
    LeavePolicy = apps.get_model('hrms', 'LeavePolicy')
    for policy in LeavePolicy.objects.exclude(policy_note=''):
        updated = sync_note_numbers(
            policy.policy_note,
            maximum_consecutive_days=policy.maximum_consecutive_days or 0,
            minimum_notice_period=policy.minimum_notice_period or 0,
            can_carry_forward=bool(policy.can_carry_forward),
            max_carry_forward_days=policy.max_carry_forward_days or 0,
        )
        if updated != policy.policy_note:
            LeavePolicy.objects.filter(pk=policy.pk).update(policy_note=updated)


class Migration(migrations.Migration):
    dependencies = [
        ('hrms', '0058_wfh_location_policy'),
    ]

    operations = [
        migrations.RunPython(sync_existing_notes, migrations.RunPython.noop),
    ]
