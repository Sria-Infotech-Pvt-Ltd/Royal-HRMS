"""
Management command: seed_demo_personas

DEMO / TEST DATA ONLY. Creates the four persona logins used to check the Employee Directory against the
reference — one per kind of access — if they do not exist yet:

    payroll@example.com   Payroll Admin          (QA0001)
    manager@example.com   Reporting Manager      (QA0002)
    employee@example.com  Employee (self-service)(QA0003, reports to the manager)
    hr@example.com        HR Business Partner    (QA0004)

All four use the password `demo@1`. @example.com is a reserved domain, so nothing sent to these addresses can
reach a real mailbox. The command only creates missing users (never changes an existing one), needs DEBUG on,
and creates a "Kondapur Office" branch only when the database has no active branch at all. Afterwards run
`seed_demo_employee_details` to give them (and the dummy employees) complete records.

Run:  python manage.py seed_demo_personas
"""
from datetime import date

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import OrgUnit, Permission, Placement, Position, PositionPermission, User

PASSWORD = 'demo@1'
BRANCH_NAME = 'Kondapur Office'

# What each demo persona's seat is allowed to do (an employee only gets the company baseline).
PERSONA_ACCESS = {
    'payroll_admin': {'permissions': ['employees.view', 'payroll.view', 'payroll.create', 'payroll.edit'], 'team': False},
    'manager':       {'permissions': ['employees.view', 'leave.approve', 'attendance.view'], 'team': True},
    'employee':      {'permissions': [], 'team': False},
    'hr_admin':      {'permissions': ['employees.view', 'employees.create', 'employees.edit', 'leave.approve', 'onboarding.approve', 'payroll.view'], 'team': False},
}

# email, kind of access, employee_id, full_name, branch, reports_to_manager
PERSONAS = [
    ('payroll@example.com',  'payroll_admin', 'QA0001', 'QA Payroll Admin',     BRANCH_NAME, False),
    # The manager's own branch stays blank on purpose: opening any employee record auto-assigns a branch's
    # manager-less employees to the branch manager (EmployeeDetailView), which would quietly hand this demo
    # account employees it should not have.
    ('manager@example.com',  'manager',       'QA0002', 'QA Reporting Manager', '',          False),
    ('employee@example.com', 'employee',      'QA0003', 'QA Employee',          BRANCH_NAME, True),
    ('hr@example.com',       'hr_admin',      'QA0004', 'QA HR Partner',        BRANCH_NAME, False),
]


def _ensure_branch():
    from apps.branch.models import Branch, City, State
    if Branch.objects.filter(status=Branch.STATUS_ACTIVE).exists():
        return
    if not State.objects.exists():
        call_command('seed_reference_data')
    state = State.objects.filter(name='Telangana').first() or State.objects.first()
    city = City.objects.filter(state=state, name='Hyderabad').first() or City.objects.filter(state=state).first()
    Branch.objects.create(
        branch_code='KDP', branch_name=BRANCH_NAME, address='Kondapur, Hyderabad', state=state, city=city,
        is_headquarter=True,
    )


def _place_in_demo_seat(user, access_kind, title):
    """A seat in a demo org unit carrying this persona's access, held by `user` from their joining date."""
    access = PERSONA_ACCESS[access_kind]
    unit, _ = OrgUnit.objects.get_or_create(name='QA Demo Personas')
    seat = Position.objects.create(org_unit=unit, title=title, grade='L2', can_manage_team=access['team'])
    for codename in access['permissions']:
        module, _, action = codename.partition('.')
        permission, _ = Permission.objects.get_or_create(codename=codename, defaults={'module': module, 'action': action})
        PositionPermission.objects.get_or_create(position=seat, permission=permission)
    Placement.objects.create(position=seat, employee=user, effective_from=user.date_of_joining or date(2024, 4, 1))


def create_missing_personas():
    """Create whichever of the four persona logins do not exist yet (never changes an existing user).
    Returns the emails created. Callers are responsible for the DEBUG / confirmation guard."""
    _ensure_branch()
    created = []
    manager = None
    for email, access_kind, employee_id, full_name, branch, reports_to_manager in PERSONAS:
        user = User.objects.filter(email=email).first()
        if user is None:
            user = User.objects.create_user(
                email=email, password=PASSWORD, full_name=full_name, employee_id=employee_id,
                branch=branch, phone='', date_of_joining=date(2024, 4, 1),
                must_change_password=False, onboarding_status=User.ONBOARDING_COMPLETE,
                assessment_status=User.ASSESSMENT_COMPLETE,
                employment_status=User.EMPLOYMENT_STATUS_CONFIRMED, employee_type='Permanent',
            )
            _place_in_demo_seat(user, access_kind, full_name)
            created.append(email)
        if access_kind == 'manager':
            manager = user
        if reports_to_manager and manager is not None and user.reporting_manager_id is None:
            User.objects.filter(pk=user.pk).update(reporting_manager=manager)
    return created


class Command(BaseCommand):
    help = 'Create the four demo persona logins (Payroll Admin, Reporting Manager, Employee, HR) if missing.'

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Demo personas can only be created with DEBUG on.')
        created = create_missing_personas()
        self.stdout.write(self.style.SUCCESS(
            f'Created {len(created)} persona login(s): {", ".join(created) or "none (all already exist)"}.'
        ))
