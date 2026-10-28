"""
Retire a leftover designation (for example the "Test" entry) safely.

    python manage.py retire_designation --name Test            # dry run: says who uses it, changes nothing
    python manage.py retire_designation --name Test --apply    # deactivates it, only when nobody uses it

"Used" means an employee's designation text or a position's designation link/title is this name. If anything uses it the command
lists them (employee ids and position titles only) and refuses to change anything. It deactivates (is_active=False); it never deletes.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import Designation, Position, User


class Command(BaseCommand):
    help = 'Deactivate an unused designation; list its users instead when it is in use (dry run unless --apply).'

    def add_arguments(self, parser):
        parser.add_argument('--name', required=True, help='The designation name, matched ignoring case.')
        parser.add_argument('--apply', action='store_true', help='Deactivate it (only when nothing uses it).')

    def handle(self, *args, **options):
        name = options['name'].strip()
        designations = list(Designation.objects.filter(name__iexact=name))
        if not designations:
            raise CommandError(f'No designation named "{name}".')

        employees = list(User.objects.filter(designation__iexact=name).exclude(employee_id='').values_list('employee_id', flat=True))
        positions = list(
            Position.objects.filter(designation_ref__in=designations).values_list('title', flat=True)
            | Position.objects.filter(title__iexact=name).values_list('title', flat=True)
        )
        if employees or positions:
            self.stdout.write(f'"{name}" is IN USE, so it was not changed.')
            if employees:
                self.stdout.write('  employees: ' + ', '.join(sorted(employees)))
            if positions:
                self.stdout.write('  positions: ' + ', '.join(sorted(set(positions))))
            return

        active = [designation for designation in designations if designation.is_active]
        if not options['apply']:
            self.stdout.write(f'"{name}" is not used by any employee or position. DRY RUN: would deactivate {len(active)} entry(ies).')
            return
        for designation in active:
            designation.is_active = False
            designation.save(update_fields=['is_active', 'updated_at'])
        self.stdout.write(f'Deactivated {len(active)} "{name}" designation(s).')
