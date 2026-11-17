from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0051_overtime_starts_at_shift_end'),
    ]

    operations = [
        migrations.AddField(
            model_name='attendancepunchrules',
            name='short_hours_as_half_day',
            field=models.BooleanField(default=False, help_text='On: every finished day below the full-day minimum is a Half Day (the older rule), not just days at or below the half-day limit.'),
        ),
        migrations.AddField(
            model_name='attendancerecord',
            name='short_minutes',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='attendancepunchrules',
            name='min_hours_half_day',
            field=models.DecimalField(decimal_places=2, default=Decimal('4.00'), help_text='Half-day limit: a finished day of this many hours or fewer is a Half Day. Above it but below the full-day minimum the day stays Present with "hours not completed" (unless short_hours_as_half_day is on).', max_digits=4),
        ),
    ]
