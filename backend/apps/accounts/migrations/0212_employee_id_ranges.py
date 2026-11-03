from django.db import migrations, models

DEFAULT_RANGES = {
    'Permanent':  (10000000, 19999999),
    'Contract':   (20000000, 29999999),
    'Consultant': (30000000, 39999999),
    'Freelancer': (40000000, 49999999),
    'Intern':     (50000000, 59999999),
    'Part-Time':  (60000000, 69999999),
    'Temporary':  (70000000, 79999999),
}


def seed_ranges(apps, schema_editor):
    EmployeeCodeSeries = apps.get_model('accounts', 'EmployeeCodeSeries')
    for employment_type, (start, end) in DEFAULT_RANGES.items():
        series, created = EmployeeCodeSeries.objects.get_or_create(
            employment_type=employment_type,
            defaults={'range_start': start, 'range_end': end, 'next_sequence': start + 1},
        )
        if not created:
            series.range_start = start
            series.range_end = end
            series.next_sequence = start + 1
            series.save(update_fields=['range_start', 'range_end', 'next_sequence'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0211_backfill_account_activated_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='legacy_employee_code',
            field=models.CharField(blank=True, db_index=True, default='', max_length=20),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='employeecodeseries',
            name='range_start',
            field=models.PositiveBigIntegerField(default=10000000, help_text='Exclusive lower bound — never issued itself; the first ID handed out is range_start + 1.'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='employeecodeseries',
            name='range_end',
            field=models.PositiveBigIntegerField(default=19999999, help_text='Inclusive upper bound — the last ID this series can ever issue.'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='employeecodeseries',
            name='next_sequence',
            field=models.PositiveBigIntegerField(help_text='Next number this series will hand out.'),
        ),
        migrations.RemoveField(
            model_name='employeecodeseries',
            name='prefix',
        ),
        migrations.RemoveField(
            model_name='employeecodeseries',
            name='padding',
        ),
        migrations.RunPython(seed_ranges, noop_reverse),
    ]
