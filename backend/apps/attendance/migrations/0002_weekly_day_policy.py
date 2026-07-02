"""
Adds the attendance_weekly_day_policy table.

Each row represents a named weekly schedule (e.g. 'Standard 5-Day Week').
Each day of the week is stored as a CharField with choices:
  working | off | half_day
"""

import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='WeeklyDayPolicy',
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
                    help_text='Short unique code, e.g. WD-001. Auto-generated if omitted.',
                )),
                ('description', models.TextField(blank=True, default='')),
                # Day schedule fields
                ('monday',    models.CharField(max_length=10, choices=[('working', 'Working Day'), ('off', 'Weekly Off'), ('half_day', 'Half Day')], default='working')),
                ('tuesday',   models.CharField(max_length=10, choices=[('working', 'Working Day'), ('off', 'Weekly Off'), ('half_day', 'Half Day')], default='working')),
                ('wednesday', models.CharField(max_length=10, choices=[('working', 'Working Day'), ('off', 'Weekly Off'), ('half_day', 'Half Day')], default='working')),
                ('thursday',  models.CharField(max_length=10, choices=[('working', 'Working Day'), ('off', 'Weekly Off'), ('half_day', 'Half Day')], default='working')),
                ('friday',    models.CharField(max_length=10, choices=[('working', 'Working Day'), ('off', 'Weekly Off'), ('half_day', 'Half Day')], default='working')),
                ('saturday',  models.CharField(max_length=10, choices=[('working', 'Working Day'), ('off', 'Weekly Off'), ('half_day', 'Half Day')], default='off')),
                ('sunday',    models.CharField(max_length=10, choices=[('working', 'Working Day'), ('off', 'Weekly Off'), ('half_day', 'Half Day')], default='off')),
                ('is_default', models.BooleanField(
                    default=False,
                    help_text='At most one policy may be the default.',
                )),
                ('is_active', models.BooleanField(default=True)),
                ('created_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_weekly_day_policies',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('updated_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='updated_weekly_day_policies',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'attendance_weekly_day_policy',
                'ordering': ['-is_default', 'name'],
            },
        ),
        migrations.AddIndex(
            model_name='weeklydaypolicy',
            index=models.Index(fields=['is_active'],  name='wdp_active_idx'),
        ),
        migrations.AddIndex(
            model_name='weeklydaypolicy',
            index=models.Index(fields=['is_default'], name='wdp_default_idx'),
        ),
    ]
