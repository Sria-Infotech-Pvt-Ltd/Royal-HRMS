"""
Attendance Transactions tables.

AttendancePunch      — immutable raw punch events (IN / OUT)
AttendanceRecord     — processed daily result, one row per (employee, date)
AttendanceCorrection — employee-submitted regularization requests
"""

import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0007_attendance_settings_unified'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [

        # ── AttendancePunch ───────────────────────────────────────────────────
        migrations.CreateModel(
            name='AttendancePunch',
            fields=[
                ('id', models.UUIDField(
                    primary_key=True, default=uuid.uuid4,
                    editable=False, serialize=False,
                )),
                ('employee', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='attendance_punches',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('punch_type', models.CharField(
                    max_length=3,
                    choices=[('IN', 'Punch In'), ('OUT', 'Punch Out')],
                )),
                ('punched_at', models.DateTimeField()),
                ('source', models.CharField(
                    max_length=10,
                    choices=[
                        ('web',       'Web'),
                        ('mobile',    'Mobile'),
                        ('biometric', 'Biometric'),
                        ('manual',    'Manual'),
                        ('system',    'System'),
                    ],
                    default='web',
                )),
                ('location',       models.CharField(max_length=200, blank=True, default='')),
                ('is_regularized', models.BooleanField(default=False)),
                ('created_at',     models.DateTimeField(auto_now_add=True)),
            ],
            options={'db_table': 'attendance_punches', 'ordering': ['punched_at']},
        ),

        migrations.AddIndex(
            model_name='attendancepunch',
            index=models.Index(fields=['employee', 'punched_at'], name='punch_emp_time_idx'),
        ),
        migrations.AddIndex(
            model_name='attendancepunch',
            index=models.Index(fields=['employee', 'punch_type'], name='punch_emp_type_idx'),
        ),

        # ── AttendanceRecord ──────────────────────────────────────────────────
        migrations.CreateModel(
            name='AttendanceRecord',
            fields=[
                ('id', models.UUIDField(
                    primary_key=True, default=uuid.uuid4,
                    editable=False, serialize=False,
                )),
                ('employee', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='attendance_records',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('date', models.DateField()),
                ('status', models.CharField(
                    max_length=12,
                    choices=[
                        ('present',    'Present'),
                        ('late',       'Late'),
                        ('absent',     'Absent'),
                        ('half_day',   'Half Day'),
                        ('weekly_off', 'Weekly Off'),
                        ('holiday',    'Holiday'),
                        ('on_leave',   'On Leave'),
                    ],
                )),
                ('first_punch_in',        models.TimeField(null=True, blank=True)),
                ('last_punch_out',        models.TimeField(null=True, blank=True)),
                ('total_working_minutes', models.PositiveIntegerField(default=0)),
                ('overtime_minutes',      models.PositiveIntegerField(default=0)),
                ('is_late',               models.BooleanField(default=False)),
                ('is_early_exit',         models.BooleanField(default=False)),
                ('note',                  models.CharField(max_length=200, blank=True, default='')),
                ('created_at',            models.DateTimeField(auto_now_add=True)),
                ('updated_at',            models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'attendance_records'},
        ),

        migrations.AlterUniqueTogether(
            name='attendancerecord',
            unique_together={('employee', 'date')},
        ),
        migrations.AddIndex(
            model_name='attendancerecord',
            index=models.Index(fields=['employee', 'date'],   name='rec_emp_date_idx'),
        ),
        migrations.AddIndex(
            model_name='attendancerecord',
            index=models.Index(fields=['employee', 'status'], name='rec_emp_status_idx'),
        ),
        migrations.AddIndex(
            model_name='attendancerecord',
            index=models.Index(fields=['date'],               name='rec_date_idx'),
        ),

        # ── AttendanceCorrection ──────────────────────────────────────────────
        migrations.CreateModel(
            name='AttendanceCorrection',
            fields=[
                ('id', models.UUIDField(
                    primary_key=True, default=uuid.uuid4,
                    editable=False, serialize=False,
                )),
                ('employee', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='attendance_corrections',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('date', models.DateField()),
                ('punch_type', models.CharField(
                    max_length=4,
                    choices=[
                        ('IN',   'Clock In (IN)'),
                        ('OUT',  'Clock Out (OUT)'),
                        ('BOTH', 'Both IN & OUT'),
                    ],
                )),
                ('requested_in_time',  models.TimeField(null=True, blank=True)),
                ('requested_out_time', models.TimeField(null=True, blank=True)),
                ('reason', models.CharField(
                    max_length=20,
                    choices=[
                        ('biometric_error', 'Device malfunction / biometric error'),
                        ('forgot_to_punch', 'Forgot to punch'),
                        ('field_work',      'Work from field (client visit)'),
                        ('system_downtime', 'System / server downtime'),
                        ('other',           'Other'),
                    ],
                )),
                ('notes', models.TextField(blank=True, default='')),
                ('status', models.CharField(
                    max_length=10,
                    choices=[
                        ('pending',  'Pending'),
                        ('approved', 'Approved'),
                        ('rejected', 'Rejected'),
                    ],
                    default='pending',
                )),
                ('reviewed_by', models.ForeignKey(
                    null=True, blank=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='reviewed_corrections',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('reviewed_at', models.DateTimeField(null=True, blank=True)),
                ('created_by', models.ForeignKey(
                    null=True, blank=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_corrections',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'attendance_corrections'},
        ),

        migrations.AddIndex(
            model_name='attendancecorrection',
            index=models.Index(fields=['employee', 'date'],   name='corr_emp_date_idx'),
        ),
        migrations.AddIndex(
            model_name='attendancecorrection',
            index=models.Index(fields=['employee', 'status'], name='corr_emp_status_idx'),
        ),
    ]
