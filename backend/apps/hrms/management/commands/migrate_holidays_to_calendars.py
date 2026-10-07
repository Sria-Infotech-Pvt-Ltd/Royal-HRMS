"""
Phase 6A Task H.4 — builds one HolidayCalendar per (year, branch-or-company-
wide) grouping of existing `Holiday` rows, with one entry per holiday and
one assignment covering the full year. Purely additive: the legacy
`Holiday` table is untouched (not read from by any existing code path
differently as a result), and `HolidayCacheService` (the real resolver
leave validation uses) is not repointed at the new calendars.

Idempotent via get_or_create on (code, year) / (calendar, date, name).
"""
from collections import defaultdict
from datetime import date

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Idempotently migrate Holiday rows into HolidayCalendar/HolidayCalendarEntry/HolidayCalendarAssignment (Phase 6A Task H.4).'

    def handle(self, *args, **options):
        from apps.hrms.models import Holiday
        from apps.hrms.models_holiday_calendar import HolidayCalendar, HolidayCalendarAssignment, HolidayCalendarEntry

        groups = defaultdict(list)
        for holiday in Holiday.objects.filter(is_active=True).select_related('branch'):
            groups[(holiday.date.year, holiday.branch_id)].append(holiday)

        calendars_created = entries_created = assignments_created = 0
        for (year, branch_id), holidays in groups.items():
            code = f'BRANCH_{branch_id}_{year}' if branch_id else f'COMPANY_WIDE_{year}'
            calendar, was_created = HolidayCalendar.objects.get_or_create(
                code=code, year=year,
                defaults={'name': f'{"Company-wide" if branch_id is None else holidays[0].branch.branch_name} holidays {year}', 'is_active': True},
            )
            calendars_created += was_created

            for holiday in holidays:
                _, was_created = HolidayCalendarEntry.objects.get_or_create(
                    calendar=calendar, date=holiday.date, name=holiday.name,
                    defaults={'holiday_type': holiday.holiday_type, 'is_optional': holiday.is_optional},
                )
                entries_created += was_created

            _, was_created = HolidayCalendarAssignment.objects.get_or_create(
                calendar=calendar, branch_id=branch_id, effective_from=date(year, 1, 1),
                defaults={'effective_to': date(year, 12, 31)},
            )
            assignments_created += was_created

        self.stdout.write(self.style.SUCCESS(
            f'Holiday calendars migrated. Calendars created={calendars_created} '
            f'Entries created={entries_created} Assignments created={assignments_created}'
        ))
