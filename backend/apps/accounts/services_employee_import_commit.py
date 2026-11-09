"""
Commit step of the bulk employee import.

The browser sends the same file again together with the SHA-256 it was shown at preview. The file is re-read and every row
is re-validated here (the preview is advice, this is the check), then ALL employees are created in one database
transaction: if anything fails, nothing is created. Activation invites are sent only after that transaction has committed,
in the background (see services_employee_import_invites), and an invite that fails is reported separately from the
(already successful) creation.

A batch_id makes a retry safe: committing the same batch again returns the earlier result instead of creating anyone twice.
No audit entry or log line carries personal data, only the batch id, the file hash and counts.
"""
from __future__ import annotations

import logging
import secrets
import string
from dataclasses import dataclass, field

from django.db import IntegrityError, transaction

from apps.accounts.models import AuditLog, EmployeeCodeSeries, EmployeeIdSeriesExhausted, EmployeeProfile, User
from apps.accounts.services_employee_import import (
    _PHONE_FORMATTING_RE, BLOOD_GROUPS, GENDERS, ParsedFile, RowResult, file_sha256, parse_workbook, summarise, validate_rows,
)
from apps.accounts.services_placement import assign_position
from apps.accounts.services_employee_import_invites import dispatch_invites

logger = logging.getLogger(__name__)

AUDIT_ACTION = 'employee_bulk_import_committed'


class ImportRejected(Exception):
    """Nothing was created. `results` are the rows with their errors; `message` is safe to show."""

    def __init__(self, message: str, results: list[RowResult] | None = None):
        super().__init__(message)
        self.message = message
        self.results = results or []


@dataclass
class CommitOutcome:
    batch_id: str
    created: int
    already_committed: bool = False
    created_employees: list[dict] = field(default_factory=list)      # employee_id and name only
    invites_total: int = 0
    invites_sent: int = 0                                            # so far; the rest are still being sent
    invite_failures: list[dict] = field(default_factory=list)        # row, employee_id, reason


def _digits(raw: str) -> str:
    return _PHONE_FORMATTING_RE.sub('', raw or '')


def _create_one(importer: User, result: RowResult, ip_address: str | None) -> User:
    from apps.accounts.views.shared import _auto_assign_managers
    from apps.attendance.models import WeeklyDayPolicy
    from apps.attendance.services_hr import assign_weekly_off
    from apps.hrms.views.leave_shared import _allocate_leaves_for_employee
    from core.permissions import has_perm

    values = result.values
    employee_id = EmployeeCodeSeries.generate_employee_id_for_type(result.employee_type)
    user = User.objects.create_user(
        email=values['email'],
        password=''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16)),
        full_name=f"{values['first_name']} {values['last_name']}",
        employee_id=employee_id,
        branch=result.branch_name,
        phone=_digits(values.get('phone', '')),
        employee_type=result.employee_type,
        date_of_joining=result.date_of_joining,
        must_change_password=True,
        onboarding_status=User.ONBOARDING_PENDING,
    )
    assign_position(user, result.position, effective_from=result.date_of_joining, created_by=importer)
    user.refresh_from_db()
    changed: list[str] = []
    if result.manager is not None:
        user.reporting_manager = result.manager
        user.reporting_manager_from_org_chart = False
        changed += ['reporting_manager', 'reporting_manager_from_org_chart']
    changed += _auto_assign_managers(user)
    # Same rule as creating one employee: the HR user doing the import becomes that employee's HR when none was resolved.
    if has_perm(importer, 'employees.edit') and user.hr_id is None and user.pk != importer.pk:
        user.hr = importer
        changed.append('hr')
    if changed:
        user.save(update_fields=[*dict.fromkeys(changed), 'updated_at'])
    _save_profile(user, result)
    _allocate_leaves_for_employee(user, user.date_of_joining)
    policy = WeeklyDayPolicy.objects.filter(is_default=True, is_active=True).first()
    if policy is not None:
        assign_weekly_off(employee_id, policy, result.date_of_joining, actor=importer)
    return user


def _save_profile(user: User, result: RowResult) -> None:
    values = result.values
    fields = {
        'gender': GENDERS.get(values.get('gender', '').lower(), ''),
        'date_of_birth': result.date_of_birth,
        'blood_group': BLOOD_GROUPS.get(values.get('blood_group', '').lower(), ''),
        'personal_email': values.get('personal_email', ''),
        'current_address': values.get('address_line1', ''),
        'current_address_line2': values.get('address_line2', ''),
        'current_district': values.get('district', ''),
        'current_state': values.get('state', ''),
        'current_pin_code': values.get('pin_code', ''),
        'emergency_name': values.get('emergency_name', ''),
        'emergency_relationship': values.get('emergency_relationship', ''),
        'emergency_phone': _digits(values.get('emergency_phone', '')),
    }
    EmployeeProfile.objects.get_or_create(user=user, defaults={k: v for k, v in fields.items() if v not in ('', None)})


def previous_commit(importer: User, batch_id: str) -> AuditLog | None:
    return AuditLog.objects.filter(user=importer, action=AUDIT_ACTION, module='accounts', changes__batch_id=batch_id).first()


def commit_import(importer: User, content: bytes, *, batch_id: str, expected_hash: str, ip_address: str | None = None) -> CommitOutcome:
    earlier = previous_commit(importer, batch_id)
    if earlier is not None:
        return CommitOutcome(batch_id=batch_id, created=int(earlier.changes.get('created', 0)), already_committed=True)
    if file_sha256(content) != (expected_hash or '').lower():
        raise ImportRejected('The file is not the one you previewed. Upload it again and review the preview.')
    parsed: ParsedFile = parse_workbook(content)
    results = validate_rows(importer, parsed)
    summary = summarise(results)
    if not summary.can_import:
        raise ImportRejected(f'{summary.invalid} of {summary.total} rows have errors. No employees were created.', results)
    created: list[tuple[RowResult, User]] = []
    try:
        with transaction.atomic():
            for result in results:
                created.append((result, _create_one(importer, result, ip_address)))
            AuditLog.objects.create(
                user=importer, action=AUDIT_ACTION, module='accounts', object_id=batch_id,
                changes={'batch_id': batch_id, 'file_sha256': file_sha256(content), 'created': len(created)},
                branch=importer.branch, ip_address=ip_address,
            )
    except EmployeeIdSeriesExhausted as exc:
        raise ImportRejected(f'{exc} No employees were created.')
    except IntegrityError:
        logger.warning('Bulk import %s rolled back on a database constraint', batch_id)
        raise ImportRejected('Someone created one of these employees while you were importing. No employees were created. Preview the file again.')
    outcome = CommitOutcome(batch_id=batch_id, created=len(created))
    outcome.created_employees = [{'employee_id': user.employee_id, 'name': user.full_name} for _r, user in created]
    items = [(result.row, str(user.pk), user.employee_id) for result, user in created]
    progress = dispatch_invites(importer, batch_id, items, ip_address)
    outcome.invites_total, outcome.invites_sent, outcome.invite_failures = len(items), progress['sent'], progress['failed']
    logger.info('Bulk import %s created %s employees', batch_id, outcome.created)
    return outcome
