"""
Backfill AttendanceRecord rows for all approved leave requests.

Run once to fix existing data, then leave approval auto-syncs going forward.

Usage:
    python manage.py sync_leave_attendance --schema tenant_royalhrms
    python manage.py sync_leave_attendance --all --dry-run
    python manage.py sync_leave_attendance --schema tenant_royalhrms --year 2026
"""
import logging
from datetime import timedelta

from apps.attendance.models import AttendanceRecord
from apps.hrms.models import LeaveRequest, REQ_APPROVED
from core.tenant_command import TenantCommand

logger = logging.getLogger(__name__)


class Command(TenantCommand):
    help = 'Sync approved leave requests into AttendanceRecord (status=on_leave). Requires --schema/--company-code/--all.'

    def add_tenant_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Preview changes without writing.')
        parser.add_argument('--year', type=int, default=None, help='Limit to a specific year.')

    def handle_tenant(self, client, *args, **options):
        dry_run = options['dry_run']
        year    = options['year']

        qs = LeaveRequest.objects.filter(status=REQ_APPROVED).select_related('employee')
        if year:
            qs = qs.filter(start_date__year=year)

        created = updated = skipped = 0

        for lr in qs.iterator():
            current = lr.start_date
            while current <= lr.end_date:
                if dry_run:
                    exists = AttendanceRecord.objects.filter(
                        employee=lr.employee, date=current,
                    ).first()
                    if exists and exists.status == AttendanceRecord.STATUS_ON_LEAVE:
                        skipped += 1
                    elif exists:
                        self.stdout.write(
                            f'  Would update {lr.employee.email} {current} '
                            f'{exists.status} → on_leave'
                        )
                        updated += 1
                    else:
                        self.stdout.write(
                            f'  Would create {lr.employee.email} {current} on_leave'
                        )
                        created += 1
                else:
                    obj, was_created = AttendanceRecord.objects.update_or_create(
                        employee=lr.employee,
                        date=current,
                        defaults={
                            'status': AttendanceRecord.STATUS_ON_LEAVE,
                            'first_punch_in': None,
                            'last_punch_out': None,
                            'total_working_minutes': 0,
                        },
                    )
                    if was_created:
                        created += 1
                    else:
                        updated += 1

                current += timedelta(days=1)

        action = 'Would have synced' if dry_run else 'Synced'
        self.stdout.write(
            self.style.SUCCESS(
                f'{action}: {created} created, {updated} updated, {skipped} already on_leave.'
            )
        )
