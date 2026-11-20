"""Default punch rule: one punch in and one punch out a day.

The daily cap (PunchRulesPolicy.max_punch_count) only applies when a default, active policy exists. Environments that never
created one had no cap at all, so people could punch in again after punching out. This adds the "one in, one out a day"
policy (Multiple punch, cap 2: In and Out each count as one) only where NO default policy exists, so a policy an admin
chose is never replaced. Admins can still edit or replace it in Attendance Settings.
"""
from django.db import migrations

POLICY_CODE = 'PR-ONE-PER-DAY'


def add_default_policy(apps, schema_editor):
    PunchRulesPolicy = apps.get_model('attendance', 'PunchRulesPolicy')
    if PunchRulesPolicy.objects.filter(is_default=True, is_active=True).exists():
        return
    PunchRulesPolicy.objects.get_or_create(
        policy_code=POLICY_CODE,
        defaults={
            'name': 'One punch in and one punch out a day',
            'description': 'Each person punches in once and punches out once a day.',
            'punch_mode': 'multiple',
            'max_punch_count': 2,
            'is_default': True,
            'is_active': True,
        },
    )


def remove_default_policy(apps, schema_editor):
    apps.get_model('attendance', 'PunchRulesPolicy').objects.filter(policy_code=POLICY_CODE).delete()


class Migration(migrations.Migration):
    dependencies = [('attendance', '0053_wfh_backdating_limit')]
    operations = [migrations.RunPython(add_default_policy, remove_default_policy)]
