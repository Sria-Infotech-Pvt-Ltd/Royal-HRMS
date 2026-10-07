"""
Phase 6A Task A.2 — seeds the 8 existing LEAVE_TYPE_CHOICES codes as
system LeaveType rows (attributes chosen to reproduce today's behavior
exactly — 'lwp' is the only one with is_unpaid_lwp=True, matching the
LEAVE_LWP constant it replaces), plus every distinct `LeavePolicy.leave_type`
value found in the database that isn't already one of the 8 (an
admin-created custom type, which could not get a LeaveBalance/LeaveRequest
row before Task A.3's field-widening fix).
"""
from django.core.management.base import BaseCommand

SYSTEM_TYPES = [
    {'code': 'casual', 'name': 'Casual Leave', 'is_paid': True},
    {'code': 'earned', 'name': 'Earned Leave', 'is_paid': True, 'is_encashable': True},
    {'code': 'sick', 'name': 'Sick Leave', 'is_paid': True},
    {'code': 'lwp', 'name': 'Leave Without Pay', 'is_paid': False, 'is_unpaid_lwp': True, 'requires_balance': False},
    {'code': 'maternity', 'name': 'Maternity Leave', 'is_paid': True},
    {'code': 'paternity', 'name': 'Paternity Leave', 'is_paid': True},
    {'code': 'bereavement', 'name': 'Bereavement Leave', 'is_paid': True},
    {'code': 'comp_off', 'name': 'Compensatory Off', 'is_paid': True, 'is_comp_off': True},
]


class Command(BaseCommand):
    help = 'Idempotently seed LeaveType rows for the 8 built-in codes plus any custom LeavePolicy.leave_type values (Phase 6A Task A.2).'

    def handle(self, *args, **options):
        from apps.hrms.models import LeavePolicy
        from apps.hrms.models_leave_ledger import LeaveType

        created = unchanged = 0
        for order, spec in enumerate(SYSTEM_TYPES):
            _, was_created = LeaveType.objects.get_or_create(
                code=spec['code'],
                defaults={
                    'name': spec['name'], 'sort_order': order, 'is_system': True,
                    'is_paid': spec.get('is_paid', True), 'is_unpaid_lwp': spec.get('is_unpaid_lwp', False),
                    'is_comp_off': spec.get('is_comp_off', False), 'is_encashable': spec.get('is_encashable', False),
                    'requires_balance': spec.get('requires_balance', True),
                },
            )
            created += was_created
            unchanged += not was_created

        system_codes = {s['code'] for s in SYSTEM_TYPES}
        custom_codes = set(LeavePolicy.objects.exclude(leave_type__in=system_codes).values_list('leave_type', 'leave_type_label'))
        for order, (code, label) in enumerate(custom_codes, start=len(SYSTEM_TYPES)):
            _, was_created = LeaveType.objects.get_or_create(
                code=code, defaults={'name': label or code, 'sort_order': order, 'is_system': False},
            )
            created += was_created
            unchanged += not was_created

        self.stdout.write(self.style.SUCCESS(f'Leave types seeded. Created={created} Unchanged={unchanged}'))
