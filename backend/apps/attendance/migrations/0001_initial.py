"""
Initial migration for the attendance app.
Creates the attendance_working_hours_policy table.
"""

import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkingHoursPolicy',
            fields=[
                ('id', models.UUIDField(
                    primary_key=True,
                    default=uuid.uuid4,
                    editable=False,
                    serialize=False,
                )),
                ('name', models.CharField(max_length=100)),
                ('policy_code', models.CharField(
                    max_length=30,
                    unique=True,
                    help_text='Short unique code, e.g. WH-001. Auto-generated if omitted.',
                )),
                ('description', models.TextField(blank=True, default='')),
                ('start_time', models.TimeField(
                    help_text='Shift start time.',
                )),
                ('end_time', models.TimeField(
                    help_text='Shift end time. May cross midnight (e.g. 22:00 → 06:00).',
                )),
                ('break_duration', models.PositiveSmallIntegerField(
                    default=0,
                    help_text='Total break duration in minutes (e.g. 60 for a 1-hour lunch break).',
                )),
                ('grace_period', models.PositiveSmallIntegerField(
                    default=0,
                    help_text='Late-arrival grace period in minutes before a punch is marked late.',
                )),
                ('minimum_working_hours', models.DecimalField(
                    max_digits=4,
                    decimal_places=2,
                    default=0,
                    help_text='Minimum hours an employee must work to count as present.',
                )),
                ('maximum_working_hours', models.DecimalField(
                    max_digits=4,
                    decimal_places=2,
                    default=0,
                    help_text='Maximum hours clocked before overtime rules apply.',
                )),
                ('is_default', models.BooleanField(
                    default=False,
                    help_text='At most one policy may be the default. Enforced at save time.',
                )),
                ('is_active', models.BooleanField(default=True)),
                ('created_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_working_hour_policies',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('updated_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='updated_working_hour_policies',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'attendance_working_hours_policy',
                'ordering': ['-is_default', 'name'],
            },
        ),
        migrations.AddIndex(
            model_name='workinghourspolicy',
            index=models.Index(
                fields=['is_active'],
                name='whp_active_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='workinghourspolicy',
            index=models.Index(
                fields=['is_default'],
                name='whp_default_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='workinghourspolicy',
            index=models.Index(
                fields=['is_active', 'is_default'],
                name='whp_active_default_idx',
            ),
        ),
    ]
