from django.db import migrations


def set_parental_leave_genders(apps, schema_editor):
    LeavePolicy = apps.get_model('hrms', 'LeavePolicy')
    LeavePolicy.objects.filter(leave_type='maternity').update(applicable_gender='female')
    LeavePolicy.objects.filter(leave_type='paternity').update(applicable_gender='male')
    LeavePolicy.objects.filter(
        leave_type='maternity',
        policy_note='Up to 180 days per Maternity Benefit Act. HR approval required.',
    ).update(policy_note='Set the entitlement in Leave Policy settings. HR approval required.')


class Migration(migrations.Migration):
    dependencies = [
        ('hrms', '0045_merge_20261013_1713'),
    ]

    operations = [
        migrations.RunPython(set_parental_leave_genders, migrations.RunPython.noop),
    ]
