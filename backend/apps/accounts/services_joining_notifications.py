"""
Joining-day notifications: when an employee's joining date arrives, tell the employee, their reporting manager, and the HR
users who may review that employee's onboarding (`onboarding.approve`) and are in scope for them.

Only a side effect. No status is written here: Employment Stage is derived from the joining date (services_lifecycle_status)
and is correct whether or not this ever runs. Each (employee, recipient) pair is recorded in the audit log, so running the
task twice, or catching up after downtime, never notifies anyone twice.
"""
from __future__ import annotations

import datetime
import hashlib
import logging

from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.models import AuditLog, User

logger = logging.getLogger(__name__)

AUDIT_ACTION = 'joining_notification_sent'
CATCH_UP_DAYS = 3          # a missed scheduler run is made up for on the next ones, for this many days after joining
HR_PERMISSION = 'onboarding.approve'


def _recipients(employee: User) -> list[tuple[User, str]]:
    """(recipient, role) pairs, each person once: the employee, the resolved reporting manager, and in-scope HR."""
    from apps.accounts.services_reporting_line import resolve_manager
    from core.access import employee_in_scope, users_with_permission

    found: dict = {employee.pk: (employee, 'employee')}
    manager = resolve_manager(employee)
    if manager is not None and manager.pk not in found:
        found[manager.pk] = (manager, 'manager')
    candidates = User.objects.filter(users_with_permission(HR_PERMISSION), is_active=True).exclude(pk=employee.pk).distinct()
    for hr_user in candidates:
        if hr_user.pk not in found and employee_in_scope(hr_user, employee):
            found[hr_user.pk] = (hr_user, 'hr')
    return list(found.values())


def _already_sent(employee: User, recipient: User, joined_on: datetime.date) -> bool:
    """One joining EVENT is an employee plus a joining date, so a rehire with a new joining date is notified again."""
    return AuditLog.objects.filter(
        action=AUDIT_ACTION, module='accounts', object_id=str(employee.pk), changes__recipient=str(recipient.pk),
        changes__joining_date=joined_on.isoformat(),
    ).exists()


def _lock_key(employee: User, recipient: User, joined_on: datetime.date) -> int:
    """A stable 64-bit key for one (employee, recipient, joining date), for a Postgres advisory lock."""
    digest = hashlib.sha256(f'joining:{employee.pk}:{recipient.pk}:{joined_on.isoformat()}'.encode()).digest()
    return int.from_bytes(digest[:8], 'big', signed=True)


def _text(employee: User, role: str, joined_on: datetime.date) -> tuple[str, str]:
    name = employee.full_name or employee.email
    if role == 'employee':
        return ('Welcome - your joining date is here',
                f'Today ({joined_on:%d %b %Y}) is your joining date. You can now use attendance, leave and the rest of your workspace.')
    return (f'{name} has joined',
            f'{name} ({employee.employee_id}) joined on {joined_on:%d %b %Y}. Their onboarding status is {employee.onboarding_status}.')


def _reference(employee: User, role: str) -> str:
    """What the notification bell links to: the employee's own profile for them, the employee's record for everyone else."""
    return 'profile' if role == 'employee' else f'employee:{employee.employee_id}'


def _notify(employee: User, recipient: User, role: str, joined_on: datetime.date) -> bool:
    from apps.notifications.models import Notification
    from apps.notifications.signals import _category_enabled

    # Check, send and record under one lock per (employee, recipient, joining date): a second worker running at the same moment
    # waits here, then finds the marker the first one wrote and does nothing. The lock is held until the transaction ends, so the
    # notification and its marker become visible together (or not at all).
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(%s)', [_lock_key(employee, recipient, joined_on)])
        if _already_sent(employee, recipient, joined_on):
            return False
        # Type and module are both `system` (like the other system messages), and a person who has switched system
        # notifications off is not sent one. The marker is still written, so a later run does not try again for this person.
        is_enabled = _category_enabled(recipient, 'system')
        if is_enabled:
            title, message = _text(employee, role, joined_on)
            Notification.objects.create(
                user=recipient, title=title, message=message, notification_type='system', module='system',
                reference_id=_reference(employee, role),
            )
        AuditLog.objects.create(
            user=None, action=AUDIT_ACTION, module='accounts', object_id=str(employee.pk), branch=employee.branch,
            changes={'recipient': str(recipient.pk), 'role': role, 'joining_date': joined_on.isoformat(), 'delivered': is_enabled},
        )
    return is_enabled


def notify_joiners(as_of: datetime.date | None = None) -> dict:
    """Notify for everyone whose joining date is `as_of` (default: today, Asia/Kolkata) or in the catch-up window before it."""
    from apps.accounts.services_lifecycle_status import STAGE_ACTIVE, stage_q

    day = as_of or timezone.localdate()
    joiners = (
        User.objects.filter(is_active=True, date_of_joining__gte=day - datetime.timedelta(days=CATCH_UP_DAYS), date_of_joining__lte=day)
        .exclude(employee_id='').filter(stage_q(STAGE_ACTIVE, day))
    )
    sent, skipped, failed = 0, 0, 0
    for employee in joiners:
        try:
            for recipient, role in _recipients(employee):
                if _notify(employee, recipient, role, employee.date_of_joining):
                    sent += 1
                else:
                    skipped += 1
        except Exception:  # noqa: BLE001 - one employee's problem must not stop everyone else's notifications
            logger.exception('Joining notification failed for employee %s', employee.pk)
            failed += 1
    return {'employees': joiners.count(), 'sent': sent, 'already_sent': skipped, 'failed': failed}
