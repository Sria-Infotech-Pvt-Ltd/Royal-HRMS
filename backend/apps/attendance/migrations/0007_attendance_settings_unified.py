"""
Creates the unified attendance settings tables (one per organisation).

AttendanceSettings         — parent record, UUID PK, audit fields
AttendanceWorkingHours     — shift times, grace period, break deduction
AttendanceWeeklyOff        — boolean per day of week (True = weekly off)
AttendancePunchRules       — minimum hours full/half day, early-exit grace
AttendanceOvertimeRules    — OT threshold, regular + holiday multipliers
AttendanceLateMarkRules    — late marks per LOP, deduction unit
AttendanceAbsenceAlert     — consecutive absent days threshold + notify config
"""

import uuid
import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0006_absence_alert_policy'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [

        # ── Parent ────────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='AttendanceSettings',
            fields=[
                ('id', models.UUIDField(
                    primary_key=True,
                    default=uuid.uuid4,
                    editable=False,
                    serialize=False,
                )),
                ('is_active',  models.BooleanField(default=True)),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_attendance_settings',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('updated_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='updated_attendance_settings',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'attendance_settings'},
        ),

        # ── Working Hours ─────────────────────────────────────────────────────
        migrations.CreateModel(
            name='AttendanceWorkingHours',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('settings', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='working_hours',
                    to='attendance.attendancesettings',
                )),
                ('shift_start',            models.TimeField(default='09:00:00')),
                ('shift_end',              models.TimeField(default='18:00:00')),
                ('grace_period_minutes',   models.PositiveSmallIntegerField(default=15)),
                ('break_duration_minutes', models.PositiveSmallIntegerField(default=30)),
            ],
            options={'db_table': 'attendance_settings_working_hours'},
        ),

        # ── Weekly Off ────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='AttendanceWeeklyOff',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('settings', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='weekly_off',
                    to='attendance.attendancesettings',
                )),
                ('monday',    models.BooleanField(default=False)),
                ('tuesday',   models.BooleanField(default=False)),
                ('wednesday', models.BooleanField(default=False)),
                ('thursday',  models.BooleanField(default=False)),
                ('friday',    models.BooleanField(default=False)),
                ('saturday',  models.BooleanField(default=True)),
                ('sunday',    models.BooleanField(default=True)),
            ],
            options={'db_table': 'attendance_settings_weekly_off'},
        ),

        # ── Punch Rules ───────────────────────────────────────────────────────
        migrations.CreateModel(
            name='AttendancePunchRules',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('settings', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='punch_rules',
                    to='attendance.attendancesettings',
                )),
                ('min_hours_full_day', models.DecimalField(
                    max_digits=4, decimal_places=2, default=Decimal('8.00'),
                )),
                ('min_hours_half_day', models.DecimalField(
                    max_digits=4, decimal_places=2, default=Decimal('4.00'),
                )),
                ('early_exit_grace_minutes', models.PositiveSmallIntegerField(default=30)),
            ],
            options={'db_table': 'attendance_settings_punch_rules'},
        ),

        # ── Overtime Rules ────────────────────────────────────────────────────
        migrations.CreateModel(
            name='AttendanceOvertimeRules',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('settings', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='overtime_rules',
                    to='attendance.attendancesettings',
                )),
                ('ot_threshold_hours', models.DecimalField(
                    max_digits=4, decimal_places=2, default=Decimal('9.00'),
                )),
                ('ot_multiplier_regular', models.DecimalField(
                    max_digits=3, decimal_places=2, default=Decimal('1.50'),
                )),
                ('ot_multiplier_holiday', models.DecimalField(
                    max_digits=3, decimal_places=2, default=Decimal('2.00'),
                )),
            ],
            options={'db_table': 'attendance_settings_overtime_rules'},
        ),

        # ── Late Mark Rules ───────────────────────────────────────────────────
        migrations.CreateModel(
            name='AttendanceLateMarkRules',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('settings', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='late_mark_rules',
                    to='attendance.attendancesettings',
                )),
                ('late_marks_per_lop', models.PositiveSmallIntegerField(default=3)),
                ('lop_deduction_unit', models.CharField(
                    max_length=10,
                    choices=[('full_day', 'Full Day'), ('half_day', 'Half Day (0.5 day)')],
                    default='full_day',
                )),
            ],
            options={'db_table': 'attendance_settings_late_mark_rules'},
        ),

        # ── Absence Alert ─────────────────────────────────────────────────────
        migrations.CreateModel(
            name='AttendanceAbsenceAlert',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('settings', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='absence_alert',
                    to='attendance.attendancesettings',
                )),
                ('is_enabled',       models.BooleanField(default=True)),
                ('alert_after_days', models.PositiveSmallIntegerField(default=3)),
                ('notify_whom', models.CharField(
                    max_length=15,
                    choices=[
                        ('manager_and_hr', 'Manager + HR'),
                        ('hr_only',        'HR Only'),
                        ('manager_only',   'Manager Only'),
                    ],
                    default='manager_and_hr',
                )),
            ],
            options={'db_table': 'attendance_settings_absence_alert'},
        ),

        # ── Index on parent is_active ─────────────────────────────────────────
        migrations.AddIndex(
            model_name='attendancesettings',
            index=models.Index(fields=['is_active'], name='as_active_idx'),
        ),
    ]
