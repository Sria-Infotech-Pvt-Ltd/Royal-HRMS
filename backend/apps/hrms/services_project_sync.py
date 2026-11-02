"""
The sync layer around services_project_assignments: every attempt is logged (ProjectSyncLog), employees we can't match
are reported to admins instead of silently dropped, and the pulls (per-employee fallback, scheduled reconcile) live here.
"""
from __future__ import annotations

import logging
from collections import defaultdict

import requests
from django.conf import settings
from django.core.cache import cache

from apps.accounts.models import User
from apps.hrms.models import ProjectAssignment, ProjectSyncLog
from apps.hrms.serializers_project_assignment import ProjectAssignmentRowSerializer
from apps.hrms.services_project_assignments import STATUS_COMPLETED, STATUS_REMOVED, apply_employee_snapshot

logger = logging.getLogger(__name__)

SOURCE_WEBHOOK = 'webhook'
SOURCE_PULL = 'pull'
SOURCE_RECONCILE = 'reconcile'
RECONCILE_ACTOR = 'scheduled_reconcile'
PULL_ACTOR = 'dashboard_fallback_pull'

PROJECT_ASSIGNMENTS_PATH = '/api/v1/project-assignments/'
RESOURCE_ASSIGNMENTS_PATH = '/api/v1/resource-assignments/'
PULL_TIMEOUT_SECONDS = 10
PULL_PAGE_SIZE = 100
PULL_MAX_PAGES = 200
FALLBACK_COOLDOWN_SECONDS = 10 * 60
UNMATCHED_ALERT_COOLDOWN_SECONDS = 24 * 60 * 60

NOTIFICATION_TYPE_PROJECT_SYNC_ALERT = 'project_sync_alert'
NOTIFICATION_MODULE_SYSTEM = 'system'


class ProjectSyncError(Exception):
    """A whole-list pull from Project Budgeting couldn't be completed (so nothing was changed)."""


def alert_admins_unmatched(employee_code: str) -> None:
    """Tell every system admin that Project Budgeting sent projects for an employee_id we don't have. At most once per
    employee per day so a retrying sender can't flood them."""
    if not cache.add(f'project_sync_unmatched:{employee_code}', True, UNMATCHED_ALERT_COOLDOWN_SECONDS):
        return
    from core.access import users_with_permission
    from apps.notifications.signals import _notify

    admins = User.objects.filter(users_with_permission('settings.edit'), is_active=True).distinct()
    for admin in admins:
        _notify(
            admin,
            'Project assignment for unknown employee',
            f'Project Budgeting sent project assignments for employee ID "{employee_code}", which does not match any '
            'employee in AIRA HRMS. The data is stored and will appear once the employee exists. '
            'Check the ID in Project Budgeting.',
            NOTIFICATION_TYPE_PROJECT_SYNC_ALERT, NOTIFICATION_MODULE_SYSTEM, reference_id=employee_code,
        )


def sync_employee_snapshot(employee_code: str, rows: list[dict], *, source: str, triggered_by: str) -> dict:
    """apply_employee_snapshot + sync log + unmatched-employee alert. A failure is logged and re-raised so the sender
    (or Celery) retries."""
    try:
        result = apply_employee_snapshot(employee_code, rows, source=source, triggered_by=triggered_by)
    except Exception as exc:
        logger.exception('Project assignments sync failed for %s', employee_code)
        ProjectSyncLog.objects.create(
            source=source, triggered_by=triggered_by, employee_code=employee_code,
            status=ProjectSyncLog.STATUS_FAILED, message=f'{type(exc).__name__}: {exc}'[:1000],
        )
        raise

    is_matched = User.objects.filter(employee_id=employee_code).exists()
    if not is_matched:
        logger.error('Project assignments synced for unknown employee_id %s; stored for later.', employee_code)
        alert_admins_unmatched(employee_code)
    ProjectSyncLog.objects.create(
        source=source, triggered_by=triggered_by, employee_code=employee_code,
        status=ProjectSyncLog.STATUS_SUCCESS if is_matched else ProjectSyncLog.STATUS_UNMATCHED,
        saved=result['saved'], changed=result['changed'], removed=result['removed'],
        message='' if is_matched else 'No employee in AIRA HRMS has this employee ID.',
    )
    return {**result, 'is_matched': is_matched}


def _credentials() -> tuple[str, str] | None:
    base_url = getattr(settings, 'PROJECT_BUDGET_API_BASE_URL', '')
    api_key = getattr(settings, 'PROJECT_BUDGET_API_KEY', '')
    return (base_url.rstrip('/'), api_key) if base_url and api_key else None


def _get_all_pages(path: str, params: dict) -> list[dict]:
    """Every row from a paginated Project Budgeting list, or ProjectSyncError (callers must not act on partial data)."""
    credentials = _credentials()
    if credentials is None:
        raise ProjectSyncError('PROJECT_BUDGET_API_BASE_URL / PROJECT_BUDGET_API_KEY are not configured.')
    base_url, api_key = credentials
    rows: list[dict] = []
    for page in range(1, PULL_MAX_PAGES + 1):
        try:
            response = requests.get(
                f'{base_url}{path}', params={**params, 'page': page, 'page_size': PULL_PAGE_SIZE},
                headers={'X-API-Key': api_key}, timeout=PULL_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()['data']
            rows.extend(data['results'])
            total_pages = int(data['total_pages'])
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            raise ProjectSyncError(f'Pull of {path} failed on page {page}: {exc}') from exc
        if page >= total_pages:
            return rows
    raise ProjectSyncError(f'Pull of {path} exceeded {PULL_MAX_PAGES} pages.')


def _validated_rows(raw_rows: list[dict]) -> list[dict]:
    serializer = ProjectAssignmentRowSerializer(data=raw_rows, many=True)
    if not serializer.is_valid():
        raise ProjectSyncError(f'Invalid assignment rows: {serializer.errors}')
    return serializer.validated_data


def sync_employee_assignments_if_unknown(employee_code: str) -> None:
    """Dashboard fallback: when we hold no rows for an employee, try one pull. Rate-limited per employee so someone who
    genuinely has no projects doesn't hit Project Budgeting on every dashboard load. Never raises."""
    if not employee_code or _credentials() is None:
        return
    if ProjectAssignment.objects.filter(employee_code=employee_code).exists():
        return
    if not cache.add(f'project_assignments_pull:{employee_code}', True, FALLBACK_COOLDOWN_SECONDS):
        return
    try:
        rows = _validated_rows(_get_all_pages(PROJECT_ASSIGNMENTS_PATH, {'employee_id': employee_code, 'status': 'all'}))
        sync_employee_snapshot(employee_code, rows, source=SOURCE_PULL, triggered_by=PULL_ACTOR)
    except ProjectSyncError as exc:
        logger.warning('Fallback pull failed for %s: %s', employee_code, exc)
        ProjectSyncLog.objects.create(
            source=SOURCE_PULL, triggered_by=PULL_ACTOR, employee_code=employee_code,
            status=ProjectSyncLog.STATUS_FAILED, message=str(exc)[:1000],
        )
    except Exception:  # noqa: BLE001 — sync_employee_snapshot already logged it; the dashboard must still load.
        logger.exception('Fallback pull crashed for %s', employee_code)


def reconcile_all_employees() -> dict:
    """Scheduled safety net for missed pushes: pull EVERY employee assignment (including removed ones) and re-apply
    each employee's list. Employees we hold open assignments for who are absent from the pull are treated as having no
    projects (their rows get closed, not deleted). Raises ProjectSyncError, leaving everything untouched, if any page of
    the pull fails — a partial list must never be read as "these people were removed"."""
    if _credentials() is None:
        return {'skipped': True}
    try:
        raw_rows = _get_all_pages(RESOURCE_ASSIGNMENTS_PATH, {'resource_type': 'employee', 'status': 'all'})
        by_code: dict[str, list[dict]] = defaultdict(list)
        for raw in raw_rows:
            if raw.get('resource_code'):
                by_code[raw['resource_code']].append(raw)
        validated = {code: _validated_rows(rows) for code, rows in by_code.items()}
    except ProjectSyncError as exc:
        ProjectSyncLog.objects.create(
            source=SOURCE_RECONCILE, triggered_by=RECONCILE_ACTOR, status=ProjectSyncLog.STATUS_FAILED,
            message=str(exc)[:1000],
        )
        raise

    held_codes = set(
        ProjectAssignment.objects
        .exclude(assignment_status__in=(STATUS_REMOVED, STATUS_COMPLETED))
        .values_list('employee_code', flat=True)
    )
    failed = 0
    for code in sorted(set(validated) | held_codes):
        try:
            sync_employee_snapshot(code, validated.get(code, []), source=SOURCE_RECONCILE, triggered_by=RECONCILE_ACTOR)
        except Exception:  # noqa: BLE001 — logged per employee inside sync_employee_snapshot; keep going.
            failed += 1
    summary = {'employees': len(set(validated) | held_codes), 'failed': failed}
    ProjectSyncLog.objects.create(
        source=SOURCE_RECONCILE, triggered_by=RECONCILE_ACTOR,
        status=ProjectSyncLog.STATUS_FAILED if failed else ProjectSyncLog.STATUS_SUCCESS,
        saved=len(raw_rows), message=f'Reconciled {summary["employees"]} employees, {failed} failed.',
    )
    return summary
