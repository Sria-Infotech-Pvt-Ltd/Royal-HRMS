import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0012_hr_attendance_models'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Add missing_punch_grace_minutes to attendance_settings_working_hours
        migrations.AddField(
            model_name='attendanceworkinghours',
            name='missing_punch_grace_minutes',
            field=models.PositiveSmallIntegerField(
                default=10,
                help_text='Minutes after shift end before a missing clock-out triggers an un-punch alert.',
            ),
        ),

        # 2. Update AttendanceRecord.status choices (app-level only, no DB change needed)
        migrations.AlterField(
            model_name='attendancerecord',
            name='status',
            field=models.CharField(
                max_length=12,
                choices=[
                    ('present',    'Present'),
                    ('late',       'Late'),
                    ('absent',     'Absent'),
                    ('half_day',   'Half Day'),
                    ('weekly_off', 'Weekly Off'),
                    ('holiday',    'Holiday'),
                    ('on_leave',   'On Leave'),
                    ('incomplete', 'Incomplete'),
                ],
            ),
        ),

        # 3. Add composite index (date, status) on attendance_records
        migrations.AddIndex(
            model_name='attendancerecord',
            index=models.Index(fields=['date', 'status'], name='rec_date_status_idx'),
        ),

        # 4. Create MissingPunchNotification table
        migrations.CreateModel(
            name='MissingPunchNotification',
            fields=[
                ('id',         models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('date',       models.DateField(help_text='The working date for which the notification was sent.')),
                ('channel',    models.CharField(default='email', max_length=20, help_text='Delivery channel: email, in_app, push, sms.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('employee',   models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='missing_punch_notifications',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'attendance_missing_punch_notifications',
            },
        ),
        migrations.AlterUniqueTogether(
            name='missingpunchnotification',
            unique_together={('employee', 'date', 'channel')},
        ),
        migrations.AddIndex(
            model_name='missingpunchnotification',
            index=models.Index(fields=['employee', 'date'], name='mpn_emp_date_idx'),
        ),
        migrations.AddIndex(
            model_name='missingpunchnotification',
            index=models.Index(fields=['date'], name='mpn_date_idx'),
        ),
    ]
