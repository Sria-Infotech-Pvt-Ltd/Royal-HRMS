"""Move access from ROLES to the ORG CHART — run this before roles are deleted.

What it does (dry run unless --apply; safe to re-run, nothing is ever taken away):
  1. BASELINE: the default employee role's permissions become company-wide baseline permissions (self-service).
  2. SEATS: each current seat holder's role permissions (beyond the baseline) and scope flags are copied onto the
     seat they hold, so whoever holds that seat later inherits them.
  3. PEOPLE WITHOUT A SEAT cannot be converted automatically and are listed. With --promote-unseated-admins, those
     whose role has full access are made super-admins (a flag on the person, not a role); everyone else must be
     placed in the org chart.
"""
import logging
from datetime import date

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.accounts.models import BaselinePermission, Permission, Placement, PositionPermission, Role, User

logger = logging.getLogger(__name__)

SEAT_FLAGS = ('can_manage_team', 'can_manage_branch', 'exclude_from_payroll', 'exclude_from_headcount')


class Command(BaseCommand):
    help = 'Copy role access onto the org chart (baseline + seats). Dry run unless --apply.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write the changes (default is a dry run).')
        parser.add_argument(
            '--promote-unseated-admins', action='store_true',
            help='Make people with no seat whose role has full access super-admins.',
        )

    def handle(self, *args, **options):
        apply_changes = options['apply']
        baseline = self._baseline(apply_changes)
        seated_ids, seats_changed, permissions_added = self._seats(apply_changes, baseline)
        unseated = self._unseated(seated_ids, apply_changes and options['promote_unseated_admins'])
        mode = 'APPLIED' if apply_changes else 'DRY RUN (use --apply to write)'
        self.stdout.write(self.style.SUCCESS(
            f'{mode}: baseline {len(baseline)} permissions, {seats_changed} seats, '
            f'{permissions_added} seat permissions, {unseated} people without a seat.'
        ))

    def _baseline(self, apply_changes: bool) -> set[str]:
        role = Role.objects.filter(is_default_employee_role=True).first()
        codenames = set(BaselinePermission.objects.values_list('permission__codename', flat=True))
        if role:
            wanted = set(role.role_permissions.values_list('permission__codename', flat=True))
            self.stdout.write(f'BASELINE <- default employee role [{role.name}]: +{len(wanted - codenames)} permissions')
            if apply_changes:
                for permission in Permission.objects.filter(codename__in=wanted - codenames):
                    BaselinePermission.objects.get_or_create(permission=permission)
            codenames |= wanted
        return codenames

    def _seats(self, apply_changes: bool, baseline: set[str]):
        today = date.today()
        placements = (
            Placement.objects.filter(effective_from__lte=today, position__is_active=True)
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))
            .select_related('position', 'employee__role')
        )
        seated_ids, seats_changed, permissions_added = set(), 0, 0
        for placement in placements:
            employee, seat = placement.employee, placement.position
            seated_ids.add(employee.pk)
            if not employee.role:
                continue
            role = employee.role
            codenames = set(role.role_permissions.values_list('permission__codename', flat=True)) - baseline
            existing = set(seat.position_permissions.values_list('permission__codename', flat=True))
            missing = sorted(codenames - existing)
            flags_differ = any(getattr(seat, flag) != getattr(role, flag) for flag in SEAT_FLAGS)
            if not missing and not flags_differ:
                continue
            seats_changed += 1
            permissions_added += len(missing)
            self.stdout.write(f'{seat.title} ({seat.org_unit.name}) <- {employee.employee_id} [{role.name}]: +{len(missing)} permissions')
            if apply_changes:
                for permission in Permission.objects.filter(codename__in=missing):
                    PositionPermission.objects.get_or_create(position=seat, permission=permission)
                for flag in SEAT_FLAGS:
                    setattr(seat, flag, getattr(seat, flag) or getattr(role, flag))
                seat.save(update_fields=[*SEAT_FLAGS, 'updated_at'])
                logger.info('Seat %s received %d permissions from role %s', seat.pk, len(missing), role.name)
        return seated_ids, seats_changed, permissions_added

    def _unseated(self, seated_ids: set, promote: bool) -> int:
        people = User.objects.filter(is_active=True, role__isnull=False, is_superuser=False).exclude(pk__in=seated_ids).select_related('role')
        count = 0
        for user in people:
            count += 1
            if promote and user.role.is_full_access:
                user.is_superuser = True
                user.save(update_fields=['is_superuser', 'updated_at'])
                self.stdout.write(self.style.WARNING(f'PROMOTED to super-admin: {user.employee_id} [{user.role.name}]'))
            else:
                self.stdout.write(self.style.WARNING(f'NO SEAT: {user.employee_id} [{user.role.name}] keeps access only through the role'))
        return count
