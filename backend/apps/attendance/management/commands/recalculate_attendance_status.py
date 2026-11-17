"""
Recalculate Present / Late / Half Day for existing days with the CURRENT attendance settings.

Preview first (writes nothing):
    python manage.py recalculate_attendance_status                      # this month so far
    python manage.py recalculate_attendance_status --month 2026-10
    python manage.py recalculate_attendance_status --employee-id <employee code>

Then apply the same selection:
    python manage.py recalculate_attendance_status --apply

Only days with real IN and OUT punches and a Present / Late / Half Day status are considered; leave, holiday, weekly off,
hand-edited, imported-without-punches and paid/closed payroll days are never touched. See services_recalculate.py.
"""
from __future__ import annotations

import calendar
import logging
from collections import Counter
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.attendance.services_attendance import _get_settings
from apps.attendance.services_recalculate import RecalcPlan, apply_plan, build_plan

logger = logging.getLogger(__name__)

PREVIEW_ROWS = 40


def _month_range(month: str) -> tuple[date, date]:
    today = timezone.localdate()
    if not month:
        return today.replace(day=1), today
    try:
        year, number = (int(part) for part in month.split('-'))
        first = date(year, number, 1)
    except ValueError as exc:
        raise CommandError('--month must look like 2026-11') from exc
    if first > today:
        raise CommandError('--month is in the future; there is nothing to recalculate yet.')
    last = date(year, number, calendar.monthrange(year, number)[1])
    return first, min(last, today)


def _describe_settings(cfg) -> str:
    if cfg is None or not hasattr(cfg, 'punch_rules') or not hasattr(cfg, 'working_hours'):
        return 'No attendance settings saved yet - the built-in defaults would be used.'
    rules, hours = cfg.punch_rules, cfg.working_hours
    return (
        f'Full-day minimum {rules.min_hours_full_day} h, half-day minimum {rules.min_hours_half_day} h, '
        f'break {hours.break_duration_minutes} min, late grace {hours.grace_period_minutes} min.'
    )


class Command(BaseCommand):
    help = 'Recalculate Present/Late/Half Day for existing days using the current attendance settings (preview unless --apply).'

    def add_arguments(self, parser):
        parser.add_argument('--month', default='', help='YYYY-MM. Default: the current month up to today.')
        parser.add_argument('--employee-id', default='', help='Only this employee code.')
        parser.add_argument('--apply', action='store_true', help='Write the changes. Without it, only a preview is shown.')

    def handle(self, *args, **options):
        start, end = _month_range(options['month'])
        self.stdout.write(f'Period: {start} to {end}')
        self.stdout.write(f'Settings in use: {_describe_settings(_get_settings())}')
        plan = build_plan(start, end, employee_code=options['employee_id'])
        self._print_plan(plan)
        if not plan.changes:
            return
        if not options['apply']:
            self.stdout.write(self.style.WARNING('Preview only - nothing was changed. Run again with --apply to write these changes.'))
            return
        updated = apply_plan(plan)
        logger.info('Attendance status recalculated for %s..%s: %s record(s) updated', start, end, updated)
        self.stdout.write(self.style.SUCCESS(f'Done: {updated} record(s) updated, each with an audit entry.'))

    def _print_plan(self, plan: RecalcPlan) -> None:
        moves = Counter((change.old_status, change.new_status) for change in plan.changes)
        self.stdout.write(f'Would change: {len(plan.changes)}   Already correct: {plan.unchanged}')
        for (old, new), count in sorted(moves.items()):
            self.stdout.write(f'  {old} -> {new}: {count}')
        for reason, count in sorted(plan.skipped.items()):
            self.stdout.write(f'Skipped ({reason}): {count}')
        for change in plan.changes[:PREVIEW_ROWS]:
            self.stdout.write(
                f'  {change.day}  {change.employee_code:<10} {change.employee_name[:24]:<24} '
                f'{change.old_status} ({change.old_minutes} min) -> {change.new_status} ({change.new_minutes} min)'
            )
        if len(plan.changes) > PREVIEW_ROWS:
            self.stdout.write(f'  ... and {len(plan.changes) - PREVIEW_ROWS} more')
