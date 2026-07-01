"""
Adds geofencing fields to the Branch model:
  latitude, longitude, allowed_radius_meters, geofencing_enabled

Existing branches get geofencing_enabled=False so nothing breaks.
Set latitude + longitude + flip geofencing_enabled=True in Admin
(or via the Settings UI) to activate geofence validation per branch.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('branch', '0003_branch_permissions'),
    ]

    operations = [
        migrations.AddField(
            model_name='branch',
            name='latitude',
            field=models.DecimalField(
                blank=True, decimal_places=7, max_digits=10, null=True,
                help_text='Office GPS latitude. Required when geofencing_enabled is True.',
            ),
        ),
        migrations.AddField(
            model_name='branch',
            name='longitude',
            field=models.DecimalField(
                blank=True, decimal_places=7, max_digits=10, null=True,
                help_text='Office GPS longitude. Required when geofencing_enabled is True.',
            ),
        ),
        migrations.AddField(
            model_name='branch',
            name='allowed_radius_meters',
            field=models.PositiveIntegerField(
                default=150,
                help_text='Geofence radius in metres. Punches outside this radius are rejected.',
            ),
        ),
        migrations.AddField(
            model_name='branch',
            name='geofencing_enabled',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'When True, employees must be within allowed_radius_meters of the branch '
                    'coordinates to record an office punch.'
                ),
            ),
        ),
        migrations.AddIndex(
            model_name='branch',
            index=models.Index(fields=['branch_name'], name='branch_name_idx'),
        ),
        migrations.AddIndex(
            model_name='branch',
            index=models.Index(fields=['status'], name='branch_status_idx'),
        ),
    ]
