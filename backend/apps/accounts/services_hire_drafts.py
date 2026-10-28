"""
Hire-wizard drafts: discarding one for real, giving back its reserved employee number, expiring stale ones, and spotting
drafts for people who already are employees.

"Save & exit" keeps a draft. "Discard" (the wizard button, the Drafts list's Delete, and expiry) ends it: the draft leaves
the list, its reserved number is released when that is safe (see EmployeeCodeSeries.release_employee_id), and an audit
entry records who did it and why.
"""
from __future__ import annotations

import re
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.accounts.models import AuditLog, EmployeeCodeSeries, HireAction, User

DEFAULT_EXPIRY_DAYS = 30


def draft_expiry_days() -> int:
    return int(getattr(settings, 'HIRE_DRAFT_EXPIRY_DAYS', DEFAULT_EXPIRY_DAYS))


def _draft_text(draft_data: dict, key: str) -> str:
    value = (draft_data or {}).get(key) or ''
    if isinstance(value, list):  # stray list-wrapped values from old multipart PATCHes
        value = value[0] if value else ''
    return str(value).strip()


def discard_draft(action: HireAction, actor: User | None, reason: str = 'discarded', ip_address: str | None = None) -> bool:
    """Ends one draft. Returns True when its reserved employee number went back to the series."""
    reserved = action.reserved_employee_id
    is_released = bool(reserved and EmployeeCodeSeries.release_employee_id(action.employment_type, reserved))
    action.status = HireAction.STATUS_DISCARDED
    action.reserved_employee_id = ''
    action.save(update_fields=['status', 'reserved_employee_id', 'updated_at'])
    AuditLog.objects.create(
        user=actor, action=f'hire_draft_{reason}', module='employees', object_id=str(action.id),
        changes={'reserved_employee_id': reserved, 'number_released': is_released},
        ip_address=ip_address,
    )
    return is_released


def find_stale_drafts(now=None):
    cutoff = (now or timezone.now()) - timedelta(days=draft_expiry_days())
    return HireAction.objects.filter(status=HireAction.STATUS_DRAFT, updated_at__lt=cutoff)


def _last_ten_digits(raw: str) -> str:
    return re.sub(r'\D', '', raw or '')[-10:]


def existing_employee_match(action: HireAction) -> str:
    """Why this draft looks like someone who already is an employee ('' when it does not): same email or same mobile."""
    data = action.draft_data or {}
    emails = {_draft_text(data, 'email').lower(), _draft_text(data, 'work_email').lower()} - {''}
    if emails and User.objects.filter(email__in=emails).exists():
        return 'email matches an existing employee'
    mobile = _last_ten_digits(_draft_text(data, 'phone'))
    if len(mobile) == 10:
        phones = User.objects.exclude(phone='').values_list('phone', flat=True)
        if any(_last_ten_digits(phone) == mobile for phone in phones):
            return 'mobile matches an existing employee'
    return ''


def find_conflicting_drafts():
    """(draft, reason) for every open draft that matches an existing employee. Never discarded automatically: a human decides."""
    drafts = HireAction.objects.select_related('position').filter(status=HireAction.STATUS_DRAFT)
    return [(draft, reason) for draft in drafts if (reason := existing_employee_match(draft))]


def expire_stale_drafts() -> int:
    """Discards every draft untouched for HIRE_DRAFT_EXPIRY_DAYS (default 30). Returns how many."""
    count = 0
    for action in find_stale_drafts():
        discard_draft(action, actor=None, reason='expired')
        count += 1
    return count
