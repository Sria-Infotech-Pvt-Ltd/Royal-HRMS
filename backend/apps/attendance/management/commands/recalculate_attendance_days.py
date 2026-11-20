"""Recalculate recent attendance days that were saved with the old punch-pairing rule (e.g. an approved earlier punch-in not counted).

    python manage.py recalculate_attendance_days                 # the last 14 days, everyone
    python manage.py recalculate_attendance_days --dry-run       # only show what would change
    python manage.py recalculate_attendance_days --days 45 --employee surya@example.com

Safe to run again: it only touches days whose saved hours differ from what their punches give, never a day HR edited by hand, never leave /
holiday / week-off / absent days, never a day in a paid or closed payroll cycle. Deploy runs it automatically after the migrations.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.attendance.services_recalculate_days import recalculate_correction_days


def _time(value) -> str:
    return value.strftime('%H:%M') if value else '-'


class Command(BaseCommand):
    help = 'Recalculate recent days saved with the old punch-pairing rule.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=14, help='How many days back to look (default 14).')
        parser.add_argument('--employee', default='', help='Only this employee (employee ID or email).')
        parser.add_argument('--dry-run', action='store_true', help='Show what would change without changing it.')

    def handle(self, *args, **options):
        changes = recalculate_correction_days(options['days'], employee_key=options['employee'].strip(), dry_run=options['dry_run'])
        verb = 'would change' if options['dry_run'] else 'recalculated'
        for change in changes:
            old, new = change['before'], change['after']
            self.stdout.write(f'  {change["employee_id"]} {change["date"]}: {old[0]} {_time(old[1])}-{_time(old[2])} {old[3]} min  ->  {new[0]} {_time(new[1])}-{_time(new[2])} {new[3]} min')
        self.stdout.write(self.style.SUCCESS(f'{len(changes)} day(s) {verb}.') if changes else 'No day needs recalculating.')
