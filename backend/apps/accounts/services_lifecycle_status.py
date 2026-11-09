"""
Employee lifecycle statuses, DERIVED from fields that already exist. Nothing here is stored, so nothing can drift and nothing
depends on a scheduler having run.

Three independent statuses:
  * Employment Stage - Pre-Joining / Active / Terminated / Unknown (Date Missing), from date_of_joining and separations.
    It is NOT User.employment_status (probation/confirmed, which is unchanged) and it does not look at User.is_active, which
    controls account access and has several meanings.
  * Account Status   - Invitation Pending / Active / Disabled, from is_active, activation_pending, account_activated_at.
    A temporarily locked account (locked_until) is reported separately as `account_locked`, never as Disabled.
  * Onboarding stage - a display label for the existing onboarding_status values (the raw values are unchanged).

"Today" is always the Asia/Kolkata calendar date (settings.TIME_ZONE, via timezone.localdate()).
Callers that handle many people at once use the Q builders / prefetched attributes, so no per-person query is needed.
"""
from __future__ import annotations

import datetime

from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from apps.accounts.models import User

STAGE_PRE_JOINING = 'pre_joining'
STAGE_ACTIVE = 'active'
STAGE_TERMINATED = 'terminated'
STAGE_UNKNOWN = 'unknown'
STAGES = (STAGE_PRE_JOINING, STAGE_ACTIVE, STAGE_TERMINATED, STAGE_UNKNOWN)
STAGE_LABELS = {
    STAGE_PRE_JOINING: 'Pre-Joining', STAGE_ACTIVE: 'Active', STAGE_TERMINATED: 'Terminated', STAGE_UNKNOWN: 'Unknown (Date Missing)',
}

ACCOUNT_INVITATION_PENDING = 'invitation_pending'
ACCOUNT_ACTIVE = 'active'
ACCOUNT_DISABLED = 'disabled'
ACCOUNT_STATUSES = (ACCOUNT_INVITATION_PENDING, ACCOUNT_ACTIVE, ACCOUNT_DISABLED)
ACCOUNT_LABELS = {ACCOUNT_INVITATION_PENDING: 'Invitation Pending', ACCOUNT_ACTIVE: 'Active', ACCOUNT_DISABLED: 'Disabled'}

ONBOARDING_STAGE_BY_STATUS = {
    User.ONBOARDING_PENDING: 'not_started',
    User.ONBOARDING_DRAFT: 'in_progress',
    User.ONBOARDING_SUBMITTED: 'awaiting_review',
    User.ONBOARDING_REJECTED: 'needs_revision',
    User.ONBOARDING_COMPLETE: 'completed',
}
ONBOARDING_STAGES = tuple(ONBOARDING_STAGE_BY_STATUS.values())
ONBOARDING_STAGE_LABELS = {
    'not_started': 'Not Started', 'in_progress': 'In Progress', 'awaiting_review': 'Awaiting Review',
    'needs_revision': 'Needs Revision', 'completed': 'Completed',
}

# What a Pre-Joining / Unknown / Terminated employee may not do (see block_message).
ACTION_PUNCH = 'punch'
ACTION_WFH = 'wfh'
ACTION_LEAVE = 'leave'
ACTION_EXPENSE = 'expense'
ACTION_PAYSLIP = 'payslip'
_BLOCKED_STAGES = {
    ACTION_PUNCH: (STAGE_PRE_JOINING, STAGE_UNKNOWN, STAGE_TERMINATED),
    ACTION_WFH: (STAGE_PRE_JOINING, STAGE_UNKNOWN),
    ACTION_LEAVE: (STAGE_PRE_JOINING,),
    ACTION_EXPENSE: (STAGE_PRE_JOINING,),
    ACTION_PAYSLIP: (STAGE_PRE_JOINING,),
}
_ACTION_NAMES = {
    ACTION_PUNCH: 'mark attendance', ACTION_WFH: 'request work from home', ACTION_LEAVE: 'request leave',
    ACTION_EXPENSE: 'submit expenses', ACTION_PAYSLIP: 'view payslips',
}


def today() -> datetime.date:
    return timezone.localdate()


# ── Queryset building blocks ───────────────────────────────────────────────────

def _separation_model():
    from apps.hrms.models import SeparationRequest

    return SeparationRequest


def _applicable_separations():
    """Approved separations that apply to the CURRENT employment: the last working day is on or after the current joining date.
    An older separation (from before a rehire) is history and never counts. Correlated to the outer employee row."""
    from apps.hrms.models import SEP_APPROVED

    return _separation_model().objects.filter(
        employee=OuterRef('pk'), status=SEP_APPROVED, proposed_last_working_day__gte=OuterRef('date_of_joining'),
    )


def ended_separation_q(as_of: datetime.date | None = None) -> Q:
    """Employees whose LATEST applicable approved last working day is before `as_of` (default: today). A later approved
    separation (an extension) replaces an earlier one, and separations from before a rehire are ignored."""
    day = as_of or today()
    applicable = _applicable_separations()
    return Q(Exists(applicable.filter(proposed_last_working_day__lt=day))) & ~Q(Exists(applicable.filter(proposed_last_working_day__gte=day)))


def stage_q(stage: str, as_of: datetime.date | None = None) -> Q:
    day = as_of or today()
    not_ended = ~ended_separation_q(day)
    if stage == STAGE_TERMINATED:
        return ended_separation_q(day)
    if stage == STAGE_UNKNOWN:
        return not_ended & Q(date_of_joining__isnull=True)
    if stage == STAGE_PRE_JOINING:
        return not_ended & Q(date_of_joining__gt=day)
    if stage == STAGE_ACTIVE:
        return not_ended & Q(date_of_joining__lte=day)
    raise ValueError(f'Unknown employment stage: {stage}')


def joined_q(as_of: datetime.date | None = None) -> Q:
    """The joining date has arrived. A blank joining date never matches."""
    return Q(date_of_joining__lte=as_of or today())


def attendance_eligible_q(as_of: datetime.date | None = None) -> Q:
    """Expected to attend on `as_of`: account active, joined by then, and not past an approved last working day."""
    day = as_of or today()
    return Q(is_active=True) & joined_q(day) & ~ended_separation_q(day)


def account_status_q(status: str) -> Q:
    if status == ACCOUNT_DISABLED:
        return Q(is_active=False)
    pending = Q(activation_pending=True) | Q(account_activated_at__isnull=True)
    if status == ACCOUNT_INVITATION_PENDING:
        return Q(is_active=True) & pending
    if status == ACCOUNT_ACTIVE:
        return Q(is_active=True) & ~pending
    raise ValueError(f'Unknown account status: {status}')


def onboarding_stage_q(stage: str) -> Q:
    statuses = [raw for raw, label in ONBOARDING_STAGE_BY_STATUS.items() if label == stage]
    if not statuses:
        raise ValueError(f'Unknown onboarding stage: {stage}')
    return Q(onboarding_status__in=statuses)


# ── Single-person derivation ───────────────────────────────────────────────────

def applicable_last_working_days(date_of_joining: datetime.date | None, last_days) -> list:
    """The approved last working days that apply to the current employment (on or after the joining date)."""
    if date_of_joining is None:
        return []
    return [d for d in last_days if d >= date_of_joining]


def latest_last_working_day(date_of_joining: datetime.date | None, last_days) -> datetime.date | None:
    """The latest approved last working day of the current employment, or None."""
    applicable = applicable_last_working_days(date_of_joining, last_days)
    return max(applicable) if applicable else None


def separation_has_ended(date_of_joining: datetime.date | None, last_days, as_of: datetime.date) -> bool:
    """Pure form of ended_separation_q for one person: the latest applicable last working day is before `as_of`."""
    latest = latest_last_working_day(date_of_joining, last_days)
    return latest is not None and latest < as_of


def approved_last_working_days(user: User) -> list:
    """Every approved last working day on record for `user` (the directory passes them prefetched)."""
    from apps.hrms.models import SEP_APPROVED

    prefetched = getattr(user, 'directory_approved_separations', None)
    if prefetched is not None:
        return [separation.proposed_last_working_day for separation in prefetched]
    return list(user.separation_requests.filter(status=SEP_APPROVED).values_list('proposed_last_working_day', flat=True))


def has_ended_separation(user: User, as_of: datetime.date | None = None) -> bool:
    return separation_has_ended(user.date_of_joining, approved_last_working_days(user), as_of or today())


def ended_employee_ids(users, as_of: datetime.date | None = None) -> set:
    """Primary keys of those among `users` whose employment has ended, for a list of people, with one query for all of them."""
    from apps.hrms.models import SEP_APPROVED

    people = list(users)
    by_employee: dict = {}
    rows = _separation_model().objects.filter(employee_id__in=[u.pk for u in people], status=SEP_APPROVED)
    for employee_id, last_day in rows.values_list('employee_id', 'proposed_last_working_day'):
        by_employee.setdefault(employee_id, []).append(last_day)
    day = as_of or today()
    return {u.pk for u in people if separation_has_ended(u.date_of_joining, by_employee.get(u.pk, []), day)}


def employment_stage(user: User, as_of: datetime.date | None = None, *, ended: bool | None = None) -> str:
    """`ended` lets a caller that already knows (a batch lookup) skip the separation query."""
    day = as_of or today()
    if ended is None:
        ended = has_ended_separation(user, day)
    if ended:
        return STAGE_TERMINATED
    if user.date_of_joining is None:
        return STAGE_UNKNOWN
    return STAGE_PRE_JOINING if user.date_of_joining > day else STAGE_ACTIVE


# ── Eligibility on a given DATE (HR entry points that record attendance for a past day) ───────────────────────────────

ATTENDANCE_DATE_PROBLEMS = {
    'no_joining_date': 'This employee has no joining date. Correct the joining date first.',
    'before_joining': 'The employee had not joined by that date.',
    'after_last_working_day': 'The employee\'s employment had ended by that date.',
}


def attendance_date_problem_code(date_of_joining: datetime.date | None, last_days, on_date: datetime.date) -> str | None:
    """Why attendance cannot be recorded for an employee ON `on_date` (None when it can). Unlike the live punch rule this looks
    at the date itself, so HR can still record or correct a day that fell inside the employment of someone who has since left."""
    if date_of_joining is None:
        return 'no_joining_date'
    if on_date < date_of_joining:
        return 'before_joining'
    latest = latest_last_working_day(date_of_joining, last_days)
    if latest is not None and on_date > latest:
        return 'after_last_working_day'
    return None


def attendance_date_problem(user: User, on_date: datetime.date) -> str | None:
    """The plain-language reason attendance cannot be recorded for `user` on `on_date`, or None."""
    code = attendance_date_problem_code(user.date_of_joining, approved_last_working_days(user), on_date)
    return ATTENDANCE_DATE_PROBLEMS[code] if code else None


# ── Changing a joining date on someone with earlier separations (rehire) ─────────────────────────────────────────────

def validate_joining_date_change(user: User, new_date: datetime.date) -> str | None:
    """A new joining date may not fall before the last working day of the PREVIOUS employment: that would overlap two periods.
    "Previous" means approved last working days before the current joining date. With no current joining date there is no
    previous period to compare with, so nothing is refused."""
    current = user.date_of_joining
    if current is None:
        return None
    previous = [d for d in approved_last_working_days(user) if d < current]
    if previous and new_date < max(previous):
        return f'The new joining date must not be before the last working day of the previous employment ({max(previous):%d %b %Y}).'
    return None


def joining_date_change_audit(user: User, new_date: datetime.date) -> dict | None:
    """What to record when HR changes the joining date of someone who has separations on record (None when they have none)."""
    from apps.hrms.models import SeparationRequest

    if not SeparationRequest.objects.filter(employee=user).exists():
        return None
    last_days = approved_last_working_days(user)
    old = user.date_of_joining
    latest_before = latest_last_working_day(old, last_days)
    latest_after = latest_last_working_day(new_date, last_days)
    return {
        'joining_date': {'from': str(old) if old else None, 'to': str(new_date)},
        'approved_last_working_days': sorted(d.isoformat() for d in last_days),
        'applicable_last_working_day_before': latest_before.isoformat() if latest_before else None,
        'applicable_last_working_day_after': latest_after.isoformat() if latest_after else None,
    }


def account_status(user: User) -> str:
    if not user.is_active:
        return ACCOUNT_DISABLED
    if user.activation_pending or user.account_activated_at is None:
        return ACCOUNT_INVITATION_PENDING
    return ACCOUNT_ACTIVE


def account_locked(user: User) -> bool:
    return bool(user.locked_until and user.locked_until > timezone.now())


def onboarding_stage(user: User) -> str:
    return ONBOARDING_STAGE_BY_STATUS.get(user.onboarding_status, 'in_progress')


def lifecycle_summary(user: User, *, ended: bool | None = None) -> dict:
    """The API block added to employee payloads. All additive; the legacy `status` field is unchanged."""
    stage = employment_stage(user, ended=ended)
    return {
        'employment_stage': stage,
        'employment_stage_label': STAGE_LABELS[stage],
        'date_missing': stage == STAGE_UNKNOWN,
        'account_status': account_status(user),
        'account_locked': account_locked(user),
        'onboarding_stage': onboarding_stage(user),
    }


# ── Guards for the employee's own actions ──────────────────────────────────────

def blocked_stage(user: User, action: str) -> str | None:
    """The employment stage that stops `user` performing `action` right now, or None when it is allowed."""
    stage = employment_stage(user)
    return stage if stage in _BLOCKED_STAGES[action] else None


def block_message(user: User, action: str) -> str | None:
    """Why `user` may not perform `action` right now, in words safe to show, or None when allowed."""
    stage = blocked_stage(user, action)
    if stage is None:
        return None
    verb = _ACTION_NAMES[action]
    if stage == STAGE_PRE_JOINING:
        return f'You can {verb} from your joining date, {user.date_of_joining:%d %b %Y}.'
    if stage == STAGE_UNKNOWN:
        return f'Your joining date is missing, so you cannot {verb} yet. Please contact HR to correct it.'
    return 'Your employment has ended, so you can no longer ' + verb + '.'
