"""
Fills a blank work_location from the employee's Company Code address (work location is now derived, not typed in).

    python manage.py backfill_work_location           # dry run: prints what would change
    python manage.py backfill_work_location --apply   # writes it

Only blank values are filled; a work location someone already entered is never touched.
"""
from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.accounts.services_work_location import work_location_for_branch


class Command(BaseCommand):
    help = 'Fill blank work_location from the Company Code address (dry run unless --apply).'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write the changes (default is a dry run).')

    def handle(self, *args, **options):
        changed = 0
        for employee in User.objects.filter(work_location='').exclude(branch='').exclude(employee_id=''):
            derived = work_location_for_branch(employee.branch)
            if not derived:
                continue
            changed += 1
            self.stdout.write(f'{employee.employee_id}: "" -> "{derived}"')
            if options['apply']:
                employee.work_location = derived
                employee.save(update_fields=['work_location', 'updated_at'])
        verb = 'Updated' if options['apply'] else 'Would update (dry run)'
        self.stdout.write(f'{verb}: {changed} employee(s).')
