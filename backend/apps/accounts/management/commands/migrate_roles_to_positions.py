"""Copy each seat holder's ROLE permissions onto the seat (PositionPermission) — step 1 of removing Roles.

Dry run by default; pass --apply to write. Safe to re-run: existing rows are left alone. Nothing is taken
away from anyone (permissions are the union of role and seat until the role path is deleted).

People with a role but no seat cannot be converted automatically — they are listed so a decision can be made
(place them in the org chart, or make them a super-admin).
"""
import logging
from datetime import date

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.accounts.models import Placement, PositionPermission, User

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Copy role permissions of current seat holders onto their seats (dry run unless --apply).'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write the changes (default is a dry run).')

    def handle(self, *args, **options):
        apply_changes = options['apply']
        today = date.today()
        placements = (
            Placement.objects.filter(effective_from__lte=today, position__is_active=True)
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))
            .select_related('position', 'employee__role')
        )
        seated_ids = set()
        seats_changed = permissions_added = 0
        for placement in placements:
            employee, seat = placement.employee, placement.position
            seated_ids.add(employee.pk)
            if not employee.role:
                continue
            codenames = list(employee.role.role_permissions.values_list('permission__codename', flat=True))
            existing = set(seat.position_permissions.values_list('permission__codename', flat=True))
            missing = [codename for codename in codenames if codename not in existing]
            flags_differ = (
                seat.can_manage_team != employee.role.can_manage_team
                or seat.can_manage_branch != employee.role.can_manage_branch
            )
            if not missing and not flags_differ:
                continue
            seats_changed += 1
            permissions_added += len(missing)
            self.stdout.write(f'{seat.title} ({seat.org_unit.name}) <- {employee.employee_id} [{employee.role.name}]: +{len(missing)} permissions')
            if apply_changes:
                self._apply(seat, employee, missing)

        unseated = User.objects.filter(is_active=True, role__isnull=False, is_superuser=False).exclude(pk__in=seated_ids)
        for user in unseated.select_related('role'):
            self.stdout.write(self.style.WARNING(f'NO SEAT: {user.employee_id} [{user.role.name}] keeps access only through the role'))
        mode = 'APPLIED' if apply_changes else 'DRY RUN (use --apply to write)'
        self.stdout.write(self.style.SUCCESS(
            f'{mode}: {seats_changed} seats, {permissions_added} permissions, {unseated.count()} people without a seat.'
        ))

    @staticmethod
    def _apply(seat, employee, missing_codenames):
        from apps.accounts.models import Permission

        for permission in Permission.objects.filter(codename__in=missing_codenames):
            PositionPermission.objects.get_or_create(position=seat, permission=permission)
        seat.can_manage_team = employee.role.can_manage_team
        seat.can_manage_branch = employee.role.can_manage_branch
        seat.save(update_fields=['can_manage_team', 'can_manage_branch', 'updated_at'])
        logger.info('Seat %s received %d permissions from role %s', seat.pk, len(missing_codenames), employee.role.name)
