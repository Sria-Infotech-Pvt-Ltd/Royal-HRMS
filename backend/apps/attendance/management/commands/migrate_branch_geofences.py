"""
Phase 6B Task F.2 — one `Geofence` per branch with `geofencing_enabled=True`
and real coordinates, identical centre/radius/enabled state. Idempotent
via get_or_create keyed on a derived code. Purely additive — does not
touch `Branch.latitude`/`longitude`/`allowed_radius_meters`/`geofencing_enabled`,
which stay the live fields `GeofencingService` reads.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Idempotently create one Geofence per branch with geofencing enabled (Phase 6B Task F.2).'

    def handle(self, *args, **options):
        from apps.attendance.models_geofence import Geofence
        from apps.branch.models import Branch

        created = unchanged = 0
        for branch in Branch.objects.filter(geofencing_enabled=True).exclude(latitude__isnull=True).exclude(longitude__isnull=True):
            _, was_created = Geofence.objects.get_or_create(
                code=f'BRANCH_{branch.id}',
                defaults={
                    'name': f'{branch.branch_name} geofence', 'type': Geofence.TYPE_CIRCLE,
                    'branch': branch, 'center_latitude': branch.latitude, 'center_longitude': branch.longitude,
                    'radius_meters': branch.allowed_radius_meters, 'is_active': True,
                },
            )
            created += was_created
            unchanged += not was_created
        self.stdout.write(self.style.SUCCESS(f'Branch geofences migrated. Created={created} Unchanged={unchanged}'))
