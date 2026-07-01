"""
Adds the attendance_punch_rules_policy table.

Stores punch-mode configuration per organization:
  single   → one punch-in; system auto-punches out
  multiple → multiple in/out pairs, capped by max_punch_count

Also stores auto-checkout time, early-checkout grace, and missing-punch handling.
"""

import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


_DAY_TYPE_CHOICES = [
    ('single',   'Single Punch'),
    ('multiple', 'Multiple Punch'),
]

_MISSING_PUNCH_CHOICES = [
    ('mark_absent',             'Mark as Absent'),
    ('mark_half_day',           'Mark as Half Day'),
    ('require_regularization',  'Require Regularization'),
    ('auto_regularize',         'Auto Regularize'),
]


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0002_weekly_day_policy'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PunchRulesPolicy',
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
                    help_text='Short unique code, e.g. PR-001. Auto-generated if omitted.',
                )),
                ('description', models.TextField(blank=True, default='')),
                ('punch_mode', models.CharField(
                    max_length=10,
                    choices=_DAY_TYPE_CHOICES,
                    default='multiple',
                    help_text='Single: one punch-in + auto-checkout. '
                              'Multiple: unlimited in/out pairs up to max_punch_count.',
                )),
                ('max_punch_count', models.PositiveSmallIntegerField(
                    default=2,
                    help_text='Maximum punch events per day. Forced to 1 in single mode.',
                )),
                ('auto_checkout_enabled', models.BooleanField(
                    default=False,
                    help_text='System auto-punches out at auto_checkout_time if not already punched out.',
                )),
                ('auto_checkout_time', models.TimeField(
                    null=True, blank=True,
                    help_text='Required when auto_checkout_enabled is True.',
                )),
                ('early_checkout_grace', models.PositiveSmallIntegerField(
                    default=0,
                    help_text='Minutes before shift end that an employee can punch out without penalty.',
                )),
                ('missing_punch_action', models.CharField(
                    max_length=25,
                    choices=_MISSING_PUNCH_CHOICES,
                    default='require_regularization',
                    help_text='Action when an employee has an IN punch but no OUT punch (or vice versa).',
                )),
                ('is_default', models.BooleanField(default=False)),
                ('is_active',  models.BooleanField(default=True)),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_punch_rules_policies',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('updated_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='updated_punch_rules_policies',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'attendance_punch_rules_policy',
                'ordering': ['-is_default', 'name'],
            },
        ),
        migrations.AddIndex(
            model_name='punchrulespolicy',
            index=models.Index(fields=['is_active'],  name='prp_active_idx'),
        ),
        migrations.AddIndex(
            model_name='punchrulespolicy',
            index=models.Index(fields=['is_default'], name='prp_default_idx'),
        ),
    ]
