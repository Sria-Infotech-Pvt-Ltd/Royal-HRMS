"""
Extends AttendancePunch with geofencing and device audit fields.

New columns on attendance_punches:
  branch                — FK to branch_branches (resolved at punch time)
  device_time           — client-reported timestamp
  attendance_mode       — office / wfh / field / client_location / remote_office
  latitude              — employee GPS latitude
  longitude             — employee GPS longitude
  accuracy              — GPS accuracy (metres)
  calculated_distance   — Haversine distance to branch (metres)
  is_inside_geofence    — True/False/None
  ip_address            — request IP
  browser               — browser name
  operating_system      — OS name
  device_name           — human-readable device label
  device_id             — persistent device fingerprint

Removes: location (free-text string field from 0008 — replaced by structured geo fields).

New indexes for fraud detection and reporting queries.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0008_attendance_transactions'),
        ('branch',     '0004_branch_geofencing'),
    ]

    operations = [

        # ── New fields ────────────────────────────────────────────────────────

        migrations.AddField(
            model_name='attendancepunch',
            name='branch',
            field=django.db.models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='attendance_punches',
                to='branch.branch',
            ),
        ),
        migrations.AddField(
            model_name='attendancepunch',
            name='device_time',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='attendancepunch',
            name='attendance_mode',
            field=models.CharField(
                max_length=16,
                choices=[
                    ('office',          'Office'),
                    ('wfh',             'Work From Home'),
                    ('field',           'Field Work'),
                    ('client_location', 'Client Location'),
                    ('remote_office',   'Remote Office'),
                ],
                default='office',
            ),
        ),
        migrations.AddField(
            model_name='attendancepunch',
            name='latitude',
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='attendancepunch',
            name='longitude',
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='attendancepunch',
            name='accuracy',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True),
        ),
        migrations.AddField(
            model_name='attendancepunch',
            name='calculated_distance',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='attendancepunch',
            name='is_inside_geofence',
            field=models.BooleanField(null=True),
        ),
        migrations.AddField(
            model_name='attendancepunch',
            name='ip_address',
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='attendancepunch',
            name='browser',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='attendancepunch',
            name='operating_system',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='attendancepunch',
            name='device_name',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AddField(
            model_name='attendancepunch',
            name='device_id',
            field=models.CharField(blank=True, default='', max_length=255),
        ),

        # ── Remove old free-text location field ───────────────────────────────
        migrations.RemoveField(
            model_name='attendancepunch',
            name='location',
        ),

        # ── New indexes ───────────────────────────────────────────────────────
        migrations.AddIndex(
            model_name='attendancepunch',
            index=models.Index(
                fields=['employee', 'is_inside_geofence'],
                name='punch_emp_geofence_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='attendancepunch',
            index=models.Index(
                fields=['branch', 'punched_at'],
                name='punch_branch_time_idx',
            ),
        ),
    ]
