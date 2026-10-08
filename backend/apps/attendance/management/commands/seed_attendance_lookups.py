"""
Phase 6B Task A.1/A.2, E.1 — seeds ATTENDANCE_STATUS (behavior attributes
reproducing today's 8 status codes exactly) and PUNCH_SOURCE (the
existing 6 AttendancePunch.source values) as Phase 1 LookupType/
LookupValue rows. Additive: `AttendanceRecord.status`/`AttendancePunch.source`
stay plain CharField+choices, read by every existing call site exactly as
before — nothing switches over to reading these lookups in this pass.
"""
from django.core.management.base import BaseCommand

ATTENDANCE_STATUSES = [
    {'code': 'present', 'label': 'Present', 'day_value_paid': 1.0, 'day_value_present': 1.0, 'counts_as': 'present', 'is_lop': False, 'color': '#16a34a', 'short_code': 'P', 'payroll_category': 'worked'},
    {'code': 'late', 'label': 'Late', 'day_value_paid': 1.0, 'day_value_present': 1.0, 'counts_as': 'present', 'is_lop': False, 'color': '#f59e0b', 'short_code': 'L', 'payroll_category': 'worked'},
    {'code': 'absent', 'label': 'Absent', 'day_value_paid': 0.0, 'day_value_present': 0.0, 'counts_as': 'absent', 'is_lop': True, 'color': '#dc2626', 'short_code': 'A', 'payroll_category': 'lop'},
    {'code': 'half_day', 'label': 'Half Day', 'day_value_paid': 0.5, 'day_value_present': 0.5, 'counts_as': 'present', 'is_lop': False, 'color': '#f97316', 'short_code': 'HD', 'payroll_category': 'worked'},
    {'code': 'weekly_off', 'label': 'Weekly Off', 'day_value_paid': 1.0, 'day_value_present': 0.0, 'counts_as': 'weekly_off', 'is_lop': False, 'color': '#64748b', 'short_code': 'WO', 'payroll_category': 'non_working'},
    {'code': 'holiday', 'label': 'Holiday', 'day_value_paid': 1.0, 'day_value_present': 0.0, 'counts_as': 'holiday', 'is_lop': False, 'color': '#8b5cf6', 'short_code': 'H', 'payroll_category': 'non_working'},
    {'code': 'on_leave', 'label': 'On Leave', 'day_value_paid': 1.0, 'day_value_present': 0.0, 'counts_as': 'leave', 'is_lop': False, 'color': '#0ea5e9', 'short_code': 'LV', 'payroll_category': 'leave'},
    {'code': 'incomplete', 'label': 'Incomplete', 'day_value_paid': 0.0, 'day_value_present': 0.0, 'counts_as': 'other', 'is_lop': True, 'color': '#eab308', 'short_code': 'IC', 'payroll_category': 'lop'},
]

PUNCH_SOURCES = [
    {'code': 'web', 'label': 'Web', 'requires_geofence': True, 'requires_face': False, 'trusted': False},
    {'code': 'mobile', 'label': 'Mobile', 'requires_geofence': True, 'requires_face': False, 'trusted': False},
    {'code': 'biometric', 'label': 'Biometric', 'requires_geofence': False, 'requires_face': True, 'trusted': True},
    {'code': 'manual', 'label': 'Manual', 'requires_geofence': False, 'requires_face': False, 'trusted': False},
    {'code': 'system', 'label': 'System', 'requires_geofence': False, 'requires_face': False, 'trusted': True},
    {'code': 'voice', 'label': 'Voice', 'requires_geofence': True, 'requires_face': True, 'trusted': False},
]


class Command(BaseCommand):
    help = 'Idempotently seed ATTENDANCE_STATUS / PUNCH_SOURCE lookups (Phase 6B Task A.1/A.2, E.1).'

    def handle(self, *args, **options):
        from apps.platform_core.models import LookupType, LookupValue

        created = updated = 0
        for lookup_code, name, rows in (
            ('ATTENDANCE_STATUS', 'Attendance Status', ATTENDANCE_STATUSES),
            ('PUNCH_SOURCE', 'Punch Source', PUNCH_SOURCES),
        ):
            lookup_type, _ = LookupType.objects.get_or_create(
                code=lookup_code, defaults={'name': name, 'module': 'attendance', 'is_system': True, 'allow_custom_values': True},
            )
            for order, spec in enumerate(rows):
                attributes = {k: v for k, v in spec.items() if k not in ('code', 'label')}
                _, was_created = LookupValue.objects.update_or_create(
                    lookup_type=lookup_type, code=spec['code'],
                    defaults={'label': spec['label'], 'sort_order': order, 'attributes': attributes, 'is_system': True},
                )
                created += was_created
                updated += not was_created
        self.stdout.write(self.style.SUCCESS(f'Attendance lookups seeded. Created={created} Updated={updated}'))
