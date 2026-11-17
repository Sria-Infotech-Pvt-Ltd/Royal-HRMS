"""Maternity and paternity are granted per case when an eligible employee applies, not credited to everyone every year.

Switches the existing maternity and paternity policies to grant_mode='on_request' (the policy rows are left as they are otherwise: days,
gender, service period). Yearly balances already credited to employees stay in the table untouched; they are simply not listed as a
yearly balance unless the employee has used or requested that leave (see services_leave_event.hide_unused_event_balances).
Reversible: the reverse puts the two policies back to 'annual'.
"""
from django.db import migrations

ON_REQUEST_TYPES = ('maternity', 'paternity')


def switch_to_on_request(apps, schema_editor):
    LeavePolicy = apps.get_model('hrms', 'LeavePolicy')
    LeavePolicy.objects.filter(leave_type__in=ON_REQUEST_TYPES).update(grant_mode='on_request')


def switch_back_to_annual(apps, schema_editor):
    LeavePolicy = apps.get_model('hrms', 'LeavePolicy')
    LeavePolicy.objects.filter(leave_type__in=ON_REQUEST_TYPES).update(grant_mode='annual')


class Migration(migrations.Migration):

    dependencies = [
        ('hrms', '0055_leave_policy_grant_mode'),
    ]

    operations = [
        migrations.RunPython(switch_to_on_request, switch_back_to_annual),
    ]
