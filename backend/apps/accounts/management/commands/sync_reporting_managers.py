"""
Brings every employee's stored reporting manager (L1, the immediate head) in line with the org chart.

    python manage.py sync_reporting_managers           # dry run: prints what would change
    python manage.py sync_reporting_managers --apply   # writes it

Only people whose manager is blank or was copied from the org chart earlier are considered; a manager chosen by hand is never
touched. Day-to-day this happens by itself whenever the org chart changes (see signals.py); run this once to fix what is already
stale, and again if someone's seat starts or ends on a date with no edit (a placement that begins tomorrow).
"""
from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.accounts.services_org_chart_managers import resync_all


class Command(BaseCommand):
    help = 'Set reporting managers from the org chart for everyone whose manager was not picked by hand (dry run unless --apply).'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write the changes (default is a dry run).')

    def handle(self, *args, **options):
        changes = resync_all(dry_run=not options['apply'])
        manager_ids = {pk for _employee, old_id, new_id in changes for pk in (old_id, new_id) if pk}
        names = dict(User.objects.filter(pk__in=manager_ids).values_list('pk', 'full_name'))
        for employee, old_id, new_id in changes:
            self.stdout.write(f'{employee.employee_id}: {names.get(old_id) or "(none)"} -> {names.get(new_id) or "(none)"}')
        verb = 'Changed' if options['apply'] else 'Would change'
        self.stdout.write(self.style.SUCCESS(f'{verb} {len(changes)} reporting manager(s).'))
