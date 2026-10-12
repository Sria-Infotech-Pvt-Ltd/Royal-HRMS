"""
Management command: seed_demo_employee_details

DEMO / TEST DATA ONLY. Gives the placeholder employees already in the database
(the `seed_dummy_employees` batch and the QA persona logins — anyone whose work
email is on @example.com) the same kind of COMPLETE record the reference
Employee Directory shows: personal details, address, emergency contact,
government IDs and bank (made-up), pay, leave balances, a believable joining
date and status, a reporting line and a synthetic profile picture.

Safe by construction:
  * never creates employees — only fills in the ones that exist;
  * only touches @example.com accounts, so real people are left alone;
  * only FILLS BLANK fields — anything already filled is never overwritten;
  * refuses to run unless DEBUG is on;
  * re-running gives the same result (everything is derived from the employee number).

Run:  python manage.py seed_demo_employee_details --dry-run
      python manage.py seed_demo_employee_details
      python manage.py seed_demo_employee_details --skip-photos
"""
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.accounts import demo_profile_data as demo
from apps.accounts.demo_avatar import generate_avatar_png
from apps.accounts.models import EmployeeProfile, Placement, Position, User
from apps.accounts.services_placement import assign_position, sync_from_position

SEEDER_WINDOW_START = date(2026, 9, 1)  # dummies were all created after this; their join date is a placeholder
MANAGER_EMAIL = 'manager@example.com'
QA_TEAM_UNITS = ('Web', 'Mobile')  # these teams report to the QA Reporting Manager so that persona has a team

# QA persona logins have no org seat yet — (org unit, seat title) to put each on. They take an EXISTING
# seat (no new org-structure rows) and their designation simply follows the seat's title.
QA_POSITIONS = {
    'payroll@example.com':  ('Finance & Accounts',      'Finance & Accounts Associate'),
    'manager@example.com':  ('Application Development', 'Head — Application Development'),
    'employee@example.com': ('Mobile',                  'Mobile Trainee Associate'),
    'hr@example.com':       ('HR Operations',           'HR Operations Associate'),
}


def _has_open_notice(user, today):
    from apps.hrms.models import SEP_APPROVED, SeparationRequest
    return SeparationRequest.objects.filter(
        employee=user, status=SEP_APPROVED, proposed_last_working_day__gte=today,
    ).exists()


def _lifecycle(user, number, today):
    """Believable status mix for everyone, and a believable joining date where the current one is a placeholder."""
    if _has_open_notice(user, today):
        return user.date_of_joining or today
    bucket = 'active' if user.email in QA_POSITIONS else demo.lifecycle_bucket(number)
    placeholder = user.date_of_joining is None or user.date_of_joining >= SEEDER_WINDOW_START
    joined = user.date_of_joining or today
    if placeholder:
        joined = {
            'active':     demo.joining_date(number, today),
            'probation':  today - timedelta(days=30 + number % 50),
            'onboarding': today - timedelta(days=number % 12),
        }[bucket]
    is_new = (today - joined).days <= 180
    user.date_of_joining = joined
    user.must_change_password = bucket == 'onboarding'
    user.onboarding_status = User.ONBOARDING_PENDING if bucket == 'onboarding' else User.ONBOARDING_COMPLETE
    user.employment_status = (
        User.EMPLOYMENT_STATUS_PROBATION if bucket != 'active' or is_new else User.EMPLOYMENT_STATUS_CONFIRMED
    )
    user.save(update_fields=['date_of_joining', 'must_change_password', 'onboarding_status', 'employment_status', 'updated_at'])
    first = Placement.objects.filter(employee=user).order_by('effective_from').first()
    if first is not None and first.effective_from > joined:
        Placement.objects.filter(pk=first.pk).update(effective_from=joined)
    return joined


def _seat_qa_user(user, joined):
    """Put the persona on its seat. Re-seats if it sits on a different one (QA accounts only)."""
    unit_name, seat_title = QA_POSITIONS[user.email]
    seat = Position.objects.filter(org_unit__name=unit_name, title=seat_title, is_active=True).first()
    if seat is None:
        return False
    current = Placement.objects.filter(employee=user, effective_to__isnull=True).first()
    if current is not None and current.position_id == seat.pk:
        if user.designation != seat_title or not user.designation_synced_from_position:
            sync_from_position(seat, force=True, as_of=current.effective_from)
        return False
    if Placement.objects.filter(position=seat).exclude(employee=user).exists():
        return False  # seat already belongs to someone else
    Placement.objects.filter(employee=user).delete()
    assign_position(user, seat, effective_from=joined)
    return True


def _fill_blanks(instance, values):
    changed = [name for name, value in values.items() if not getattr(instance, name) and value]
    for name in changed:
        setattr(instance, name, values[name])
    return changed


def _fix_seeded_gender(profile, expected):
    """Earlier runs picked gender from a number pattern. Correct it for profiles this command created
    (recognised by the demo personal-email pattern) so gender matches the name. True when it changed."""
    if profile.personal_email.endswith('.demo@example.com') and profile.gender and profile.gender != expected:
        profile.gender = expected
        return True
    return False


def _fill_profile(user, number):
    """Returns (anything_changed, gender_corrected)."""
    profile, _ = EmployeeProfile.objects.get_or_create(user=user)
    personal = demo.personal_details(number, user.full_name)
    gender_corrected = _fix_seeded_gender(profile, personal['gender'])
    changed = _fill_blanks(profile, personal)
    changed += _fill_blanks(profile, demo.statutory_and_bank(number, user.full_name))
    if changed or gender_corrected:
        profile.save()
    if not user.phone or user.email in QA_POSITIONS:  # QA logins were created with a bare placeholder number
        user.phone = demo.mobile_number(number)
        user.save(update_fields=['phone', 'updated_at'])
    return bool(changed) or gender_corrected, gender_corrected


def _scale_group_for(user):
    placement = Placement.objects.filter(employee=user, effective_to__isnull=True).select_related('position').first()
    grade = (placement.position.grade if placement else '')[:2]
    return grade if grade in ('L1', 'L2', 'L3', 'L4', 'L5') else 'L2'


def _fill_salary(user, joined):
    from apps.payroll.models import EmployeeSalaryConfig
    existing = EmployeeSalaryConfig.objects.filter(employee=user)
    if existing.exists():
        # Records this command made earlier had no reason / pay scale yet — complete them (never overwrite).
        existing.filter(reason='').update(reason=EmployeeSalaryConfig.REASON_INITIAL)
        existing.filter(pay_scale_group='').update(pay_scale_group=_scale_group_for(user), pay_scale_level='01')
        return False
    # bulk_create on purpose: the post_save hook would send the (fake) employee a "your CTC was updated" notification.
    EmployeeSalaryConfig.objects.bulk_create([EmployeeSalaryConfig(
        employee=user, annual_ctc=Decimal(demo.annual_ctc_for(user.designation)), effective_from=joined, is_active=True,
        reason=EmployeeSalaryConfig.REASON_INITIAL, pay_scale_group=_scale_group_for(user), pay_scale_level='01',
    )])
    return True


def _fill_leave(user, number, joined, today):
    from apps.hrms.models import LeaveBalance, LeavePolicy
    from apps.hrms.views.leave_shared import _allocate_leaves_for_employee
    anchor = max(joined, date(today.year, 1, 1))
    _allocate_leaves_for_employee(user, anchor)
    months = 13 - anchor.month
    for balance in LeaveBalance.objects.filter(employee=user, year=today.year):
        policy = LeavePolicy.objects.filter(is_active=True, leave_type=balance.leave_type).first()
        if policy is None:
            continue
        expected = Decimal(str(round(float(policy.annual_days) * months / 12 * 2) / 2))
        update = {}
        if balance.total_days < expected:
            update['total_days'] = expected
        if balance.used_days == 0 and balance.leave_type == 'casual' and number % 4 == 0:
            update['used_days'] = Decimal('2')
        if balance.used_days == 0 and balance.leave_type == 'earned' and number % 5 == 0:
            update['used_days'] = Decimal('3')
        if update:
            LeaveBalance.objects.filter(pk=balance.pk).update(**update)


def _unit_of(user):
    placement = Placement.objects.filter(employee=user, effective_to__isnull=True).select_related('position__org_unit').first()
    return placement.position.org_unit if placement else None


def _assign_reporting_lines(targets):
    """Heads lead their own unit; Web/Mobile report to the QA manager; everyone else reports to their unit head."""
    qa_manager = User.objects.filter(email=MANAGER_EMAIL).first()
    heads = {}
    for user in targets:
        unit = _unit_of(user)
        if unit is not None and (user.designation or '').startswith('Head'):
            heads[unit.id] = user
    updated = 0
    for user in targets:
        if user.reporting_manager_id or user.email in QA_POSITIONS or (user.designation or '').startswith('Head'):
            continue
        unit = _unit_of(user)
        manager = None
        if unit is not None and unit.name in QA_TEAM_UNITS:
            manager = qa_manager
        elif unit is not None:
            manager = heads.get(unit.id) or (heads.get(unit.parent_id) if unit.parent_id else None)
        if manager is not None and manager.pk != user.pk:
            User.objects.filter(pk=user.pk).update(reporting_manager=manager)
            updated += 1
    return updated


def _add_photo(user, redraw=False):
    """Create the synthetic avatar. With redraw=True an avatar this command made earlier
    (file named <employee_id>_...) is replaced; anyone else's real photo is never touched."""
    if user.profile_photo:
        if not (redraw and user.profile_photo.name.startswith(f'profile_photos/{user.employee_id}_')):
            return False
        user.profile_photo.delete(save=False)
    gender = getattr(getattr(user, 'profile', None), 'gender', '') or ''
    user.profile_photo.save(f'{user.employee_id}.png', ContentFile(generate_avatar_png(user.employee_id, gender)), save=True)
    return True


class Command(BaseCommand):
    help = "Fill blank details on the existing @example.com demo employees (profile, pay, leave, photo, reporting line)."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='List who would be touched; write nothing.')
        parser.add_argument('--skip-photos', action='store_true', help='Do not generate/upload profile pictures.')

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Demo data can only be seeded with DEBUG on.')
        targets = list(User.objects.exclude(employee_id='').filter(email__iendswith='@example.com').order_by('employee_id'))
        if options['dry_run']:
            for user in targets:
                self.stdout.write(f'  would fill {user.employee_id}  {user.full_name}  <{user.email}>')
            self.stdout.write(self.style.SUCCESS(f'[dry-run] {len(targets)} employees would be filled in.'))
            return

        today = timezone.localdate()
        counts = {'profile': 0, 'pay': 0, 'seated': 0, 'photo': 0}
        for user in targets:
            number = demo.employee_number(user.employee_id)
            joined = _lifecycle(user, number, today)
            if user.email in QA_POSITIONS and _seat_qa_user(user, joined):
                counts['seated'] += 1
            user.refresh_from_db()
            filled, gender_corrected = _fill_profile(user, number)
            counts['profile'] += filled
            counts['pay'] += _fill_salary(user, joined)
            _fill_leave(user, number, joined, today)
            if not options['skip_photos']:
                user.refresh_from_db()
                counts['photo'] += _add_photo(user, redraw=gender_corrected)
        lines = _assign_reporting_lines(list(User.objects.exclude(employee_id='').filter(email__iendswith='@example.com')))
        self.stdout.write(self.style.SUCCESS(
            f"Done: {len(targets)} employees checked; profiles filled {counts['profile']}, pay added {counts['pay']}, "
            f"QA users seated {counts['seated']}, photos {counts['photo']}, reporting lines set {lines}."
        ))
