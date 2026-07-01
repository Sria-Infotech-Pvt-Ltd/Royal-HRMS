"""
Adds the attendance_late_mark_lop_policy table.

Stores the rule for converting accumulated late marks into LOP deductions:
- late_marks_per_lop: how many late marks per calendar month trigger one LOP (0 = tracking only)
- lop_deduction_unit: whether each LOP counts as a full day or a half day
"""

import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0004_overtime_policy'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='LateMarkLOPPolicy',
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
                    help_text='Short unique code, e.g. LM-001. Auto-generated if omitted.',
                )),
                ('description', models.TextField(blank=True, default='')),
                ('late_marks_per_lop', models.PositiveSmallIntegerField(
                    default=3,
                    help_text=(
                        'Number of late marks within a calendar month that trigger one LOP deduction. '
                        '0 = tracking only (late marks recorded but no LOP is applied).'
                    ),
                )),
                ('lop_deduction_unit', models.CharField(
                    max_length=10,
                    choices=[
                        ('full_day', 'Full Day'),
                        ('half_day', 'Half Day'),
                    ],
                    default='full_day',
                    help_text='Whether each LOP deduction counts as a full day or a half day.',
                )),
                ('is_default', models.BooleanField(
                    default=False,
                    help_text='At most one policy may be the default.',
                )),
                ('is_active',  models.BooleanField(default=True)),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_late_mark_lop_policies',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('updated_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='updated_late_mark_lop_policies',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'attendance_late_mark_lop_policy',
                'ordering': ['-is_default', 'name'],
            },
        ),
        migrations.AddIndex(
            model_name='latemarkloppolicy',
            index=models.Index(fields=['is_active'],  name='lml_active_idx'),
        ),
        migrations.AddIndex(
            model_name='latemarkloppolicy',
            index=models.Index(fields=['is_default'], name='lml_default_idx'),
        ),
    ]
