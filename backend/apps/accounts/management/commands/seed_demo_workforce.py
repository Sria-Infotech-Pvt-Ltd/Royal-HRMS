"""
Management command: seed_demo_workforce

DEMO / TEST DATA ONLY — for a development or demo server that no client uses. Builds a realistic Indian workforce
so every screen can be checked as each persona: the four demo logins (password `demo@1`), 24 employees across
Hyderabad, Bengaluru, Pune and Chennai, about three months of backdated attendance (weekly offs, holidays, late
marks, half days, work-from-home, approved leave, absences, punch corrections) and two real payroll cycles per
office, run through the project's own payroll endpoints until they are paid.

Safe by construction:
  * needs --confirm-demo-server (a deliberate "yes, this server is for demo data") for anything that writes;
  * everything it creates is @example.com, so no email can reach a real mailbox — and emails/notifications are
    switched off for the whole run;
  * never changes an existing user's details, never touches a payroll cycle it did not create, never overwrites
    an attendance day that already has a record;
  * re-running continues where it stopped; --cleanup removes the people, cycles and holidays it made.

Run:  python manage.py seed_demo_workforce --dry-run
      python manage.py seed_demo_workforce --confirm-demo-server
      python manage.py seed_demo_workforce --confirm-demo-server --skip-payroll
      python manage.py seed_demo_workforce --confirm-demo-server --cleanup
"""
import uuid
from datetime import timedelta
from unittest import mock

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import ProtectedError
from django.utils import timezone

from apps.accounts import demo_workforce_data as data
from apps.accounts.demo_workforce_attendance import generate_for_employee, weekly_off_weekdays
from apps.accounts.demo_workforce_payroll import PayrollStepError, run_cycle
from apps.accounts.management.commands.seed_demo_employee_details import fill_user
from apps.accounts.management.commands.seed_demo_personas import PERSONAS, create_missing_personas
from apps.accounts.models import EmployeeCodeSettings, Placement, Position, User
from apps.accounts.services_placement import assign_position
from apps.attendance.models import EmployeeWeeklyOffAssignment, WeeklyDayPolicy
from apps.attendance.services_hr import bulk_assign_weekly_off
from apps.branch.models import Branch, City, State
from apps.hrms.models import Holiday
from apps.payroll.models import (
    EmployeePayslip, PayrollCycle, PayrollSettings, SalaryComponent, SalaryStructure, SalaryTransferBatch,
    SalaryTransferItem, StatutoryConfig,
)

PERSONA_EMAILS = [row[0] for row in PERSONAS]


class _RehearsalDone(Exception):
    """Raised at the end of a --rehearse run so the surrounding transaction rolls everything back."""


def _ensure_branches() -> dict:
    """City → Branch. Hyderabad is the existing active branch; the other offices are created when missing."""
    branches = {}
    for city_name, spec in data.LOCATIONS.items():
        state = State.objects.get(name=spec['state'])
        city = City.objects.get(name=city_name, state=state)
        if city_name == 'Hyderabad':
            branch = Branch.objects.filter(branch_name=spec['name']).first() or Branch.objects.filter(
                status=Branch.STATUS_ACTIVE).first()
        else:
            branch, _ = Branch.objects.get_or_create(branch_code=spec['code'], defaults=dict(
                branch_name=spec['name'], address=spec['address'], state=state, city=city, is_metro=spec['metro']))
        branches[city_name] = branch or Branch.objects.create(
            branch_code=spec['code'], branch_name=spec['name'], address=spec['address'], state=state, city=city,
            is_headquarter=True)
        if state.name in data.PT_SLABS:
            StatutoryConfig.objects.get_or_create(state=state, defaults=dict(pt_applicable=True, pt_slabs=data.PT_SLABS[state.name]))
    return branches


def _ensure_payroll_setup() -> None:
    """Payroll needs company settings and a default salary structure; add them only if the server has none."""
    PayrollSettings.objects.get_or_create(pk=PayrollSettings.objects.values_list('pk', flat=True).first() or uuid.uuid4())
    if SalaryStructure.objects.filter(is_default=True, is_active=True).exists():
        return
    name, components = data.DEFAULT_STRUCTURE
    structure, _ = SalaryStructure.objects.get_or_create(name=name, defaults=dict(is_default=True, is_active=True))
    for order, (component, kind, percent) in enumerate(components):
        SalaryComponent.objects.get_or_create(structure=structure, name=component, defaults=dict(
            component_type=kind, calculation_type=SalaryComponent.CALC_PCT_CTC, value=percent, order=order))


def _ensure_weekly_off_policy() -> WeeklyDayPolicy:
    policy = WeeklyDayPolicy.objects.filter(is_default=True, is_active=True).first() or WeeklyDayPolicy.objects.filter(
        is_active=True).first()
    return policy or WeeklyDayPolicy.objects.create(
        name='Standard 5-Day Week', policy_code='WD-DEMO', description='Monday–Friday working, Saturday and Sunday off.',
        is_default=True)


def _ensure_holidays() -> dict:
    for name, day, kind in data.HOLIDAYS:
        Holiday.objects.get_or_create(name=name, date=day, branch=None, defaults=dict(
            holiday_type=kind, description=data.HOLIDAY_TAG))
    return {h.date: h.name for h in Holiday.objects.filter(branch__isnull=True, is_active=True)}


def _vacant_seats(unit_name: str) -> list:
    used = set(Placement.objects.values_list('position_id', flat=True).distinct())
    seats = Position.objects.filter(org_unit__name=unit_name, is_active=True).exclude(id__in=used).order_by('title')
    return [seat for seat in seats if not any(word in seat.title for word in ('Head', 'Director', 'Lead'))]


class Command(BaseCommand):
    help = 'Seed a realistic demo workforce, backdated attendance and paid payroll cycles (demo servers only).'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show the plan; write nothing.')
        parser.add_argument('--confirm-demo-server', action='store_true', help='Required for anything that writes.')
        parser.add_argument('--rehearse', action='store_true',
                            help='Run the whole seed inside one transaction and roll it back: shows what a real run '
                                 'would do (and any error) while leaving the database exactly as it was.')
        parser.add_argument('--cleanup', action='store_true', help='Remove the people, cycles and holidays this seed made.')
        parser.add_argument('--skip-payroll', action='store_true', help='Stop after attendance; run no payroll cycles.')
        parser.add_argument('--with-photos', action='store_true', help='Also generate profile pictures (uploads to storage).')
        parser.add_argument('--actor-email', help='Admin who runs payroll (default: the first active superuser).')
        parser.add_argument('--approve-as-any-manager', action='store_true',
                            help='Let the seed approve attendance on behalf of real (non-@example.com) managers.')

    def handle(self, *args, **options):
        database = connection.settings_dict
        self.stdout.write(f"Database: {database.get('NAME')} on {database.get('HOST') or 'local file'}")
        if options['dry_run']:
            return self._print_plan()
        if not options['confirm_demo_server']:
            raise CommandError('Refusing to write without --confirm-demo-server (this seeds fake people and payroll).')
        if options['cleanup']:
            return self._cleanup()
        actor = self._actor(options['actor_email'])
        try:
            with transaction.atomic():
                self._seed(options, actor)
                if options['rehearse']:
                    raise _RehearsalDone()
        except _RehearsalDone:
            self.stdout.write(self.style.WARNING('Rehearsal only — everything above was rolled back; nothing was saved.'))
            return
        self.stdout.write(self.style.SUCCESS('Done. Log in as payroll@ / manager@ / employee@ / hr@example.com (password demo@1).'))

    def _seed(self, options, actor):
        # Nothing in this run may email or notify anyone: payroll's own helpers plus the shared SMTP sender are stubbed.
        with mock.patch('apps.accounts.utils.send_template_email'), \
                mock.patch('apps.payroll.notifications._send_email'), mock.patch('apps.payroll.notifications._notify'):
            branches, holidays, policy = self._prepare()
            people = self._create_people(branches, policy, options['with_photos'])
            self._attendance(people, branches, holidays, policy, actor)
            if not options['skip_payroll']:
                self._payroll(people, branches, actor, options['approve_as_any_manager'])

    def _actor(self, email):
        query = User.objects.filter(is_active=True)
        actor = query.filter(email=email).first() if email else query.filter(is_superuser=True).first()
        if actor is None:
            raise CommandError('No admin found to run payroll — pass --actor-email of an active admin.')
        return actor

    def _print_plan(self):
        self.stdout.write('[dry-run] would create/ensure:')
        self.stdout.write(f'  personas: {", ".join(PERSONA_EMAILS)}')
        self.stdout.write(f'  offices: {", ".join(f"{c} ({s["name"]})" for c, s in data.LOCATIONS.items())}')
        for first, last, _g, city, unit, joined, kind in data.ROSTER:
            seats = len(_vacant_seats(unit))
            self.stdout.write(f'  {first} {last:<12} {city:<10} {unit:<24} joined {joined}  {kind:<9} (vacant seats in unit: {seats})')
        self.stdout.write(f'  attendance {data.ATTENDANCE_START} → yesterday; payroll periods: '
                          + ', '.join(f'{a}…{b}' for a, b, _ in data.PERIODS))

    def _prepare(self):
        created = create_missing_personas()
        self.stdout.write(f'Personas created: {", ".join(created) or "none (already there)"}')
        _ensure_payroll_setup()
        return _ensure_branches(), _ensure_holidays(), _ensure_weekly_off_policy()

    @transaction.atomic
    def _create_one(self, row, branches, is_lead, manager):
        first, last, gender, city, unit, joined, kind = row
        email = data.email_for(first, last)
        user = User.objects.filter(email=email).first()
        if user is not None:
            return user, False
        seats = _vacant_seats(unit)
        if not seats:
            self.stdout.write(self.style.WARNING(f'  no vacant seat in {unit} — skipped {first} {last}'))
            return None, False
        user = User.objects.create_user(
            email=email, password=data.PASSWORD, full_name=f'{first} {last}',
            employee_id=EmployeeCodeSettings.generate_employee_id(first_name=first.split()[0], last_name=last, date_of_joining=joined),
            employee_type=kind, date_of_joining=joined, branch=branches[city].branch_name, phone='',
            must_change_password=False, onboarding_status=User.ONBOARDING_COMPLETE,
            assessment_status=User.ASSESSMENT_COMPLETE,
        )
        assign_position(user, seats[0], effective_from=joined)
        if is_lead:  # a team lead's seat manages a team
            Position.objects.filter(pk=seats[0].pk).update(can_manage_team=True)
        User.objects.filter(pk=user.pk).update(branch=branches[city].branch_name, reporting_manager=manager)
        return user, True

    def _create_people(self, branches, policy, with_photos) -> list:
        qa_manager = User.objects.filter(email='manager@example.com').first()
        leads, people, created = {}, [], 0
        for row in data.ROSTER:
            city = row[3]
            is_lead = data.team_leads().get(city) == (row[0], row[1])
            manager = qa_manager if city == 'Hyderabad' else leads.get(city)
            user, was_created = self._create_one(row, branches, is_lead, manager)
            if user is None:
                continue
            created += was_created
            if is_lead:
                leads.setdefault(city, user)
            people.append((user, row))
        today = timezone.localdate()
        everyone = [u for u, _ in people] + list(User.objects.filter(email__in=PERSONA_EMAILS))
        for user in everyone:
            fill_user(user, today, skip_photos=not with_photos)
        self._fix_addresses(people, branches)
        for user in everyone:  # only people with no weekly-off pattern yet — an existing pattern is never replaced
            if not EmployeeWeeklyOffAssignment.objects.filter(employee=user).exists():
                bulk_assign_weekly_off([user.employee_id], policy, user.date_of_joining or today)
        self.stdout.write(f'Employees created: {created} (of {len(data.ROSTER)} in the roster).')
        return everyone

    def _fix_addresses(self, people, branches):
        """The generic profile filler puts everyone in Hyderabad/Bengaluru/Pune; match each person's own office city."""
        for user, row in people:
            spec, city = data.LOCATIONS[row[3]], row[3]
            profile = getattr(user, 'profile', None)
            if profile is None:
                continue
            for field, value in (('current_village', city), ('current_district', city), ('current_state', spec['state']),
                                 ('current_pin_code', spec['pin']), ('bank_branch_name', city), ('gender', row[2])):
                setattr(profile, field, value)
            profile.save()

    def _attendance(self, people, branches, holidays, policy, actor):
        off_days, end = weekly_off_weekdays(policy), timezone.localdate() - timedelta(days=1)
        totals = {'records': 0, 'punches': 0, 'corrections': 0, 'leaves': 0}
        for user in people:
            branch = Branch.objects.filter(branch_name=user.branch).first()
            with transaction.atomic():
                counts = generate_for_employee(user, branch, data.ATTENDANCE_START, end, off_days, holidays, actor)
            for key, value in counts.items():
                totals[key] += value
        self.stdout.write(f'Attendance written: {totals}')

    def _payroll(self, people, branches, actor, any_manager):
        for city, branch in branches.items():
            codes = [u.employee_id for u in people if u.branch == branch.branch_name]
            for period in data.PERIODS:
                try:
                    self.stdout.write('Payroll ' + run_cycle(actor, branch, period, codes, any_manager))
                except PayrollStepError as exc:
                    self.stdout.write(self.style.WARNING(f'Payroll {city} {period[0]}…{period[1]} stopped: {exc}'))

    def _cleanup(self):
        with transaction.atomic():
            cycles = PayrollCycle.objects.filter(notes=data.CYCLE_TAG)
            self.stdout.write(f'Deleting {cycles.count()} tagged payroll cycle(s).')
            # Paid cycles are referenced by protected rows (transfer batches → payslips): remove them first, in order.
            SalaryTransferItem.objects.filter(batch__cycle__in=cycles).delete()
            SalaryTransferBatch.objects.filter(cycle__in=cycles).delete()
            EmployeePayslip.objects.filter(cycle__in=cycles).delete()
            cycles.delete()
            Holiday.objects.filter(description=data.HOLIDAY_TAG).delete()
            try:
                users = User.objects.filter(email__iendswith=data.EMAIL_SUFFIX)
                self.stdout.write(f'Deleting {users.count()} seeded employee(s) and their attendance/leave.')
                Placement.objects.filter(employee__in=users).delete()
                users.delete()
            except ProtectedError as exc:
                raise CommandError(f'Could not delete some seeded employees: {exc}')
        self.stdout.write(self.style.SUCCESS(
            'Cleanup done. Offices, statutory configs, the four persona logins and their attendance are left in place.'))
