"""
READ-ONLY: separation requests still waiting for a decision although their last working day has already passed.

    python manage.py report_stale_separations

Prints the request number, status and last working day (no names). Nothing is closed or changed: HR decides what to do with each.
"""
from datetime import date

from django.core.management.base import BaseCommand

from apps.hrms.models import SEP_PENDING, SEP_STAGE2_PENDING, SeparationRequest


class Command(BaseCommand):
    help = 'List separation requests pending past their last working day (read-only).'

    def handle(self, *args, **options):
        stale = SeparationRequest.objects.filter(
            status__in=(SEP_PENDING, SEP_STAGE2_PENDING), proposed_last_working_day__lt=date.today(),
        ).order_by('proposed_last_working_day')
        for item in stale:
            self.stdout.write(f'SEP-{item.request_number}  {item.status}  last working day {item.proposed_last_working_day}  (created {item.created_at:%Y-%m-%d})')
        self.stdout.write(f'{stale.count()} stale request(s). Nothing was changed.')
