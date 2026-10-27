"""
Correct ONE branch's office location (coordinates, radius, geofencing switch, address).

It never guesses: every value must be given on the command line, and nothing is written without --apply. Without
--apply it only prints the branch's current values and what would change, plus any warning about the coordinates.

    python manage.py set_branch_location --code KON
        (shows the current location of branch KON)

    python manage.py set_branch_location --code KON --latitude <lat> --longitude <lon> --radius 150 --apply
    python manage.py set_branch_location --code KON --disable-geofencing --apply
        (switches geofencing off for a branch while its coordinates are being confirmed)

Coordinates must be confirmed by the business (open the office in a map, copy the pin). Use the same validation as
the Company Codes form.
"""
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import AuditLog
from apps.branch.geo import MAX_RADIUS_METERS, MIN_RADIUS_METERS, coordinate_errors, location_warnings
from apps.branch.models import Branch


class Command(BaseCommand):
    help = "Show or correct one branch's office coordinates, radius, geofencing switch and address."

    def add_arguments(self, parser):
        parser.add_argument('--code', required=True, help='Branch code, e.g. KON')
        parser.add_argument('--latitude')
        parser.add_argument('--longitude')
        parser.add_argument('--radius', type=int, help=f'Metres, {MIN_RADIUS_METERS} to {MAX_RADIUS_METERS}')
        parser.add_argument('--address')
        parser.add_argument('--enable-geofencing', action='store_true')
        parser.add_argument('--disable-geofencing', action='store_true')
        parser.add_argument('--apply', action='store_true', help='Write the change (otherwise only shows it)')

    def handle(self, *args, **options):
        branch = Branch.objects.select_related('state', 'city').filter(branch_code=options['code']).first()
        if branch is None:
            raise CommandError(f"No branch with code {options['code']!r}.")
        if options['enable_geofencing'] and options['disable_geofencing']:
            raise CommandError('Choose either --enable-geofencing or --disable-geofencing, not both.')

        self.stdout.write(f'{branch.branch_code} {branch.branch_name} ({branch.city.name}, {branch.state.name})')
        self.stdout.write(
            f'  now: lat={branch.latitude} lon={branch.longitude} radius={branch.allowed_radius_meters} m '
            f'geofencing={"on" if branch.geofencing_enabled else "off"}'
        )
        self.stdout.write(f'       address={branch.address!r}')

        changes = self._changes(branch, options)
        if not changes:
            self.stdout.write('No change requested.')
            return

        for field, value in changes.items():
            setattr(branch, field, value)
        self._check(branch)
        self.stdout.write('  will set: ' + ', '.join(f'{field}={value!r}' for field, value in changes.items()))

        if not options['apply']:
            self.stdout.write(self.style.WARNING('Dry run. Nothing was written. Add --apply to save.'))
            return
        branch.save(update_fields=[*changes.keys(), 'updated_at'])
        AuditLog.objects.create(
            user=None, action='branch_location_set_by_command', module='branch', object_id=str(branch.pk),
            changes={field: str(value) for field, value in changes.items()},
        )
        self.stdout.write(self.style.SUCCESS('Saved.'))

    @staticmethod
    def _decimal(raw, name):
        try:
            return Decimal(raw)
        except (InvalidOperation, TypeError):
            raise CommandError(f'--{name} must be a number.')

    def _changes(self, branch, options):
        changes = {}
        if options['latitude'] is not None or options['longitude'] is not None:
            if options['latitude'] is None or options['longitude'] is None:
                raise CommandError('Give --latitude and --longitude together.')
            changes['latitude'] = self._decimal(options['latitude'], 'latitude')
            changes['longitude'] = self._decimal(options['longitude'], 'longitude')
        if options['radius'] is not None:
            if not MIN_RADIUS_METERS <= options['radius'] <= MAX_RADIUS_METERS:
                raise CommandError(f'--radius must be between {MIN_RADIUS_METERS} and {MAX_RADIUS_METERS} metres.')
            changes['allowed_radius_meters'] = options['radius']
        if options['address'] is not None:
            if not options['address'].strip():
                raise CommandError('--address must not be blank.')
            changes['address'] = options['address'].strip()
        if options['enable_geofencing']:
            changes['geofencing_enabled'] = True
        if options['disable_geofencing']:
            changes['geofencing_enabled'] = False
        return changes

    def _check(self, branch):
        problems = coordinate_errors(branch.latitude, branch.longitude)
        if problems:
            raise CommandError('; '.join(problems.values()))
        if branch.geofencing_enabled and not branch.has_coordinates:
            raise CommandError('Cannot enable geofencing without coordinates.')
        for warning in location_warnings(branch.latitude, branch.longitude, branch.state.name, branch.city.name):
            self.stdout.write(self.style.WARNING(f'  WARNING: {warning}'))
