"""
Phase 6A Task H.4 verification — for every legacy `Holiday` row, confirms
a matching `HolidayCalendarEntry` exists under the calendar assigned to
that holiday's branch (or company-wide) for that date, via
`services_holiday_calendar.is_holiday_for_employee()`-equivalent lookup.
Counts and ids only, per the prompt's own "Counts and ids only" rule.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Verify every legacy Holiday row has a matching HolidayCalendarEntry (Phase 6A Task H.4).'

    def handle(self, *args, **options):
        from django.db.models import Q

        from apps.hrms.models import Holiday
        from apps.hrms.models_holiday_calendar import HolidayCalendarAssignment

        checked = 0
        mismatches = []
        for holiday in Holiday.objects.filter(is_active=True):
            checked += 1
            assignment = (
                HolidayCalendarAssignment.objects.filter(
                    Q(branch_id=holiday.branch_id) if holiday.branch_id else Q(branch__isnull=True),
                    effective_from__lte=holiday.date,
                )
                .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=holiday.date))
                .select_related('calendar')
                .first()
            )
            if assignment is None:
                mismatches.append(str(holiday.id))
                continue
            matches = assignment.calendar.entries.filter(date=holiday.date, name=holiday.name).exists()
            if not matches:
                mismatches.append(str(holiday.id))

        if mismatches:
            self.stdout.write(self.style.ERROR(
                f'Checked={checked} Mismatches={len(mismatches)} ids={mismatches[:20]}'
                + (' (truncated)' if len(mismatches) > 20 else '')
            ))
        else:
            self.stdout.write(self.style.SUCCESS(f'Checked={checked} Mismatches=0'))
