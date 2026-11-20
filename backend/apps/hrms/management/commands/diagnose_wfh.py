"""Why can this employee not punch in from home, and why do their approved requests not show? Read-only.

    python manage.py diagnose_wfh <email or employee ID>

A punch is made in "work from home" mode only when the employee has a work-from-home request that is APPROVED (the last level has approved,
not only the first) and whose dates cover today. Without one the punch is checked against the office location instead. This prints, in
plain words: whether the employee may use the portal at all, their latest work-from-home requests with each approval level, the punch
mode and location check they get today, and how many requests of each kind they have.
"""
from __future__ import annotations

from types import SimpleNamespace

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Q
from django.utils import timezone

from apps.accounts.models import User
from apps.attendance.services_geofencing import _wfh_radius_m
from apps.hrms.models import LeaveRequest, WorkFromHomeRequest
from core.permissions import HasCompletedOnboardingStatus

_STATUS_HELP = {
    'pending': 'waiting for the first approver (reporting manager)',
    'l2_pending': 'first level approved, WAITING FOR THE SECOND LEVEL (HR): not approved yet, so punching from home is refused',
    'approved': 'approved',
    'rejected': 'rejected',
    'cancelled': 'cancelled by the employee',
}


class Command(BaseCommand):
    help = 'Explain why a work-from-home punch is refused for an employee and whether their approved requests are visible.'

    def add_arguments(self, parser):
        parser.add_argument('employee', help='The employee\'s email address or employee ID.')

    def handle(self, *args, **options):
        key = options['employee'].strip()
        found = list(User.objects.filter(Q(email__iexact=key) | Q(employee_id=key)).values_list('pk', flat=True)[:1])
        if not found:
            raise CommandError(f'No employee has the email or employee ID "{key}".')
        employee = User.objects.only(
            'id', 'email', 'employee_id', 'is_active', 'is_superuser', 'onboarding_status', 'account_activated_at', 'activation_pending',
            'requires_self_service_onboarding',
        ).get(pk=found[0])
        today = timezone.localdate()
        out = self.stdout.write

        out(f'Employee {employee.employee_id}: active={employee.is_active}, onboarding={employee.onboarding_status}, '
            f'activated={"yes" if employee.account_activated_at else "NO"}, activation pending={employee.activation_pending}')
        gate = HasCompletedOnboardingStatus()
        if gate.has_permission(SimpleNamespace(user=employee), None):
            out(self.style.SUCCESS('Portal access: open (requests can be read and made).'))
        else:
            out(self.style.ERROR(f'Portal access: BLOCKED. The server answers every request list with: "{gate.message}"'))
            out(self.style.ERROR('  This alone makes requests "not show" and sends punches the wrong way. Fix the onboarding / activation first.'))

        requests = list(WorkFromHomeRequest.objects.filter(employee=employee).order_by('-created_at')[:6])
        out('')
        out(f'Latest work-from-home requests ({len(requests)} shown), today is {today}:')
        if not requests:
            out(self.style.WARNING('  None. Nothing was ever requested under this account (check the request was made by this same person).'))
        for item in requests:
            covers = item.start_date <= today <= item.end_date
            out(f'  {item.start_date} to {item.end_date}{" (covers today)" if covers else ""} | status {item.status}: {_STATUS_HELP.get(item.status, item.status)}')
            out(f'     level 1: {item.l1_status or "not yet"} | level 2: {item.l2_status or "not yet"} | location "{item.location_label or "unnamed"}" '
                f'({item.location_source}) | location check {"ON, radius " + str(_wfh_radius_m(item)) + " m" if item.enforce_location else "OFF (can punch from anywhere)"}')

        active = WorkFromHomeRequest.approved_for(employee, today)
        out('')
        if active:
            out(self.style.SUCCESS(f'Today: an APPROVED request covers today, so a punch goes in WORK-FROM-HOME mode.'))
            if active.enforce_location:
                out(f'  The phone must be within {_wfh_radius_m(active)} m of the saved point ("{active.location_label or "unnamed"}", {active.location_source}) '
                    f'(plus the GPS accuracy of the reading). Further than that the punch is refused with the distance. '
                    'An approver can switch the location check off for these days on the request.')
            else:
                out('  The location check is OFF for this request: a punch from any place is accepted.')
        else:
            out(self.style.ERROR('Today: NO approved request covers today, so a punch goes in OFFICE mode and is checked against the office location.'))
            out('  From home that is refused. Either the request is not fully approved (see its status above), or its dates do not include today.')

        out('')
        out('Requests of this employee, by kind and status (these are the ones the My Requests screens read):')
        for label, queryset in (('work from home', WorkFromHomeRequest.objects.filter(employee=employee)), ('leave', LeaveRequest.objects.filter(employee=employee))):
            counts = {row['status']: row['n'] for row in queryset.values('status').annotate(n=Count('id'))}
            out(f'  {label}: ' + (', '.join(f'{status} {n}' for status, n in sorted(counts.items())) or 'none'))
