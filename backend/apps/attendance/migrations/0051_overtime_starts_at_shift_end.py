"""Overtime should start at shift end, not half an hour later.

The old default overtime threshold was 9.00 worked hours while the default shift is 9:00-18:00 (9 hours) with a 30-minute break
deducted from every day, so overtime only began 30 minutes after the shift ended (a person leaving at 18:30 had 0 overtime). For
settings still sitting on that clash, the threshold equals the shift length and a break is deducted, this lowers it to shift length
minus the break (8.5 hours for 9:00-18:00 with a 30-minute break), so overtime starts exactly at shift end.

A threshold the company already changed (anything that is not exactly the shift length) is left alone, as are overnight shifts and
settings with no break. Past attendance records are not recalculated. Reversible: the reverse restores the shift length.
"""
import datetime
from decimal import Decimal

from django.db import migrations


def _span_hours(start: datetime.time, end: datetime.time) -> Decimal | None:
    start_minutes = start.hour * 60 + start.minute
    end_minutes = end.hour * 60 + end.minute
    if end_minutes <= start_minutes:   # overnight or zero-length shift: not touched
        return None
    return Decimal(end_minutes - start_minutes) / Decimal(60)


def lower_to_shift_end(apps, schema_editor):
    Rules = apps.get_model('attendance', 'AttendanceOvertimeRules')
    for rules in Rules.objects.select_related('settings__working_hours'):
        hours = getattr(rules.settings, 'working_hours', None)
        if hours is None or not hours.break_duration_minutes:
            continue
        span = _span_hours(hours.shift_start, hours.shift_end)
        if span is None or rules.ot_threshold_hours != span.quantize(Decimal('0.01')):
            continue
        new_threshold = (span - Decimal(hours.break_duration_minutes) / Decimal(60)).quantize(Decimal('0.01'))
        if new_threshold > 0:
            rules.ot_threshold_hours = new_threshold
            rules.save(update_fields=['ot_threshold_hours'])


def restore_shift_length(apps, schema_editor):
    Rules = apps.get_model('attendance', 'AttendanceOvertimeRules')
    for rules in Rules.objects.select_related('settings__working_hours'):
        hours = getattr(rules.settings, 'working_hours', None)
        if hours is None or not hours.break_duration_minutes:
            continue
        span = _span_hours(hours.shift_start, hours.shift_end)
        if span is None:
            continue
        expected = (span - Decimal(hours.break_duration_minutes) / Decimal(60)).quantize(Decimal('0.01'))
        if rules.ot_threshold_hours == expected:
            rules.ot_threshold_hours = span.quantize(Decimal('0.01'))
            rules.save(update_fields=['ot_threshold_hours'])


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0050_late_forgive_and_ot_default'),
    ]

    operations = [
        migrations.RunPython(lower_to_shift_end, restore_shift_length),
    ]
