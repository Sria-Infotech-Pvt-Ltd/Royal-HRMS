"""
Adds the attendance_overtime_policy table.

Stores overtime thresholds (in minutes), rounding rules, approval type,
and separate multipliers for holiday and weekly-off overtime.
"""

import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0003_punch_rules_policy'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='OvertimePolicy',
            fields=[
                ('id', models.UUIDField(
                    primary_key=True,
                    default=uuid.uuid4,
                    editable=False,
                    serialize=False,
                )),
                ('name',        models.CharField(max_length=100)),
                ('policy_code', models.CharField(
                    max_length=30,
                    unique=True,
                    help_text='Short unique code, e.g. OT-001. Auto-generated if omitted.',
                )),
                ('description', models.TextField(blank=True, default='')),
                ('minimum_overtime_minutes', models.PositiveSmallIntegerField(
                    default=30,
                    help_text='Minutes beyond shift end before overtime counting begins.',
                )),
                ('maximum_overtime_minutes_per_day', models.PositiveSmallIntegerField(
                    default=0,
                    help_text='Daily overtime cap in minutes. 0 = no cap.',
                )),
                ('maximum_overtime_minutes_per_month', models.PositiveIntegerField(
                    default=0,
                    help_text='Monthly overtime cap in minutes. 0 = no cap.',
                )),
                ('round_off_rule', models.CharField(
                    max_length=10,
                    choices=[
                        ('none',   'No Rounding'),
                        ('15_min', 'Round to nearest 15 minutes'),
                        ('30_min', 'Round to nearest 30 minutes'),
                        ('60_min', 'Round to nearest 60 minutes'),
                    ],
                    default='none',
                )),
                ('approval_type', models.CharField(
                    max_length=10,
                    choices=[
                        ('none',   'Not Required'),
                        ('auto',   'Auto Approve'),
                        ('manual', 'Requires Approval'),
                    ],
                    default='manual',
                )),
                ('count_holiday_overtime', models.BooleanField(
                    default=True,
                    help_text='Track and compensate overtime worked on declared holidays.',
                )),
                ('holiday_overtime_multiplier', models.DecimalField(
                    max_digits=3,
                    decimal_places=1,
                    default='2.0',
                    help_text='Pay multiplier for holiday overtime. Min 1.0.',
                )),
                ('count_weekly_off_overtime', models.BooleanField(
                    default=True,
                    help_text='Track and compensate overtime worked on weekly off days.',
                )),
                ('weekly_off_overtime_multiplier', models.DecimalField(
                    max_digits=3,
                    decimal_places=1,
                    default='2.0',
                    help_text='Pay multiplier for weekly-off overtime. Min 1.0.',
                )),
                ('is_default', models.BooleanField(default=False)),
                ('is_active',  models.BooleanField(default=True)),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_overtime_policies',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('updated_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='updated_overtime_policies',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'attendance_overtime_policy',
                'ordering': ['-is_default', 'name'],
            },
        ),
        migrations.AddIndex(
            model_name='overtimepolicy',
            index=models.Index(fields=['is_active'],  name='otp_active_idx'),
        ),
        migrations.AddIndex(
            model_name='overtimepolicy',
            index=models.Index(fields=['is_default'], name='otp_default_idx'),
        ),
    ]
