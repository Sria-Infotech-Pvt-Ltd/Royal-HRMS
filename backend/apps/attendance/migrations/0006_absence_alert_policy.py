"""
Adds the attendance_absence_alert_policy table.

Stores the rule for triggering an HR/manager notification when an employee
is absent for N+ consecutive working days without an approved leave request.
Fields: is_enabled (toggle), absent_days_threshold (N days), notification_recipients.
"""

import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0005_late_mark_lop_policy'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AbsenceAlertPolicy',
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
                    help_text='Short unique code, e.g. AA-001. Auto-generated if omitted.',
                )),
                ('description', models.TextField(blank=True, default='')),
                ('is_enabled', models.BooleanField(
                    default=True,
                    help_text='When False, absence alerts are suppressed for this policy.',
                )),
                ('absent_days_threshold', models.PositiveSmallIntegerField(
                    default=3,
                    help_text=(
                        'Number of consecutive unexplained absent working days before '
                        'an alert is triggered. Must be at least 1.'
                    ),
                )),
                ('notification_recipients', models.CharField(
                    max_length=15,
                    choices=[
                        ('manager_and_hr', 'Manager + HR'),
                        ('hr_only',        'HR Only'),
                        ('manager_only',   'Manager Only'),
                    ],
                    default='manager_and_hr',
                    help_text='Who receives the absence alert notification.',
                )),
                ('is_default', models.BooleanField(
                    default=False,
                    help_text='At most one policy may be the default.',
                )),
                ('is_active',  models.BooleanField(default=True)),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_absence_alert_policies',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('updated_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='updated_absence_alert_policies',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'attendance_absence_alert_policy',
                'ordering': ['-is_default', 'name'],
            },
        ),
        migrations.AddIndex(
            model_name='absencealertpolicy',
            index=models.Index(fields=['is_active'],  name='aap_active_idx'),
        ),
        migrations.AddIndex(
            model_name='absencealertpolicy',
            index=models.Index(fields=['is_default'], name='aap_default_idx'),
        ),
    ]
